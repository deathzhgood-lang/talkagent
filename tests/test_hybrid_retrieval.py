from langchain_core.documents import Document

from app import hybrid_retrieval


def test_hybrid_search_merges_keyword_and_graph_hits(monkeypatch):
    doc = Document(
        page_content="TalkAgent uses ChromaDB for local knowledge retrieval.",
        metadata={"file_id": "file-1", "file_name": "demo.md", "chunk_index": 0},
    )

    monkeypatch.setattr(
        hybrid_retrieval,
        "similarity_search_with_scores",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        hybrid_retrieval,
        "get_all_files",
        lambda: [{"file_id": "file-1", "file_name": "demo.md", "chunk_count": 1}],
    )
    monkeypatch.setattr(
        hybrid_retrieval,
        "get_documents_by_file",
        lambda file_id: [doc] if file_id == "file-1" else [],
    )
    monkeypatch.setattr(
        hybrid_retrieval,
        "search_graph",
        lambda *args, **kwargs: [
            {
                "file_id": "file-1",
                "file_name": "demo.md",
                "chunk_index": 0,
                "score": 2.0,
                "matched_terms": ["chromadb"],
            }
        ],
    )

    result = hybrid_retrieval.hybrid_search("ChromaDB retrieval", k=3, mode="mix")

    assert len(result.docs) == 1
    meta = result.docs[0].metadata
    assert set(meta["retrieval_methods"]) == {"graph", "keyword"}
    assert meta["retrieval_score"] > 0
    assert result.debug[0]["methods"] == ["graph", "keyword"]
