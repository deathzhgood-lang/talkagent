import hashlib
import math
import os
from typing import List
from sentence_transformers import SentenceTransformer
from langchain_core.embeddings import Embeddings
from app.config import BASE_DIR, EMBEDDING_MODEL, MODEL_CACHE_DIR


def _local_bge_path():
    local_model = BASE_DIR / "models" / "BAAI" / "bge-m3"
    has_weights = (
        (local_model / "pytorch_model.bin").exists()
        or (local_model / "model.safetensors").exists()
    )
    return local_model if local_model.exists() and has_weights else None


class BGEEmbeddings(Embeddings):
    """BGE-M3 Embedding 封装，兼容 LangChain Embeddings 接口"""

    def __init__(self, model_name: str = EMBEDDING_MODEL, cache_dir: str = MODEL_CACHE_DIR):
        local_model = _local_bge_path()
        if local_model is not None:
            model_name = str(local_model)
        self._model = SentenceTransformer(model_name, cache_folder=cache_dir)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        embedding = self._model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding.tolist()


# 全局单例
_embedding_instance: BGEEmbeddings | None = None


def get_embedding() -> BGEEmbeddings:
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = BGEEmbeddings()
    return _embedding_instance


class HashEmbeddings(Embeddings):
    """Offline fallback embedding used when BGE-M3 weights are unavailable."""

    def __init__(self, dimensions: int = 1024):
        self.dimensions = dimensions

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        tokens = [text[i : i + 2] for i in range(max(len(text) - 1, 1))] or [text]
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)


def get_safe_embedding() -> Embeddings:
    if EMBEDDING_MODEL == "BAAI/bge-m3" and _local_bge_path() is None:
        if os.getenv("ALLOW_HASH_EMBEDDING_FALLBACK", "true").lower() == "true":
            print("BGE-M3 local weights unavailable; using hash embedding fallback.")
            return HashEmbeddings()
    try:
        return get_embedding()
    except Exception as exc:
        if os.getenv("ALLOW_HASH_EMBEDDING_FALLBACK", "true").lower() != "true":
            raise
        print(f"BGE-M3 load failed; using hash embedding fallback: {exc}")
        return HashEmbeddings()
