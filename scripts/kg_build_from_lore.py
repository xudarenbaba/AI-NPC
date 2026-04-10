"""从 lore 离线构建知识图谱并写入 Neo4j（LLM 抽取版）。"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from app.config import load_config
from app.knowledge_graph.schema import (
    ALLOWED_LABELS,
    ALLOWED_RELATIONS,
    normalize_name,
    stable_entity_id,
)
from app.reasoning.llm import call_llm

logger = logging.getLogger(__name__)


def _labels_enum_text() -> str:
    return "|".join(sorted(ALLOWED_LABELS))


def _relations_enum_text() -> str:
    return "|".join(sorted(ALLOWED_RELATIONS))


@dataclass(frozen=True)
class Entity:
    id: str
    label: str
    name: str
    aliases: list[str]
    source_file: str


@dataclass(frozen=True)
class Relation:
    head_id: str
    relation: str
    tail_id: str
    source_file: str
    evidence: str
    confidence: float


def split_chunks(text: str) -> list[str]:
    chunks: list[str] = []
    for part in text.split("\n\n"):
        p = part.strip()
        if not p:
            continue
        chunks.append(p)
    return chunks


def _extract_json(content: str) -> dict[str, Any]:
    raw = (content or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    return json.loads(raw)


def extract_graph_from_chunk(*, chunk: str, source_file: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    labels_text = _labels_enum_text()
    relations_text = _relations_enum_text()
    system_prompt = (
        "你是知识图谱抽取器。只输出 JSON，不要输出其它文本。\n"
        "输出格式："
        + '{"entities":[{"name":"...","label":"'
        + labels_text
        + '","aliases":["..."]}],'
        + '"relations":[{"head_name":"...","head_label":"'
        + labels_text
        + '",'
        + '"relation":"'
        + relations_text
        + '",'
        + '"tail_name":"...","tail_label":"'
        + labels_text
        + '",'
        + '"confidence":0.0,"evidence":"..."}]}\n'
        "要求：不要臆造，不确定就不输出。"
    )
    user_prompt = f"source_file={source_file}\ntext={chunk}\n请输出 JSON。"
    content = call_llm(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    data = _extract_json(content)
    entities = data.get("entities") or []
    relations = data.get("relations") or []
    return entities, relations


def _normalize_entities(raw_entities: list[dict[str, Any]], source_file: str) -> dict[str, Entity]:
    out: dict[str, Entity] = {}
    for e in raw_entities:
        label = str((e or {}).get("label") or "").strip()
        name = normalize_name(str((e or {}).get("name") or ""))
        aliases = [normalize_name(str(x)) for x in ((e or {}).get("aliases") or []) if str(x).strip()]
        if label not in ALLOWED_LABELS or not name:
            continue
        eid = stable_entity_id(label, name)
        out[eid] = Entity(
            id=eid,
            label=label,
            name=name,
            aliases=aliases,
            source_file=source_file,
        )
    return out


def _normalize_relations(
    raw_relations: list[dict[str, Any]],
    entities: dict[str, Entity],
    source_file: str,
) -> list[Relation]:
    out: list[Relation] = []
    for r in raw_relations:
        rel = str((r or {}).get("relation") or "").strip()
        h_name = normalize_name(str((r or {}).get("head_name") or ""))
        h_label = str((r or {}).get("head_label") or "").strip()
        t_name = normalize_name(str((r or {}).get("tail_name") or ""))
        t_label = str((r or {}).get("tail_label") or "").strip()
        if rel not in ALLOWED_RELATIONS:
            continue
        if h_label not in ALLOWED_LABELS or t_label not in ALLOWED_LABELS:
            continue
        if not h_name or not t_name:
            continue
        head_id = stable_entity_id(h_label, h_name)
        tail_id = stable_entity_id(t_label, t_name)
        if head_id not in entities or tail_id not in entities:
            # 只保留实体也成功入图的关系
            continue
        conf = float((r or {}).get("confidence") or 0.0)
        evidence = normalize_name(str((r or {}).get("evidence") or ""))
        out.append(
            Relation(
                head_id=head_id,
                relation=rel,
                tail_id=tail_id,
                source_file=source_file,
                evidence=evidence,
                confidence=max(0.0, min(1.0, conf)),
            )
        )
    return out


def write_graph(
    *,
    uri: str,
    user: str,
    password: str,
    database: str,
    entities: dict[str, Entity],
    relations: list[Relation],
) -> None:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    now = datetime.now(timezone.utc).isoformat()
    with driver.session(database=database) as session:
        for e in entities.values():
            q = f"""
            MERGE (n:{e.label} {{id: $id}})
            SET n.name = $name,
                n.aliases = $aliases,
                n.source_files = CASE WHEN n.source_files IS NULL THEN [$source_file] ELSE apoc.coll.toSet(n.source_files + [$source_file]) END,
                n.updated_at = $updated_at
            """
            try:
                session.run(
                    q,
                    id=e.id,
                    name=e.name,
                    aliases=e.aliases,
                    source_file=e.source_file,
                    updated_at=now,
                )
            except Exception:
                # 没有 APOC 的环境使用纯赋值退化
                q2 = f"""
                MERGE (n:{e.label} {{id: $id}})
                SET n.name = $name,
                    n.aliases = $aliases,
                    n.source_files = [$source_file],
                    n.updated_at = $updated_at
                """
                session.run(
                    q2,
                    id=e.id,
                    name=e.name,
                    aliases=e.aliases,
                    source_file=e.source_file,
                    updated_at=now,
                )

        for r in relations:
            q = f"""
            MATCH (h {{id: $head_id}})
            MATCH (t {{id: $tail_id}})
            MERGE (h)-[rel:{r.relation}]->(t)
            SET rel.source_file = $source_file,
                rel.evidence = $evidence,
                rel.confidence = $confidence,
                rel.updated_at = $updated_at
            """
            session.run(
                q,
                head_id=r.head_id,
                tail_id=r.tail_id,
                source_file=r.source_file,
                evidence=r.evidence,
                confidence=r.confidence,
                updated_at=now,
            )
    driver.close()


def main() -> None:
    cfg = load_config()
    neo4j_cfg = cfg.get("knowledge_graph", {}).get("neo4j", {})
    parser = argparse.ArgumentParser(description="从 lore 离线构建知识图谱并写入 Neo4j（LLM）")
    parser.add_argument("--uri", default=neo4j_cfg.get("uri", "neo4j://127.0.0.1:7687"), help="Neo4j URI")
    parser.add_argument("--user", default=neo4j_cfg.get("user", "neo4j"), help="Neo4j 用户名")
    parser.add_argument("--password", default=neo4j_cfg.get("password", ""), help="Neo4j 密码")
    parser.add_argument("--database", default=neo4j_cfg.get("database", "neo4j"), help="数据库名（默认 neo4j）")
    parser.add_argument("--lore-dir", default=str(root / "lore"), help="lore 目录路径")
    args = parser.parse_args()
    if not args.password:
        raise ValueError("Neo4j 密码为空，请在 config.yaml 中设置 knowledge_graph.neo4j.password 或使用 --password")

    lore_dir = Path(args.lore_dir)
    files = sorted(lore_dir.glob("**/*.md"))
    all_entities: dict[str, Entity] = {}
    all_relations: list[Relation] = []

    for f in files:
        rel = str(f.relative_to(root))
        text = f.read_text(encoding="utf-8")
        chunks = split_chunks(text)
        logger.info("KG import file start. file=%s chunks=%s", rel, len(chunks))
        for idx, chunk in enumerate(chunks):
            try:
                raw_entities, raw_relations = extract_graph_from_chunk(chunk=chunk, source_file=rel)
                chunk_entities = _normalize_entities(raw_entities, rel)
                # 先并入全局实体，保障关系校验可命中
                all_entities.update(chunk_entities)
                chunk_rel = _normalize_relations(raw_relations, all_entities, rel)
                all_relations.extend(chunk_rel)
                logger.info(
                    "KG chunk extracted. file=%s idx=%s entities=%s relations=%s",
                    rel,
                    idx,
                    len(chunk_entities),
                    len(chunk_rel),
                )
            except Exception as e:
                logger.warning("KG chunk extract failed. file=%s idx=%s detail=%s", rel, idx, e)

    # 关系去重
    dedup_rel: dict[tuple[str, str, str], Relation] = {}
    for r in all_relations:
        key = (r.head_id, r.relation, r.tail_id)
        old = dedup_rel.get(key)
        if old is None or r.confidence > old.confidence:
            dedup_rel[key] = r
    final_relations = list(dedup_rel.values())

    write_graph(
        uri=args.uri,
        user=args.user,
        password=args.password,
        database=args.database,
        entities=all_entities,
        relations=final_relations,
    )
    print(
        f"图谱导入完成：nodes={len(all_entities)} edges={len(final_relations)} "
        f"uri={args.uri} database={args.database}"
    )


if __name__ == "__main__":
    main()

