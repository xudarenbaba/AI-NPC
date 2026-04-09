"""Neo4j 客户端封装（Label 化实体查询）。"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from neo4j import GraphDatabase

from app.config import load_config
from app.knowledge_graph.schema import ALLOWED_LABELS, ALLOWED_RELATIONS


def _kg_cfg() -> dict[str, Any]:
    cfg = load_config().get("knowledge_graph", {})
    return cfg.get("neo4j", {})


@lru_cache(maxsize=1)
def get_driver():
    neo = _kg_cfg()
    uri = neo.get("uri", "neo4j://127.0.0.1:7687")
    user = neo.get("user", "neo4j")
    password = neo.get("password", "")
    return GraphDatabase.driver(uri, auth=(user, password))


def fetch_seed_entities_by_specs(specs: list[dict[str, str]], *, limit_per_label: int) -> list[dict[str, Any]]:
    """
    按 LLM 解析出的 (label, name) 查找种子实体。
    """
    if not specs:
        return []
    neo = _kg_cfg()
    database = neo.get("database", "neo4j")
    out: list[dict[str, Any]] = []
    with get_driver().session(database=database) as s:
        for spec in specs:
            label = (spec.get("label") or "").strip()
            name = (spec.get("name") or "").strip()
            if not label or not name or label not in ALLOWED_LABELS:
                continue
            q = f"""
            MATCH (n:{label})
            WHERE n.name CONTAINS $name OR ANY(a IN coalesce(n.aliases, []) WHERE a CONTAINS $name)
            RETURN DISTINCT n.id AS id, n.name AS name, $label AS label
            LIMIT $limit
            """
            rows = s.run(q, name=name, label=label, limit=limit_per_label)
            out.extend([r.data() for r in rows])
    # 去重
    dedup: dict[str, dict[str, Any]] = {}
    for r in out:
        rid = str(r.get("id") or "")
        if rid and rid not in dedup:
            dedup[rid] = r
    return list(dedup.values())


def fetch_neighbors(entity_ids: list[str], *, limit: int, relations: list[str] | None = None) -> list[dict[str, Any]]:
    if not entity_ids:
        return []
    valid_rel = [r for r in (relations or []) if r in ALLOWED_RELATIONS]
    neo = _kg_cfg()
    database = neo.get("database", "neo4j")
    if valid_rel:
        q = """
        UNWIND $entity_ids AS eid
        MATCH (a {id: eid})-[r]-(b)
        WHERE type(r) IN $relations
        WITH a, b, r,
             CASE WHEN startNode(r).id = a.id THEN a ELSE b END AS head,
             CASE WHEN startNode(r).id = a.id THEN b ELSE a END AS tail
        RETURN head.id AS head_id, head.name AS head_name, type(r) AS relation, tail.id AS tail_id, tail.name AS tail_name, r.confidence AS confidence
        LIMIT $limit
        """
    else:
        q = """
        UNWIND $entity_ids AS eid
        MATCH (a {id: eid})-[r]-(b)
        WITH a, b, r,
             CASE WHEN startNode(r).id = a.id THEN a ELSE b END AS head,
             CASE WHEN startNode(r).id = a.id THEN b ELSE a END AS tail
        RETURN head.id AS head_id, head.name AS head_name, type(r) AS relation, tail.id AS tail_id, tail.name AS tail_name, r.confidence AS confidence
        LIMIT $limit
        """
    with get_driver().session(database=database) as s:
        rows = s.run(q, entity_ids=entity_ids, relations=valid_rel, limit=limit)
        return [r.data() for r in rows]

