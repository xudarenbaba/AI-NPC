"""Neo4j 客户端封装（查询 Entity 子图）。"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from neo4j import GraphDatabase

from app.config import load_config


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


def fetch_seed_entities(tokens: list[str], *, limit: int) -> list[dict[str, Any]]:
    if not tokens:
        return []
    neo = _kg_cfg()
    database = neo.get("database", "neo4j")
    q = """
    UNWIND $tokens AS token
    MATCH (n:Entity)
    WHERE n.name CONTAINS token OR toLower(n.id) CONTAINS toLower(token)
    RETURN DISTINCT n.id AS id, n.name AS name, n.type AS type
    LIMIT $limit
    """
    with get_driver().session(database=database) as s:
        rows = s.run(q, tokens=tokens, limit=limit)
        return [r.data() for r in rows]


def fetch_neighbors(entity_ids: list[str], *, limit: int) -> list[dict[str, Any]]:
    if not entity_ids:
        return []
    neo = _kg_cfg()
    database = neo.get("database", "neo4j")
    q = """
    UNWIND $entity_ids AS eid
    MATCH (a:Entity {id: eid})-[r]->(b:Entity)
    RETURN a.id AS head_id, a.name AS head_name, type(r) AS relation, b.id AS tail_id, b.name AS tail_name, r.confidence AS confidence
    LIMIT $limit
    """
    with get_driver().session(database=database) as s:
        rows = s.run(q, entity_ids=entity_ids, limit=limit)
        return [r.data() for r in rows]

