""" 大模型调用（OpenAI 兼容 / DeepSeek），支持 Function Calling """
import json
import logging
from typing import Any

from openai import OpenAI

from app.config import load_config
from app.integrations.mcp_client import MCPToolClient
from app.schemas.response import ActionResponse
from app.tools.location_tools import resolve_location_coordinates
from app.tools.npc_state_tools import get_npc_runtime_state_local

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

GET_NPC_RUNTIME_STATE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_npc_runtime_state",
        "description": "获取 NPC 当前坐标、职业、任务、可行动作。",
        "parameters": {
            "type": "object",
            "properties": {
                "npc_id": {"type": "string", "description": "NPC 唯一标识"},
            },
            "required": ["npc_id"],
        },
    },
}


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


def call_llm_with_tools(
    messages: list[dict[str, Any]],
    temperature: float | None = None,
    timeout: int | None = None,
) -> ActionResponse | None:
    """
    使用 Function Calling 请求 LLM，解析 npc_action 调用结果为 ActionResponse。
    若未返回合法 tool_call 则返回 None，由调用方兜底。
    """
    cfg = load_config()
    llm = cfg.get("llm", {})
    model = llm.get("model", "deepseek-chat")
    temp = temperature if temperature is not None else llm.get("temperature", 0.2)
    tout = timeout if timeout is not None else llm.get("timeout_s", 60)

    client = _get_client()
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
            logger.warning("MCP list_tools failed, fallback to local tools only: %s", e)
            mcp_client = None
    if mcp_client is None:
        # MCP 不可用时退回本地状态工具，保证功能不中断
        tool_defs.append(GET_NPC_RUNTIME_STATE_TOOL)

    working_messages = list(messages)

    for _ in range(4):
        resp = client.chat.completions.create(
            model=model,
            messages=working_messages,
            tools=tool_defs,
            temperature=temp,
            timeout=tout,
        )
        choice = resp.choices[0] if resp.choices else None
        if not choice or not choice.message:
            return None
        msg = choice.message

        # 模型直接返回文本（未使用工具）时兜底
        if not msg.tool_calls:
            if msg.content:
                return reply_to_action(msg.content.strip())
            return None

        assistant_tool_calls = []
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
        working_messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": assistant_tool_calls,
            }
        )

        for tc in msg.tool_calls:
            fn = getattr(tc, "function", None)
            if not fn:
                continue
            tool_name = fn.name
            try:
                args = json.loads(fn.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if tool_name == "npc_action":
                return _action_from_args(args)

            if tool_name == "resolve_location_coordinates":
                place_name = (args.get("place_name") or "").strip()
                result = resolve_location_coordinates(place_name)
                tool_result = result or {"error": "unknown place", "place_name": place_name}
            elif tool_name == "get_npc_runtime_state":
                npc_id = args.get("npc_id") or ""
                tool_result = get_npc_runtime_state_local(npc_id)
            elif mcp_client is not None and tool_name in mcp_tools_by_name:
                try:
                    tool_result = mcp_client.call_tool(tool_name, args)
                except Exception as e:
                    tool_result = {"error": "mcp call failed", "tool_name": tool_name, "detail": str(e)}
            else:
                tool_result = {"error": "unknown tool", "tool_name": tool_name}

            working_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )
    return None


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
