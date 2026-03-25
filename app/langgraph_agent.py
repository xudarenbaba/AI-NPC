"""LangGraph 编排：RAG(Chroma) -> Prompt -> LLM tools -> 写回 Chroma。"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.config import load_config
from app.memory.long_term import LongTermMemory
from app.reasoning.llm import call_llm_with_tools, reply_to_action
from app.reasoning.prompts import build_messages
from app.schemas.response import ActionResponse


class AgentState(TypedDict, total=False):
    player_id: str
    npc_id: str | None
    message: str
    scene_info: dict[str, Any]

    long_term_chunks: list[str]
    messages: list[dict[str, Any]]
    action: ActionResponse


def build_agent_graph():
    """创建并返回已编译的 LangGraph 图（一次构建，多次 invoke）。"""
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

    def build_prompt(state: AgentState) -> AgentState:
        short_term_history = None  # 新链路只保留“单一RAG链路”
        state["messages"] = build_messages(
            player_message=state.get("message") or "",
            npc_id=state.get("npc_id"),
            scene_info=state.get("scene_info") or {},
            short_term_history=short_term_history,
            long_term_chunks=state.get("long_term_chunks") or None,
        )
        return state

    def run_llm(state: AgentState) -> AgentState:
        action = call_llm_with_tools(state.get("messages") or [])
        if action is None:
            action = reply_to_action("（思考中……）")
        state["action"] = action
        return state

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

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("retrieve", retrieve)
    graph_builder.add_node("build_prompt", build_prompt)
    graph_builder.add_node("run_llm", run_llm)
    graph_builder.add_node("store_memory", store_memory)

    graph_builder.set_entry_point("retrieve")
    graph_builder.add_edge("retrieve", "build_prompt")
    graph_builder.add_edge("build_prompt", "run_llm")
    graph_builder.add_edge("run_llm", "store_memory")
    graph_builder.add_edge("store_memory", END)

    return graph_builder.compile()

