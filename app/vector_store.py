import uuid
from pathlib import Path
from typing import List
from langchain_core.documents import Document
from langchain_chroma import Chroma
from app.config import CHROMA_DIR
from app.embedder import get_safe_embedding


_collection_name = "talkagent_knowledge"


def _store_exists() -> bool:
    return any(Path(CHROMA_DIR).glob("**/*.sqlite3")) or any(Path(CHROMA_DIR).glob("**/*.parquet"))


def _get_store(with_embedding: bool = False) -> Chroma:
    """获取 Chroma 向量库实例"""
    return Chroma(
        collection_name=_collection_name,
        embedding_function=get_safe_embedding() if with_embedding else None,
        persist_directory=CHROMA_DIR,
    )


def add_documents(documents: List[Document], file_name: str) -> str:
    """
    将一组文档块入库。返回 file_id。
    """
    file_id = str(uuid.uuid4())
    for doc in documents:
        doc.metadata["file_id"] = file_id
        doc.metadata["file_name"] = file_name
    store = _get_store(with_embedding=True)
    store.add_documents(documents)
    return file_id


def delete_by_file(file_id: str) -> int:
    """
    根据 file_id 删除文档。返回删除的 chunk 数。
    """
    store = _get_store()
    # ChromaDB 通过 metadata 过滤删除
    results = store.get(where={"file_id": file_id})
    ids_to_delete = results.get("ids", [])
    if ids_to_delete:
        store.delete(ids=ids_to_delete)
    return len(ids_to_delete)


def similarity_search(query: str, k: int = 4, file_ids: list[str] | None = None) -> List[Document]:
    """相似度检索，可限制在指定 file_id 范围内。"""
    store = _get_store(with_embedding=True)
    if file_ids:
        where = {"file_id": file_ids[0]} if len(file_ids) == 1 else {"file_id": {"$in": file_ids}}
        return store.similarity_search(query, k=k, filter=where)
    return store.similarity_search(query, k=k)


def get_all_files() -> List[dict]:
    """
    返回知识库中所有文件的列表（去重 + 统计每个文件的 chunk 数）。
    """
    if not _store_exists():
        return []
    store = _get_store()
    results = store.get()
    metadatas = results.get("metadatas", [])
    file_map = {}
    for i, meta in enumerate(metadatas):
        fid = meta.get("file_id", "unknown")
        name = meta.get("file_name", "未知")
        if fid not in file_map:
            file_map[fid] = {"file_id": fid, "file_name": name, "chunk_count": 0}
        file_map[fid]["chunk_count"] += 1

    return list(file_map.values())


def get_documents_by_file(file_id: str) -> List[Document]:
    """返回指定文件的所有文档块。"""
    if not _store_exists():
        return []
    store = _get_store()
    results = store.get(where={"file_id": file_id})
    documents = results.get("documents", []) or []
    metadatas = results.get("metadatas", []) or []
    return [
        Document(page_content=text or "", metadata=metadata or {})
        for text, metadata in zip(documents, metadatas)
    ]


def get_stats() -> dict:
    """获取知识库统计信息"""
    if not _store_exists():
        return {"total_chunks": 0, "total_files": 0}
    store = _get_store()
    results = store.get()
    metadatas = results.get("metadatas", [])
    file_ids = set(m.get("file_id") for m in metadatas if m.get("file_id"))
    return {
        "total_chunks": len(results.get("ids", [])),
        "total_files": len(file_ids),
    }


def clear_all() -> int:
    """清空整个知识库。返回删除的 chunk 数。"""
    store = _get_store()
    results = store.get()
    ids = results.get("ids", [])
    if ids:
        store.delete(ids=ids)
    return len(ids)
