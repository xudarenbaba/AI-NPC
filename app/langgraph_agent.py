"""LangGraph 编排（规范版）：RAG(Chroma) -> Prompt -> (agent <-> tools 循环) -> 更新短期记忆。"""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.config import load_config
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory
from app.reasoning.llm import (
    build_tooling,
    classify_and_prepare_dialogue_memory,
    llm_step_with_tools,
    parse_tool_args,
    reply_to_action,
    run_tool_call,
)
from app.reasoning.prompts import build_messages
from app.schemas.response import ActionResponse

logger = logging.getLogger(__name__)


def _preview(text: str, limit: int = 300) -> str:
    t = (text or "").replace("\n", "\\n")
    return t if len(t) <= limit else t[:limit] + "..."


class AgentState(TypedDict, total=False):
    request_id: str
    player_id: str
    npc_id: str | None
    message: str
    scene_info: dict[str, Any]

    short_term_history: list[dict[str, Any]]
    world_chunks: list[str]
    persona_chunks: list[str]
    dialogue_daily_chunks: list[str]
    dialogue_important_chunks: list[str]
    messages: list[dict[str, Any]]
    action: ActionResponse

    tool_defs: list[dict[str, Any]]
    # MCP tooling（不共享本地调用，只有 MCP call_tool）
    mcp_tools_by_name: dict[str, dict[str, Any]]
    # MCP client 对象放 state 里只为本次 invoke 使用（不序列化）
    mcp_client: Any


def persist_long_term_dialogue_memory(
    *,
    player_id: str,
    npc_id: str | None,
    message: str,
    npc_dialogue: str,
    scene_info: dict[str, Any] | None,
    request_id: str | None = None,
) -> None:
    """后台任务：分层 + 写入长期记忆。"""
    logger.info(
        "Long-term memory task started. rid=%s player_id=%s npc_id=%s player_message_len=%s npc_dialogue_len=%s",
        request_id,
        player_id,
        npc_id,
        len(message or ""),
        len(npc_dialogue or ""),
    )
    cfg = load_config()
    if not cfg.get("use_consolidation", True):
        logger.info("Skip long-term write: rid=%s consolidation disabled.", request_id)
        return
    if not player_id:
        logger.info("Skip long-term write: rid=%s empty player_id.", request_id)
        return

    min_chars = int(cfg.get("memory", {}).get("dialogue_store_min_chars", 0))
    if len((npc_dialogue or "").strip()) < min_chars:
        logger.info("Skip long-term write: rid=%s dialogue too short. min=%s", request_id, min_chars)
        return

    dialogue_tier, processed_text = classify_and_prepare_dialogue_memory(
        player_message=message,
        npc_dialogue=npc_dialogue,
        scene_info=scene_info or {},
        request_id=request_id,
    )
    logger.info(
        "Long-term memory classified. rid=%s player_id=%s npc_id=%s tier=%s processed_len=%s processed_text=%s",
        request_id,
        player_id,
        npc_id,
        dialogue_tier,
        len(processed_text or ""),
        _preview(processed_text or "", limit=500),
    )
    LongTermMemory().add_dialogue(
        npc_id=npc_id,
        player_id=player_id,
        texts=[processed_text],
        dialogue_tier=dialogue_tier,
        scene_info=scene_info or {},
        request_id=request_id,
    )
    logger.info(
        "Long-term memory stored. rid=%s player_id=%s npc_id=%s tier=%s text=%s",
        request_id,
        player_id,
        npc_id,
        dialogue_tier,
        _preview(processed_text or "", limit=500),
    )


