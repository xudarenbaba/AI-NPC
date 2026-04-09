""" 大模型调用（OpenAI 兼容 / DeepSeek），支持 Function Calling """
import json
import logging
from typing import Any

from openai import OpenAI

from app.config import load_config
from app.integrations.mcp_client import MCPToolClient
from app.schemas.response import ActionResponse
from app.tools.location_tools import resolve_location_coordinates

logger = logging.getLogger(__name__)


def _preview(text: str, limit: int = 300) -> str:
    t = (text or "").replace("\n", "\\n")
    return t if len(t) <= limit else t[:limit] + "..."


# 与 ActionResponse 对应的 Function Calling schema，供 DeepSeek 使用
NPC_ACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "npc_action",
        "description": (
            "最终输出工具（必须调用）。当你完成思考、并在需要时调用其他工具后，"
            "必须调用 npc_action 作为最后一步返回结构化动作；不要只返回自然语言。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["dialogue", "move", "emote", "use_item", "idle"],
                    "description": "动作类型。默认 dialogue；仅在确有必要时使用 move/emote/use_item/idle。",
                },
                "dialogue": {
                    "type": "string",
                    "description": "NPC 对玩家说的台词。必填，简洁自然，符合当前 npc_id 的身份。",
                },
                "emotion": {
                    "type": "string",
                    "description": "情绪/表情标签，可选。例如：友好、严肃、警惕。",
                },
                "target_id": {
                    "type": "string",
                    "description": "动作目标 ID，可选。例如目标 NPC 或任务对象 ID。",
                },
                "extra": {
                    "type": "object",
                    "description": "扩展字段，可选。可放坐标、任务阶段、工具结果摘要等结构化信息。",
                },
            },
            "required": ["dialogue"],
        },
    },
}

RESOLVE_LOCATION_TOOL = {
    "type": "function",
    "function": {
        "name": "resolve_location_coordinates",
        "description": (
            "地点坐标查询工具（本地工具）。当用户询问某地点在哪里、要求具体坐标、"
            "或你的回复涉及移动目的地时，优先调用该工具获取准确坐标后再回答。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "place_name": {
                    "type": "string",
                    "description": "地点名称（必须是单个地点）。示例：村口、商店、铁匠铺、酒馆、广场。",
                },
            },
            "required": ["place_name"],
        },
    },
}


def build_tooling() -> tuple[list[dict[str, Any]], MCPToolClient | None, dict[str, dict[str, Any]]]:
    """
    构建 tools schema，并返回 MCP client（若启用且可用）与 MCP tools 映射。
    重要：不做“本地共享状态工具”的回退，MCP 工具只能通过 MCP 调用。
    """
    tool_defs = [NPC_ACTION_TOOL, RESOLVE_LOCATION_TOOL]
    mcp_client: MCPToolClient | None = None
    mcp_tools_by_name: dict[str, dict[str, Any]] = {}
    if _mcp_enabled():
        try:
            mcp_client = _build_mcp_client()
            for t in mcp_client.list_tools():
                name = t["name"]
                mcp_tools_by_name[name] = t
                raw_desc = (t.get("description") or "").strip()
                if name == "get_npc_runtime_state":
                    desc = (
                        raw_desc
                        or "MCP 状态查询工具。用于获取指定 npc_id 的实时状态：location/job/task/available_actions。"
                    )
                else:
                    desc = raw_desc or "MCP 工具。按参数调用并基于返回结果再决定最终 npc_action。"
                tool_defs.append(
                    {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": desc,
                            "parameters": t.get("input_schema") or {"type": "object"},
                        },
                    }
                )
        except Exception as e:
            logger.warning("MCP list_tools failed, MCP tools disabled for this run: %s", e)
            mcp_client = None
            mcp_tools_by_name = {}
    logger.info(
        "Tooling built. local_tools=%s mcp_tools=%s",
        2,  # npc_action + resolve_location_coordinates
        len(mcp_tools_by_name),
    )
    return tool_defs, mcp_client, mcp_tools_by_name


def llm_step_with_tools(
    messages: list[dict[str, Any]],
    tool_defs: list[dict[str, Any]],
    temperature: float | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """单步调用 LLM：返回一条可直接 append 到 messages 的 assistant message(dict)。"""
    cfg = load_config()
    llm = cfg.get("llm", {})
    model = llm.get("model", "deepseek-chat")
    temp = temperature if temperature is not None else llm.get("temperature", 0.2)
    tout = timeout if timeout is not None else llm.get("timeout_s", 60)

    client = _get_client()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tool_defs,
        temperature=temp,
        timeout=tout,
    )
    choice = resp.choices[0] if resp.choices else None
    if not choice or not choice.message:
        logger.info("LLM step returned empty choice.")
        return {"role": "assistant", "content": ""}

    msg = choice.message
    assistant_tool_calls: list[dict[str, Any]] = []
    if msg.tool_calls:
        for tc in msg.tool_calls:
            fn = getattr(tc, "function", None)
            if not fn:
                continue
            assistant_tool_calls.append(
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": fn.name, "arguments": fn.arguments or "{}"},
                }
            )

    out: dict[str, Any] = {"role": "assistant", "content": (msg.content or "")}
    if assistant_tool_calls:
        out["tool_calls"] = assistant_tool_calls
    logger.info(
        "LLM step response parsed. content_len=%s tool_calls=%s",
        len(out.get("content") or ""),
        len(assistant_tool_calls),
    )
    return out


def parse_tool_args(arguments: str | None) -> dict[str, Any]:
    try:
        return json.loads(arguments or "{}")
    except Exception:
        return {}


