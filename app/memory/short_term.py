""" 短期记忆：按玩家维护最近 N 轮对话 """
from collections import deque
from typing import Any

from app.config import load_config


class ShortTermMemory:
    """进程内短期对话历史，按 (player_id, npc_id) 分桶"""

    def __init__(self, max_turns: int | None = None):
        cfg = load_config()
        mem = cfg.get("memory", {})
        self._max_turns = max_turns or mem.get("short_term_turns", 10)
        self._buckets: dict[str, deque[dict[str, Any]]] = {}

    def _key(self, player_id: str, npc_id: str | None) -> str:
        return f"{player_id}:{npc_id or 'default'}"

    def add_turn(self, player_id: str, role: str, content: str, npc_id: str | None = None) -> None:
        """追加一轮对话。role 为 'user' 或 'assistant'。"""
        k = self._key(player_id, npc_id)
        if k not in self._buckets:
            self._buckets[k] = deque(maxlen=self._max_turns * 2)
        self._buckets[k].append({"role": role, "content": content})

    def get_recent(
        self,
        player_id: str,
        n: int | None = None,
        npc_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """获取该玩家最近 n 轮（每轮含 user + assistant 各一条），默认全部。"""
        k = self._key(player_id, npc_id)
        if k not in self._buckets:
            return []
        items = list(self._buckets[k])
        if n is not None and n > 0:
            # 保留最后 n*2 条（n 轮）
            items = items[-(n * 2) :]
        return items

    def clear(self, player_id: str, npc_id: str | None = None) -> None:
        """清空该玩家的短期记忆"""
        k = self._key(player_id, npc_id)
        self._buckets.pop(k, None)