def build_agent_graph():
    """创建并返回已编译的 LangGraph 图（一次构建，多次 invoke）。"""
    short_term = ShortTermMemory()
    long_term = LongTermMemory()

    def retrieve(state: AgentState) -> AgentState:
        request_id = state.get("request_id")
        cfg = load_config()
        if not cfg.get("use_rag", True):
            state["world_chunks"] = []
            state["persona_chunks"] = []
            state["dialogue_daily_chunks"] = []
            state["dialogue_important_chunks"] = []
            logger.info("RAG disabled by config. rid=%s", request_id)
            return state

        player_id = state.get("player_id") or ""
        npc_id = state.get("npc_id")
        message = state.get("message") or ""
        scene_info = state.get("scene_info") or {}

        # 把 npc_id / player_id / scene / message 拼到检索 query 里
        parts: list[str] = []
        if npc_id:
            parts.append(f"npc_id:{npc_id}")
        parts.append(f"player:{player_id}")
        parts.append(f"message:{message}")
        query = "\n".join(parts)
        if scene_info:
            query = f"scene:{scene_info}\n" + query

        world_chunks = long_term.search_world(query)
        persona_chunks = long_term.search_persona(query, npc_id)
        dialogue_daily_chunks = long_term.search_dialogue_daily(query, npc_id, player_id)
        dialogue_important_chunks = long_term.search_dialogue_important(query, npc_id, player_id)

        state["world_chunks"] = world_chunks or []
        state["persona_chunks"] = persona_chunks or []
        state["dialogue_daily_chunks"] = dialogue_daily_chunks or []
        state["dialogue_important_chunks"] = dialogue_important_chunks or []
        logger.info(
            "RAG retrieve done. rid=%s player_id=%s npc_id=%s world=%s persona=%s dialogue_daily=%s dialogue_important=%s",
            request_id,
            player_id,
            npc_id,
            len(state["world_chunks"]),
            len(state["persona_chunks"]),
            len(state["dialogue_daily_chunks"]),
            len(state["dialogue_important_chunks"]),
        )
        return state

    def get_short_term_history(state: AgentState) -> AgentState:
        request_id = state.get("request_id")
        player_id = state.get("player_id") or ""
        npc_id = state.get("npc_id")
        state["short_term_history"] = short_term.get_recent(player_id, npc_id=npc_id)
        logger.info(
            "Short-term history loaded. rid=%s player_id=%s npc_id=%s turns=%s",
            request_id,
            player_id,
            npc_id,
            len(state["short_term_history"]),
        )
        return state

    def build_prompt(state: AgentState) -> AgentState:
        request_id = state.get("request_id")
        state["messages"] = build_messages(
            player_message=state.get("message") or "",
            npc_id=state.get("npc_id"),
            scene_info=state.get("scene_info") or {},
            short_term_history=state.get("short_term_history") or None,
            world_chunks=state.get("world_chunks") or None,
            persona_chunks=state.get("persona_chunks") or None,
            dialogue_daily_chunks=state.get("dialogue_daily_chunks") or None,
            dialogue_important_chunks=state.get("dialogue_important_chunks") or None,
        )
        logger.info("Prompt built. rid=%s messages=%s", request_id, len(state["messages"]))
        return state

    def prepare_tools(state: AgentState) -> AgentState:
        request_id = state.get("request_id")
        tool_defs, mcp_client, mcp_tools_by_name = build_tooling()
        state["tool_defs"] = tool_defs
        state["mcp_client"] = mcp_client
        state["mcp_tools_by_name"] = mcp_tools_by_name
        logger.info(
            "Tooling prepared. rid=%s total_tools=%s mcp_tools=%s",
            request_id,
            len(tool_defs),
            len(mcp_tools_by_name),
        )
        return state

    def agent(state: AgentState) -> AgentState:
        request_id = state.get("request_id")
        messages = state.get("messages") or []
        tool_defs = state.get("tool_defs") or []
        assistant_msg = llm_step_with_tools(messages, tool_defs, request_id=request_id)
        messages = list(messages) + [assistant_msg]
        state["messages"] = messages

        # 若模型没走 tools，直接返回文本时兜底为 ActionResponse
        tool_calls = assistant_msg.get("tool_calls") or []
        logger.info("LLM step finished. rid=%s tool_calls=%s", request_id, len(tool_calls))
        if not tool_calls:
            content = (assistant_msg.get("content") or "").strip()
            if content:
                state["action"] = reply_to_action(content)
                logger.info(
                    "LLM produced direct action fallback. rid=%s dialogue=%s",
                    request_id,
                    _preview(content),
                )
        return state

    def tools(state: AgentState) -> AgentState:
        request_id = state.get("request_id")
        messages = state.get("messages") or []
        if not messages:
            return state
        last = messages[-1] or {}
        tool_calls = last.get("tool_calls") or []
        if not tool_calls:
            return state

        mcp_client = state.get("mcp_client")
        mcp_tools_by_name = state.get("mcp_tools_by_name") or {}

        new_messages = list(messages)
        for tc in tool_calls:
            fn = (tc or {}).get("function") or {}
            tool_name = fn.get("name") or ""
            args = parse_tool_args(fn.get("arguments"))

            def _tool_result_with_template(t_name: str, result: dict[str, Any]) -> str:
                """把工具返回值用解释模板包起来，降低模型误读概率。"""
                raw_json = json.dumps(result, ensure_ascii=False)
                if t_name == "resolve_location_coordinates":
                    guide = (
                        "解释规则：请直接使用 result.x/result.y/result.z 作为坐标；"
                        "result.place_name 只用于确认地点名是否匹配。"
                    )
                elif t_name == "get_npc_runtime_state":
                    guide = (
                        "解释规则：请直接使用 result.location.x/result.location.y/result.location.z 作为坐标；"
                        "result.job 表示职业，result.task 表示当前任务，available_actions 表示可行动作集合。"
                    )
                else:
                    guide = (
                        "解释规则：result 为该工具返回的结构化数据。优先使用字段含义明确的值，"
                        "必要时把信息提取为可用于对话/行动的摘要。"
                    )
                return (
                    f"TOOL_NAME={t_name}\n"
                    f"RAW_RESULT_JSON={raw_json}\n"
                    f"RESULT_EXPLANATION_TEMPLATE={guide}"
                )

            # npc_action 是“格式指定工具”：解析为最终 ActionResponse，并终止循环
            if tool_name == "npc_action":
                dialogue = args.get("dialogue", "")
                action_type = args.get("action_type", "dialogue")
                emotion = args.get("emotion")
                target_id = args.get("target_id")
                extra = args.get("extra")
                state["action"] = ActionResponse(
                    action_type=action_type,
                    dialogue=dialogue or "...",
                    emotion=emotion,
                    target_id=target_id,
                    extra=extra,
                )
                logger.info(
                    "npc_action parsed. rid=%s action_type=%s dialogue=%s",
                    request_id,
                    action_type,
                    _preview(dialogue),
                )
                continue

            tool_result = run_tool_call(
                tool_name,
                args,
                mcp_client=mcp_client,
                mcp_tools_by_name=mcp_tools_by_name,
            )
            new_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "name": tool_name,
                    "content": _tool_result_with_template(tool_name, tool_result),
                }
            )
            logger.info("Tool result appended. rid=%s tool_name=%s", request_id, tool_name)
        state["messages"] = new_messages
        return state

    def route_from_agent(state: AgentState):
        # 有最终 action：更新短期记忆并结束
        if state.get("action") is not None:
            return "update_short_term"
        # 有 tool_calls：继续执行工具并回到 agent
        messages = state.get("messages") or []
        if messages and (messages[-1] or {}).get("tool_calls"):
            return "tools"
        # 正常情况下不会走到这里（agent 已兜底 action），但为了安全：结束图运行
        return END

    def route_from_tools(state: AgentState):
        # tools 节点若已产生最终 action，则更新短期记忆
        if state.get("action") is not None:
            return "update_short_term"
        return "agent"

    def update_short_term(state: AgentState) -> AgentState:
        request_id = state.get("request_id")
        player_id = state.get("player_id") or ""
        npc_id = state.get("npc_id")
        message = state.get("message") or ""
        action = state.get("action")
        if not player_id or not action:
            return state

        # 写入短期对话：先用户，再 NPC（保持与原始逻辑一致）
        short_term.add_turn(player_id, "user", message, npc_id)
        short_term.add_turn(player_id, "assistant", action.dialogue, npc_id)
        logger.info("Short-term memory updated. rid=%s player_id=%s npc_id=%s", request_id, player_id, npc_id)
        return state

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("retrieve", retrieve)
    graph_builder.add_node("get_short_term_history", get_short_term_history)
    graph_builder.add_node("build_prompt", build_prompt)
    graph_builder.add_node("prepare_tools", prepare_tools)
    graph_builder.add_node("agent", agent)
    graph_builder.add_node("tools", tools)
    graph_builder.add_node("update_short_term", update_short_term)

    graph_builder.set_entry_point("retrieve")
    graph_builder.add_edge("retrieve", "get_short_term_history")
    graph_builder.add_edge("get_short_term_history", "build_prompt")
    graph_builder.add_edge("build_prompt", "prepare_tools")
    graph_builder.add_edge("prepare_tools", "agent")
    graph_builder.add_conditional_edges("agent", route_from_agent)
    graph_builder.add_conditional_edges("tools", route_from_tools)
    graph_builder.add_edge("update_short_term", END)

    return graph_builder.compile()

