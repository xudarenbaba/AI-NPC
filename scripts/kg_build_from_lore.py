"""从 lore 离线构建知识图谱并写入 Neo4j（MVP 规则版）。"""
import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from neo4j import GraphDatabase


root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from app.config import load_config


@dataclass(frozen=True)
class Entity:
    id: str
    type: str
    name: str
    source_file: str


@dataclass(frozen=True)
class Relation:
    head_id: str
    relation: str
    tail_id: str
    source_file: str
    evidence: str
    confidence: float


def slug(text: str) -> str:
    """
    生成可读 slug：
    - 保留中英文、数字、下划线
    - 其它符号归一为 "_"
    - 为空时返回 "entity"
    """
    s = text.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "entity"


def entity_id(entity_type: str, name: str) -> str:
    """
    生成稳定唯一 ID：
    <Type>:<readable_slug>:<sha1_12>
    - slug 用于可读性
    - hash 用于去歧义与稳定性（避免同名/清洗后冲突）
    """
    canonical = name.strip()
    readable = slug(canonical)
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]
    return f"{entity_type}:{readable}:{digest}"


def parse_world(world_path: Path) -> tuple[dict[str, Entity], list[Relation]]:
    entities: dict[str, Entity] = {}
    relations: list[Relation] = []
    source = str(world_path.relative_to(root))
    text = world_path.read_text(encoding="utf-8")

    # 地点常识：形如 “村口：xxx”
    for m in re.finditer(r"^([^\n：]{1,20})：([^\n]+)$", text, flags=re.M):
        name = m.group(1).strip()
        if len(name) > 12:
            continue
        if name in {"当前可交互 NPC 设定（对应现有脚本角色）", "可扩展 NPC 设定（供后续添加到 npc_state_tools.py）"}:
            continue
        eid = entity_id("Location", name)
        entities[eid] = Entity(id=eid, type="Location", name=name, source_file=source)

    # 世界观中常见组织
    for org in ["青石巡卫", "行脚商会"]:
        if org in text:
            eid = entity_id("Organization", org)
            entities[eid] = Entity(id=eid, type="Organization", name=org, source_file=source)

    # 世界观中出现的关键概念
    for concept in ["北山谷口封印", "妖雾", "镇雾符核", "赤纹铁", "清心草", "下品灵石"]:
        if concept in text:
            eid = entity_id("Concept", concept)
            entities[eid] = Entity(id=eid, type="Concept", name=concept, source_file=source)

    return entities, relations


def parse_persona_file(path: Path) -> tuple[dict[str, Entity], list[Relation]]:
    entities: dict[str, Entity] = {}
    relations: list[Relation] = []
    source = str(path.relative_to(root))
    text = path.read_text(encoding="utf-8")

    npc_id_match = re.search(r"^NPC_ID:\s*([^\n]+)$", text, flags=re.M)
    npc_id = npc_id_match.group(1).strip() if npc_id_match else path.stem

    # 姓名/称呼：罗恩（城门守卫）
    display_match = re.search(r"^姓名/称呼：([^\n]+)$", text, flags=re.M)
    display = display_match.group(1).strip() if display_match else npc_id
    char_eid = entity_id("Character", npc_id)
    entities[char_eid] = Entity(id=char_eid, type="Character", name=display, source_file=source)

    # 身份定位：xxx
    role_match = re.search(r"^身份定位：([^\n]+)$", text, flags=re.M)
    if role_match:
        role_name = role_match.group(1).strip()
        role_eid = entity_id("Role", role_name)
        entities[role_eid] = Entity(id=role_eid, type="Role", name=role_name, source_file=source)
        relations.append(
            Relation(
                head_id=char_eid,
                relation="HAS_ROLE",
                tail_id=role_eid,
                source_file=source,
                evidence=role_name,
                confidence=0.95,
            )
        )

    # 当前任务：xxx
    task_match = re.search(r"^当前任务：([^\n]+)$", text, flags=re.M)
    if task_match:
        task_name = task_match.group(1).strip()
        task_eid = entity_id("Task", task_name)
        entities[task_eid] = Entity(id=task_eid, type="Task", name=task_name, source_file=source)
        relations.append(
            Relation(
                head_id=char_eid,
                relation="HAS_TASK",
                tail_id=task_eid,
                source_file=source,
                evidence=task_name,
                confidence=0.9,
            )
        )

    # 与玩家互动偏好：xxx
    pref_match = re.search(r"^与玩家互动偏好：([^\n]+)$", text, flags=re.M)
    if pref_match:
        pref_name = pref_match.group(1).strip()
        pref_eid = entity_id("Preference", pref_name)
        entities[pref_eid] = Entity(id=pref_eid, type="Preference", name=pref_name, source_file=source)
        relations.append(
            Relation(
                head_id=char_eid,
                relation="INTERACTS_WITH_PLAYER_AS",
                tail_id=pref_eid,
                source_file=source,
                evidence=pref_name,
                confidence=0.85,
            )
        )

    # 可执行动作：dialogue, idle, emote
    actions_match = re.search(r"^可执行动作：([^\n]+)$", text, flags=re.M)
    if actions_match:
        actions = [a.strip(" 。,，") for a in re.split(r"[,，]", actions_match.group(1)) if a.strip()]
        for action in actions:
            act_eid = entity_id("Action", action)
            entities[act_eid] = Entity(id=act_eid, type="Action", name=action, source_file=source)
            relations.append(
                Relation(
                    head_id=char_eid,
                    relation="CAN_DO",
                    tail_id=act_eid,
                    source_file=source,
                    evidence=action,
                    confidence=0.98,
                )
            )

    # 角色到地点（从人设描述里做轻量规则）
    if "城门守卫" in text or "村口" in text:
        loc_eid = entity_id("Location", "村口")
        entities[loc_eid] = Entity(id=loc_eid, type="Location", name="村口", source_file=source)
        relations.append(
            Relation(
                head_id=char_eid,
                relation="LOCATED_IN",
                tail_id=loc_eid,
                source_file=source,
                evidence="城门守卫/村口",
                confidence=0.8,
            )
        )

    return entities, relations


