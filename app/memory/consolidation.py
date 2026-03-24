""" 记忆沉淀：将本轮对话摘要写入长期记忆（ChromaDB） """
import logging
from typing import Any

from app.config import load_config
from app.memory.long_term import LongTermMemory
from app.reasoning.llm import call_llm

logger = logging.getLogger(__name__)

_long_term: LongTermMemory | None = None


def _get_long_term() -> LongTermMemory:
    global _long_term
    if _long_term is None:
        _long_term = LongTermMemory()
    return _long_term


def consolidate_turn(
    player_id: str,
    npc_id: str | None,
    user_message: str,
    assistant_message: str,
    scene_info: dict[str, Any] | None = None,
) -> None:
    """
    本轮交互完成后，将对话摘要写入该玩家的长期记忆，供后续 RAG 检索。
    当前实现：简单拼接存储；可选改为调用 LLM 做摘要再存。
    """
    if not player_id:
        return
    try:
        store = _get_long_term()
        scene = (scene_info or {})
        text = f"玩家说：{user_message}；NPC 回复：{assistant_message}"
        if scene:
            text = f"[场景 {scene}] " + text
        store.add_documents(
            texts=[text],
            metadatas=[{"player_id": player_id, "npc_id": npc_id, "type": "interaction"}],
            ids=None,
        )
    except Exception as e:
        logger.warning("Consolidation failed: %s", e)
