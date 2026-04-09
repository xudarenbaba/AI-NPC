"""知识图谱检索与事实格式化。"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.config import load_config
from app.knowledge_graph.client import fetch_neighbors, fetch_seed_entities

logger = logging.getLogger(__name__)


def _split_tokens(text: str) -> list[str]:
    # 提取中英文/数字词元，过滤太短 token
    raw = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", text or "")
    out: list[str] = []
    for t in raw:
        token = t.strip()
        if len(token) < 2:
            continue
        if token not in out:
            out.append(token)
    return out


def _build_ranked_facts(rows: list[dict[str, Any]], *, max_facts: int) -> list[str]:
    seen: set[tuple[str, str, str]] = set()
    items: list[tuple[float, str]] = []
    for r in rows:
        head = (r.get("head_name") or "").strip()
        rel = (r.get("relation") or "").strip()
        tail = (r.get("tail_name") or "").strip()
        if not head or not rel or not tail:
            continue
        key = (head, rel, tail)
        if key in seen:
            continue
        seen.add(key)
        conf = float(r.get("confidence") or 0.0)
        # 核心关系加权，保证更有用事实优先
        if rel in {"HAS_ROLE", "LOCATED_IN", "HAS_TASK", "AFFILIATED_WITH"}:
            conf += 0.6
        fact = f"{head} {rel} {tail}"
        items.append((conf, fact))
    items.sort(key=lambda x: x[0], reverse=True)
    return [t[1] for t in items[:max_facts]]


def retrieve_kg_facts(
    *,
    message: str,
    npc_id: str | None,
    request_id: str | None = None,
) -> tuple[list[str], list[str]]:
    cfg = load_config().get("knowledge_graph", {})
    if not cfg.get("enabled", True):
        logger.info("KG disabled by config. rid=%s", request_id)
        return [], []

    ret_cfg: dict[str, Any] = cfg.get("retrieval", {})
    max_entities = int(ret_cfg.get("max_entities", 6))
    max_facts = int(ret_cfg.get("max_facts", 8))
    edge_limit = int(ret_cfg.get("edge_limit", 80))

    tokens = _split_tokens(message)
    if npc_id:
        tokens.append(npc_id)
    # 保序去重
    dedup_tokens: list[str] = []
    for t in tokens:
        if t not in dedup_tokens:
            dedup_tokens.append(t)

    logger.info("KG query tokens. rid=%s tokens=%s", request_id, dedup_tokens)
    try:
        seeds = fetch_seed_entities(dedup_tokens, limit=max_entities)
        entity_ids = [str(x.get("id")) for x in seeds if x.get("id")]
        entity_names = [str(x.get("name")) for x in seeds if x.get("name")]
        logger.info(
            "KG seed entities matched. rid=%s count=%s entities=%s",
            request_id,
            len(entity_ids),
            entity_names,
        )
        rows = fetch_neighbors(entity_ids, limit=edge_limit)
        facts = _build_ranked_facts(rows, max_facts=max_facts)
        logger.info("KG facts retrieved. rid=%s count=%s facts=%s", request_id, len(facts), facts)
        return facts, entity_names
    except Exception as e:
        logger.warning("KG retrieve failed. rid=%s detail=%s", request_id, e)
        return [], []

