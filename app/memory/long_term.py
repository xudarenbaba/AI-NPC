"""长期记忆：单集合 + metadata 分类（world/persona/dialogue）。"""
import uuid
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from app.config import load_config


def _get_embedding_model():
    cfg = load_config()
    emb = cfg.get("embeddings", {})
    model_name = emb.get("model", "BAAI/bge-small-zh-v1.5")
    cache_dir = emb.get("cache_dir", "models")
    # 相对路径相对项目根目录，避免从其它 cwd 启动时误用错误目录
    root = Path(__file__).resolve().parent.parent.parent
    cache_path = Path(cache_dir)
    if not cache_path.is_absolute():
        cache_path = root / cache_path
    cache_path.mkdir(parents=True, exist_ok=True)
    # True：仅用本地缓存，不向 Hugging Face 发 HEAD/下载（适合已下过模型或内网环境）
    local_only = bool(emb.get("local_files_only", False))
    return SentenceTransformer(
        model_name,
        cache_folder=str(cache_path),
        local_files_only=local_only,
    )


_embedding_model = None


def _embed_fn(texts: list[str]) -> list[list[float]]:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = _get_embedding_model()
    emb = _embedding_model.encode(texts, normalize_embeddings=True)
    return emb.tolist()


class LongTermMemory:
    """ChromaDB 封装：单集合 memory，靠 metadata 做逻辑分层。"""

    def __init__(self):
        cfg = load_config()
        vs = cfg.get("vectorstore", {})
        persist_dir = Path(vs.get("persist_dir", "data/chroma"))
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection_name = vs.get("collection_name", "memory")
        mem = cfg.get("memory", {})
        self._k_world = int(mem.get("k_world", 3))
        self._k_persona = int(mem.get("k_persona", 3))
        self._k_dialogue = int(mem.get("k_dialogue", 5))

    def _get_collection(self, name: str):
        return self._client.get_or_create_collection(
            name=name,
            metadata={"description": "AI NPC unified memory store"},
        )

    def add_memory(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str] | None = None,
    ) -> list[str]:
        """写入统一 memory 集合。"""
        coll = self._get_collection(self._collection_name)
        if not texts:
            return []
        if len(metadatas) != len(texts):
            raise ValueError("metadatas length must equal texts length")
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]
        embeddings = _embed_fn(texts)
        # 使用 upsert 便于按固定 id 去重导入（重复导入会更新而非报错）
        coll.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        return ids

    def _query_documents(
        self,
        query: str,
        *,
        where: dict[str, Any],
        k: int,
    ) -> list[str]:
        coll = self._get_collection(self._collection_name)
        try:
            q_emb = _embed_fn([query])[0]
            raw = coll.query(
                query_embeddings=[q_emb],
                n_results=k,
                where=where,
                include=["documents"],
            )
            docs = raw.get("documents", [[]])[0] if raw else []
            return [doc for doc in docs if doc]
        except Exception:
            return []

    def add_world(self, texts: list[str], ids: list[str] | None = None) -> list[str]:
        now = datetime.now(timezone.utc).isoformat()
        if ids is None:
            ids = [
                f"world:{hashlib.sha1(t.strip().encode('utf-8')).hexdigest()}"
                for t in texts
            ]
        metas = [
            {
                "memory_type": "world",
                "scope": "global",
                "source": "import",
                "created_at": now,
            }
            for _ in texts
        ]
        return self.add_memory(texts=texts, metadatas=metas, ids=ids)

    def add_persona(self, npc_id: str, texts: list[str], ids: list[str] | None = None) -> list[str]:
        now = datetime.now(timezone.utc).isoformat()
        if ids is None:
            ids = [
                f"persona:{npc_id}:{hashlib.sha1(t.strip().encode('utf-8')).hexdigest()}"
                for t in texts
            ]
        metas = [
            {
                "memory_type": "persona",
                "scope": "npc",
                "npc_id": npc_id,
                "source": "seed",
                "created_at": now,
            }
            for _ in texts
        ]
        return self.add_memory(texts=texts, metadatas=metas, ids=ids)

    def add_dialogue(
        self,
        npc_id: str | None,
        player_id: str,
        texts: list[str],
        *,
        scene_info: dict[str, Any] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        now = datetime.now(timezone.utc).isoformat()
        npc_value = npc_id or "default"
        scene = str(scene_info) if scene_info else ""
        metas = [
            {
                "memory_type": "dialogue",
                "scope": "npc_player",
                "npc_id": npc_value,
                "player_id": player_id,
                "source": "runtime",
                "scene": scene,
                "created_at": now,
            }
            for _ in texts
        ]
        return self.add_memory(texts=texts, metadatas=metas, ids=ids)

    def search_world(self, query: str, k: int | None = None) -> list[str]:
        return self._query_documents(
            query,
            where={"memory_type": "world"},
            k=k or self._k_world,
        )

    def search_persona(self, query: str, npc_id: str | None, k: int | None = None) -> list[str]:
        return self._query_documents(
            query,
            where={"memory_type": "persona", "npc_id": npc_id or "default"},
            k=k or self._k_persona,
        )

    def search_dialogue(
        self,
        query: str,
        npc_id: str | None,
        player_id: str,
        k: int | None = None,
    ) -> list[str]:
        return self._query_documents(
            query,
            where={
                "memory_type": "dialogue",
                "npc_id": npc_id or "default",
                "player_id": player_id,
            },
            k=k or self._k_dialogue,
        )
