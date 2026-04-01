""" 长期记忆：ChromaDB 存储 Lore 与交互记录，RAG 检索 """
import uuid
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
    """ChromaDB 封装：kbase（交互 + 可选 Lore）与 lore 集合"""

    def __init__(self):
        cfg = load_config()
        vs = cfg.get("vectorstore", {})
        persist_dir = Path(vs.get("persist_dir", "data/chroma"))
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection_name = vs.get("collection_name", "kbase")
        self._lore_name = vs.get("lore_collection_name", "lore")
        self._k = cfg.get("memory", {}).get("rag_top_k", 5)

    def _get_collection(self, name: str):
        return self._client.get_or_create_collection(
            name=name,
            metadata={"description": "NPC long-term memory"},
        )

    def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        collection: str | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """写入文档。若未提供 ids 则自动生成。返回实际使用的 id 列表。"""
        coll_name = collection or self._collection_name
        coll = self._get_collection(coll_name)
        if not texts:
            return []
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]
        if metadatas is None:
            metadatas = [{}] * len(texts)
        if len(metadatas) < len(texts):
            metadatas = metadatas + [{}] * (len(texts) - len(metadatas))
        embeddings = _embed_fn(texts)
        coll.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        return ids

    def search(
        self,
        query: str,
        k: int | None = None,
        filter_by_player: str | None = None,
        filter_by_npc: str | None = None,
        include_lore: bool = True,
    ) -> list[str]:
        """
        语义检索：先查 kbase（可选按 player_id 过滤），若 include_lore 再查 lore，合并去重后返回文本列表。
        """
        k = k or self._k
        results: list[str] = []
        seen: set[str] = set()

        # 交互记忆（kbase）
        coll = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"description": "NPC long-term memory"},
        )
        where: dict[str, Any] | None = None
        if filter_by_player or filter_by_npc:
            where = {}
            if filter_by_player:
                where["player_id"] = filter_by_player
            if filter_by_npc:
                where["npc_id"] = filter_by_npc
        try:
            q_emb = _embed_fn([query])[0]
            raw = coll.query(
                query_embeddings=[q_emb],
                n_results=k,
                where=where,
                include=["documents"],
            )
            if raw and raw.get("documents") and raw["documents"][0]:
                for doc in raw["documents"][0]:
                    if doc and doc not in seen:
                        seen.add(doc)
                        results.append(doc)
        except Exception:
            pass

        # 世界观 Lore
        if include_lore and k - len(results) > 0:
            try:
                lore_coll = self._client.get_or_create_collection(
                    name=self._lore_name,
                    metadata={"description": "World lore"},
                )
                q_emb = _embed_fn([query])[0]
                raw = lore_coll.query(
                    query_embeddings=[q_emb],
                    n_results=max(1, k - len(results)),
                    include=["documents"],
                )
                if raw and raw.get("documents") and raw["documents"][0]:
                    for doc in raw["documents"][0]:
                        if doc and doc not in seen:
                            seen.add(doc)
                            results.append(doc)
            except Exception:
                pass

        return results

    def add_lore(self, texts: list[str], ids: list[str] | None = None) -> list[str]:
        """向 lore 集合写入世界观片段。"""
        return self.add_documents(
            texts=texts,
            metadatas=[{"type": "world"}] * len(texts),
            collection=self._lore_name,
            ids=ids,
        )
