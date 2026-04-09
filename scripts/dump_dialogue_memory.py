"""导出 ChromaDB 中 dialogue 记忆到 JSON 文件（含原文与 metadata）。"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings


# 项目根目录加入 path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from app.config import load_config


def build_where(
    *,
    npc_id: str | None,
    player_id: str | None,
    dialogue_tier: str | None,
) -> dict[str, Any]:
    where: dict[str, Any] = {"memory_type": "dialogue"}
    if npc_id:
        where["npc_id"] = npc_id
    if player_id:
        where["player_id"] = player_id
    if dialogue_tier:
        where["dialogue_tier"] = dialogue_tier
    return where


def main() -> None:
    parser = argparse.ArgumentParser(
        description="导出 data/chroma 中 NPC-玩家对话记忆到 JSON 文件（document + metadata + id）"
    )
    parser.add_argument("--npc-id", default=None, help="按 npc_id 过滤（可选）")
    parser.add_argument("--player-id", default=None, help="按 player_id 过滤（可选）")
    parser.add_argument(
        "--tier",
        choices=["daily", "important"],
        default=None,
        help="按 dialogue_tier 过滤（可选）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="最多输出条数（默认 200）",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="分页偏移（默认 0）",
    )
    parser.add_argument(
        "--output",
        default="dialogue_memory_dump.json",
        help="输出 JSON 文件名或路径（默认 dialogue_memory_dump.json）",
    )
    args = parser.parse_args()

    cfg = load_config()
    vs = cfg.get("vectorstore", {})
    persist_dir = Path(vs.get("persist_dir", "data/chroma"))
    collection_name = vs.get("collection_name", "memory")

    client = chromadb.PersistentClient(
        path=str(persist_dir),
        settings=Settings(anonymized_telemetry=False),
    )
    coll = client.get_or_create_collection(
        name=collection_name,
        metadata={"description": "AI NPC unified memory store"},
    )

    where = build_where(
        npc_id=args.npc_id,
        player_id=args.player_id,
        dialogue_tier=args.tier,
    )

    raw = coll.get(
        where=where,
        include=["documents", "metadatas"],
        limit=max(args.limit, 0),
        offset=max(args.offset, 0),
    )
    ids = raw.get("ids") or []
    docs = raw.get("documents") or []
    metas = raw.get("metadatas") or []

    total = len(ids)
    records: list[dict[str, Any]] = []
    for i in range(total):
        records.append(
            {
            "index": i + args.offset,
            "id": ids[i],
            "document": docs[i] if i < len(docs) else None,
            "metadata": metas[i] if i < len(metas) else None,
            }
        )

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_payload = {
        "summary": {
            "total": total,
            "where": where,
            "collection": collection_name,
            "persist_dir": str(persist_dir),
            "limit": max(args.limit, 0),
            "offset": max(args.offset, 0),
        },
        "records": records,
    }
    output_path.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已写入 {total} 条记录到 {output_path}")


if __name__ == "__main__":
    main()
