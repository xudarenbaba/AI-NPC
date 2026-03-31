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

# 与 ActionResponse 对应的 Function Calling schema，供 DeepSeek 使用
NPC_ACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "npc_action",
        "description": "输出 NPC 对玩家的动作与台词，游戏引擎将据此执行表现",
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["dialogue", "move", "emote", "use_item", "idle"],
                    "description": "动作类型",
                },
                "dialogue": {
                    "type": "string",
                    "description": "NPC 对玩家说的台词",
                },
                "emotion": {
                    "type": "string",
                    "description": "情绪/表情标签，可选",
                },
                "target_id": {
                    "type": "string",
                    "description": "动作目标 ID，可选",
                },
                "extra": {
                    "type": "object",
                    "description": "扩展字段，可选",
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
        "description": "把地点自然语言名称解析为坐标。",
        "parameters": {
            "type": "object",
            "properties": {
                "place_name": {"type": "string", "description": "地点名词，如 商店、酒馆"},
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
                tool_defs.append(
                    {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": t.get("description", ""),
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