def write_graph(uri: str, user: str, password: str, database: str, entities: dict[str, Entity], relations: list[Relation]) -> None:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session(database=database) as session:
        # 批量写节点
        entity_rows = [
            {
                "id": e.id,
                "type": e.type,
                "name": e.name,
                "source_file": e.source_file,
            }
            for e in entities.values()
        ]
        session.run(
            """
            UNWIND $rows AS row
            MERGE (n:Entity {id: row.id})
            SET n.type = row.type,
                n.name = row.name,
                n.source_file = row.source_file
            """,
            rows=entity_rows,
        )

        # 关系逐条写（关系类型动态）
        for r in relations:
            q = f"""
            MATCH (h:Entity {{id: $head_id}})
            MATCH (t:Entity {{id: $tail_id}})
            MERGE (h)-[rel:{r.relation}]->(t)
            SET rel.source_file = $source_file,
                rel.evidence = $evidence,
                rel.confidence = $confidence
            """
            session.run(
                q,
                head_id=r.head_id,
                tail_id=r.tail_id,
                source_file=r.source_file,
                evidence=r.evidence,
                confidence=r.confidence,
            )
    driver.close()


def main() -> None:
    cfg = load_config()
    neo4j_cfg = cfg.get("knowledge_graph", {}).get("neo4j", {})
    parser = argparse.ArgumentParser(description="从 lore 离线构建知识图谱并写入 Neo4j（MVP）")
    parser.add_argument("--uri", default=neo4j_cfg.get("uri", "neo4j://127.0.0.1:7687"), help="Neo4j URI")
    parser.add_argument("--user", default=neo4j_cfg.get("user", "neo4j"), help="Neo4j 用户名")
    parser.add_argument("--password", default=neo4j_cfg.get("password", ""), help="Neo4j 密码")
    parser.add_argument("--database", default=neo4j_cfg.get("database", "neo4j"), help="数据库名（默认 neo4j）")
    parser.add_argument("--lore-dir", default=str(root / "lore"), help="lore 目录路径")
    args = parser.parse_args()
    if not args.password:
        raise ValueError("Neo4j 密码为空，请在 config.yaml 中设置 knowledge_graph.neo4j.password 或使用 --password")

    lore_dir = Path(args.lore_dir)
    world_path = lore_dir / "world.md"
    persona_dir = lore_dir / "persona"

    all_entities: dict[str, Entity] = {}
    all_relations: list[Relation] = []

    if world_path.exists():
        ents, rels = parse_world(world_path)
        all_entities.update(ents)
        all_relations.extend(rels)

    if persona_dir.exists():
        for pf in sorted(persona_dir.glob("*.md")):
            ents, rels = parse_persona_file(pf)
            all_entities.update(ents)
            all_relations.extend(rels)

    write_graph(
        uri=args.uri,
        user=args.user,
        password=args.password,
        database=args.database,
        entities=all_entities,
        relations=all_relations,
    )
    print(
        f"图谱导入完成：nodes={len(all_entities)} edges={len(all_relations)} "
        f"uri={args.uri} database={args.database}"
    )


if __name__ == "__main__":
    main()