def run_tool_call(
    tool_name: str,
    args: dict[str, Any],
    *,
    mcp_client: MCPToolClient | None,
    mcp_tools_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    执行除 npc_action 之外的工具调用，返回可序列化 dict。
    - 本地工具：resolve_location_coordinates
    - MCP 工具：必须来自 mcp_tools_by_name（不做本地回退）
    """
    if tool_name == "resolve_location_coordinates":
        place_name = (args.get("place_name") or "").strip()
        result = resolve_location_coordinates(place_name)
        logger.info("Run local tool: resolve_location_coordinates place=%s", place_name)
        return result or {"error": "unknown place", "place_name": place_name}

    if mcp_client is not None and tool_name in mcp_tools_by_name:
        try:
            logger.info("Run MCP tool: %s", tool_name)
            return mcp_client.call_tool(tool_name, args)
        except Exception as e:
            return {"error": "mcp call failed", "tool_name": tool_name, "detail": str(e)}

    return {"error": "unknown tool", "tool_name": tool_name}

def _mcp_enabled() -> bool:
    cfg = load_config()
    return cfg.get("mcp", {}).get("enabled", True)


def _build_mcp_client() -> MCPToolClient:
    cfg = load_config().get("mcp", {})
    cmd = cfg.get("command")
    args = cfg.get("args")
    return MCPToolClient(command=cmd, args=args)


def _get_client() -> OpenAI:
    cfg = load_config()
    llm = cfg.get("llm", {})
    return OpenAI(
        api_key=llm.get("api_key") or "dummy",
        base_url=llm.get("base_url"),
    )


def call_llm(
    messages: list[dict[str, Any]],
    temperature: float | None = None,
    timeout: int | None = None,
) -> str:
    """请求 LLM 并返回 assistant 的 content 文本（无 tools 时使用）。"""
    cfg = load_config()
    llm = cfg.get("llm", {})
    model = llm.get("model", "deepseek-chat")
    temp = temperature if temperature is not None else llm.get("temperature", 0.2)
    tout = timeout if timeout is not None else llm.get("timeout_s", 60)

    client = _get_client()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temp,
        timeout=tout,
    )
    choice = resp.choices[0] if resp.choices else None
    if not choice or not choice.message:
        return ""
    return (choice.message.content or "").strip()


def classify_and_prepare_dialogue_memory(
    *,
    player_message: str,
    npc_dialogue: str,
    scene_info: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """
    使用 LLM 对对话记忆进行分层：
    - important: 原文保留
    - daily: 返回压缩总结文本
    返回 (dialogue_tier, processed_text)。
    """
    scene_text = json.dumps(scene_info or {}, ensure_ascii=False)
    raw_text = f"玩家说：{player_message}；NPC 回复：{npc_dialogue}"
    if scene_info:
        raw_text = f"[场景 {scene_text}] " + raw_text

    system_prompt = (
        "你是 NPC 长期记忆分层器。"
        "你只能返回 JSON，不要输出任何额外解释。\n"
        "返回格式必须是："
        '{"dialogue_tier":"daily|important","processed_text":"..."}。\n'
        "规则：\n"
        "1) important：玩家提供了需要长期准确保留的关键信息（身份、关系、偏好、承诺、约定、任务关键事实等）。\n"
        "2) daily：普通闲聊或低价值信息，需压缩为 1-3 句摘要。\n"
        "3) 若为 important，processed_text 必须保持原文，不允许改写。\n"
        "4) 若为 daily，processed_text 应简洁、可检索、保留核心语义。"
    )
    user_prompt = (
        f"scene_info={scene_text}\n"
        f"player_message={player_message}\n"
        f"npc_dialogue={npc_dialogue}\n"
        "请输出 JSON。"
    )
    logger.info(
        "Classify memory request. player_message_len=%s npc_dialogue_len=%s player_message=%s npc_dialogue=%s",
        len(player_message or ""),
        len(npc_dialogue or ""),
        _preview(player_message or ""),
        _preview(npc_dialogue or ""),
    )

    try:
        content = call_llm(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        data = json.loads(content)
        tier = (data.get("dialogue_tier") or "").strip()
        processed = (data.get("processed_text") or "").strip()
        if tier not in {"daily", "important"}:
            raise ValueError("invalid dialogue_tier")
        if not processed:
            raise ValueError("empty processed_text")
        if tier == "important":
            logger.info(
                "Classify memory result. tier=important output_len=%s output=%s",
                len(raw_text),
                _preview(raw_text, limit=500),
            )
            return tier, raw_text
        logger.info(
            "Classify memory result. tier=daily output_len=%s output=%s",
            len(processed),
            _preview(processed, limit=500),
        )
        return tier, processed
    except Exception as e:
        logger.warning("Dialogue memory classify failed. Fallback to important. detail=%s", e)
        logger.info(
            "Classify memory fallback output. tier=important output_len=%s output=%s",
            len(raw_text),
            _preview(raw_text, limit=500),
        )
        return "important", raw_text


def _action_from_args(args: dict[str, Any]) -> ActionResponse:
    """将 npc_action tool arguments 映射为标准 ActionResponse。"""
    dialogue = args.get("dialogue", "")
    action_type = args.get("action_type", "dialogue")
    emotion = args.get("emotion")
    target_id = args.get("target_id")
    extra = args.get("extra")
    return ActionResponse(
        action_type=action_type,
        dialogue=dialogue or "...",
        emotion=emotion,
        target_id=target_id,
        extra=extra,
    )


def reply_to_action(dialogue: str) -> ActionResponse:
    """将纯对话文本封装为 ActionResponse（兜底用）"""
    return ActionResponse(
        action_type="dialogue",
        dialogue=dialogue or "...",
        emotion=None,
        target_id=None,
        extra=None,
    )
