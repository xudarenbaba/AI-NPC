"""知识图谱检索与事实格式化。"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.config import load_config
from app.knowledge_graph.client import fetch_neighbors, fetch_seed_entities_by_specs
from app.knowledge_graph.schema import ALLOWED_LABELS, ALLOWED_RELATIONS, normalize_name
from app.reasoning.llm import call_llm

logger = logging.getLogger(__name__)


def _labels_enum_text() -> str:
    return "|".join(sorted(ALLOWED_LABELS))


def _relations_enum_text() -> str:
    return "|".join(sorted(ALLOWED_RELATIONS))


def _parse_query_with_llm(*, message: str, npc_id: str | None, request_id: str | None) -> tuple[list[dict[str, str]], list[str]]:
    labels_text = _labels_enum_text()
    relations_text = _relations_enum_text()
    system_prompt = (
        "你是知识图谱查询解析器。"
        "你必须只返回 JSON，不允许输出额外文本。\n"
        "JSON 格式："
        + '{"entities":[{"name":"...","label":"'
        + labels_text
        + '"}],'
        + '"relations":["'
        + relations_text
        + '"]}\n'
        "要求：\n"
        "1) entities 只保留和问题强相关的实体，最多 6 个。\n"
        "2) label 必须使用枚举值。\n"
        "3) relations 可为空数组。"
    )
    user_prompt = (
        f"npc_id={npc_id or ''}\n"
        f"user_message={message}\n"
        "请输出 JSON。"
    )
    content = call_llm(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    try:
        data = json.loads(content)
    except Exception as e:
        raise ValueError(f"parse query json failed: {e}")
    entities_raw = data.get("entities") or []
    relations_raw = data.get("relations") or []
    entities: list[dict[str, str]] = []
    for x in entities_raw:
        name = normalize_name(str((x or {}).get("name") or ""))
        label = str((x or {}).get("label") or "").strip()
        if not name or label not in ALLOWED_LABELS:
            continue
        entities.append({"name": name, "label": label})
    relations = [r for r in [str(v).strip() for v in relations_raw] if r in ALLOWED_RELATIONS]
    logger.info(
        "KG query parsed by LLM. rid=%s entities=%s relations=%s",
        request_id,
        entities,
        relations,
    )
    return entities[:6], relations[:10]


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
    try:
        entity_specs, rel_filters = _parse_query_with_llm(
            message=message,
            npc_id=npc_id,
            request_id=request_id,
        )
        if not entity_specs:
            logger.info("KG query parsed empty entities. rid=%s", request_id)
            return [], []
        seeds = fetch_seed_entities_by_specs(entity_specs, limit_per_label=max_entities)
        entity_ids = [str(x.get("id")) for x in seeds if x.get("id")]
        entity_names = [f"{x.get('name')}({x.get('label')})" for x in seeds if x.get("name")]
        logger.info(
            "KG seed entities matched. rid=%s count=%s entities=%s",
            request_id,
            len(entity_ids),
            entity_names,
        )
        rows = fetch_neighbors(entity_ids, limit=edge_limit, relations=rel_filters)
        logger.info("KG neighbor edges fetched. rid=%s rows=%s", request_id, len(rows))
        facts = _build_ranked_facts(rows, max_facts=max_facts)
        logger.info("KG facts retrieved. rid=%s count=%s facts=%s", request_id, len(facts), facts)
        return facts, entity_names
    except Exception as e:
        logger.warning("KG retrieve failed. rid=%s detail=%s", request_id, e)
        return [], []

