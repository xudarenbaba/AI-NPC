"""LangGraph 编排（规范版）：RAG(Chroma) -> Prompt -> (agent <-> tools 循环) -> 写回 Chroma。"""

from __future__ import annotations

import json
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.config import load_config
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory
from app.reasoning.llm import (
    build_tooling,
    llm_step_with_tools,
    parse_tool_args,
    reply_to_action,
    run_tool_call,
)
from app.reasoning.prompts import build_messages
from app.schemas.response import ActionResponse


class AgentState(TypedDict, total=False):
    player_id: str
    npc_id: str | None
    message: str
    scene_info: dict[str, Any]

    short_term_history: list[dict[str, Any]]
    long_term_chunks: list[str]
    messages: list[dict[str, Any]]
    action: ActionResponse

    tool_defs: list[dict[str, Any]]
    # MCP tooling（不共享本地调用，只有 MCP call_tool）
    mcp_tools_by_name: dict[str, dict[str, Any]]
    # MCP client 对象放 state 里只为本次 invoke 使用（不序列化）
    mcp_client: Any


def build_agent_graph():
    """创建并返回已编译的 LangGraph 图（一次构建，多次 invoke）。"""
    short_term = ShortTermMemory()
    long_term = LongTermMemory()

    def retrieve(state: AgentState) -> AgentState:
        cfg = load_config()
        if not cfg.get("use_rag", True):
            state["long_term_chunks"] = []
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

        chunks = long_term.search(
            query,
            filter_by_player=player_id,
            filter_by_npc=npc_id,
            include_lore=True,
        )
        state["long_term_chunks"] = chunks or []
        return state

    def get_short_term_history(state: AgentState) -> AgentState:
        player_id = state.get("player_id") or ""
        npc_id = state.get("npc_id")
        state["short_term_history"] = short_term.get_recent(player_id, npc_id=npc_id)
        return state

    def build_prompt(state: AgentState) -> AgentState:
        state["messages"] = build_messages(
            player_message=state.get("message") or "",
            npc_id=state.get("npc_id"),
            scene_info=state.get("scene_info") or {},
            short_term_history=state.get("short_term_history") or None,
            long_term_chunks=state.get("long_term_chunks") or None,
        )
        return state

    def prepare_tools(state: AgentState) -> AgentState:
        tool_defs, mcp_client, mcp_tools_by_name = build_tooling()
        state["tool_defs"] = tool_defs
        state["mcp_client"] = mcp_client
        state["mcp_tools_by_name"] = mcp_tools_by_name
        return state

    def agent(state: AgentState) -> AgentState:
        messages = state.get("messages") or []
        tool_defs = state.get("tool_defs") or []
        assistant_msg = llm_step_with_tools(messages, tool_defs)
        messages = list(messages) + [assistant_msg]
        state["messages"] = messages

        # 若模型没走 tools，直接返回文本时兜底为 ActionResponse
        tool_calls = assistant_msg.get("tool_calls") or []
        if not tool_calls:
            content = (assistant_msg.get("content") or "").strip()
            if content:
                state["action"] = reply_to_action(content)
        return state

    def tools(state: AgentState) -> AgentState:
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
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )
        state["messages"] = new_messages
        return state

    def route_from_agent(state: AgentState):
        # 有最终 action：直接写回记忆并结束
        if state.get("action") is not None:
            return "store_memory"
        # 有 tool_calls：继续执行工具并回到 agent
        messages = state.get("messages") or []
        if messages and (messages[-1] or {}).get("tool_calls"):
            return "tools"
        # 正常情况下不会走到这里（agent 已兜底 action），但为了安全：结束图运行
        return END

    def route_from_tools(state: AgentState):
        # tools 节点若已产生最终 action，则进入写回
        if state.get("action") is not None:
            return "store_memory"
        return "agent"

    def store_memory(state: AgentState) -> AgentState:
        # 把本轮交互写入 ChromaDB（让下一轮能被 RAG 检索到）
        if not load_config().get("use_consolidation", True):
            return state

        player_id = state.get("player_id") or ""
        npc_id = state.get("npc_id")
        message = state.get("message") or ""
        scene_info = state.get("scene_info") or {}
        action = state.get("action")
        if not player_id or not action:
            return state

        text = f"玩家说：{message}；NPC 回复：{action.dialogue}"
        if scene_info:
            text = f"[场景 {scene_info}] " + text

        long_term.add_documents(
            texts=[text],
            metadatas=[{"player_id": player_id, "npc_id": npc_id, "type": "interaction"}],
        )
        return state

    def update_short_term(state: AgentState) -> AgentState:
        player_id = state.get("player_id") or ""
        npc_id = state.get("npc_id")
        message = state.get("message") or ""
        action = state.get("action")
        if not player_id or not action:
            return state

        # 写入短期对话：先用户，再 NPC（保持与原始逻辑一致）
        short_term.add_turn(player_id, "user", message, npc_id)
        short_term.add_turn(player_id, "assistant", action.dialogue, npc_id)
        return state

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("retrieve", retrieve)
    graph_builder.add_node("get_short_term_history", get_short_term_history)
    graph_builder.add_node("build_prompt", build_prompt)
    graph_builder.add_node("prepare_tools", prepare_tools)
    graph_builder.add_node("agent", agent)
    graph_builder.add_node("tools", tools)
    graph_builder.add_node("store_memory", store_memory)
    graph_builder.add_node("update_short_term", update_short_term)

    graph_builder.set_entry_point("retrieve")
    graph_builder.add_edge("retrieve", "get_short_term_history")
    graph_builder.add_edge("get_short_term_history", "build_prompt")
    graph_builder.add_edge("build_prompt", "prepare_tools")
    graph_builder.add_edge("prepare_tools", "agent")
    graph_builder.add_conditional_edges("agent", route_from_agent)
    graph_builder.add_conditional_edges("tools", route_from_tools)
    graph_builder.add_edge("store_memory", "update_short_term")
    graph_builder.add_edge("update_short_term", END)

    return graph_builder.compile()

