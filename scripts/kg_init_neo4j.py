"""初始化 Neo4j 知识图谱约束与索引。"""
import argparse
import sys
from pathlib import Path

from neo4j import GraphDatabase


# 项目根目录加入 path（保持与现有脚本风格一致）
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from app.config import load_config


CONSTRAINTS_AND_INDEXES = [
    "CREATE CONSTRAINT kg_entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE",
    "CREATE INDEX kg_entity_type IF NOT EXISTS FOR (n:Entity) ON (n.type)",
    "CREATE INDEX kg_entity_name IF NOT EXISTS FOR (n:Entity) ON (n.name)",
]


def main() -> None:
    cfg = load_config()
    neo4j_cfg = cfg.get("knowledge_graph", {}).get("neo4j", {})
    parser = argparse.ArgumentParser(description="初始化 Neo4j 图谱约束与索引")
    parser.add_argument("--uri", default=neo4j_cfg.get("uri", "neo4j://127.0.0.1:7687"), help="Neo4j URI")
    parser.add_argument("--user", default=neo4j_cfg.get("user", "neo4j"), help="Neo4j 用户名")
    parser.add_argument("--password", default=neo4j_cfg.get("password", ""), help="Neo4j 密码")
    parser.add_argument("--database", default=neo4j_cfg.get("database", "neo4j"), help="数据库名（默认 neo4j）")
    args = parser.parse_args()
    if not args.password:
        raise ValueError("Neo4j 密码为空，请在 config.yaml 中设置 knowledge_graph.neo4j.password 或使用 --password")

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    with driver.session(database=args.database) as session:
        for q in CONSTRAINTS_AND_INDEXES:
            session.run(q)
    driver.close()
    print(f"Neo4j 初始化完成: uri={args.uri}, database={args.database}")


if __name__ == "__main__":
    main()

