import importlib
from types import ModuleType, SimpleNamespace


def _load_rag_chain(monkeypatch):
    import sys

    sys.modules.pop("app.rag_chain", None)
    sys.modules.pop("app.hybrid_retrieval", None)
    fake_vector_store = ModuleType("app.vector_store")
    fake_vector_store.similarity_search = lambda *args, **kwargs: []
    fake_vector_store.similarity_search_with_scores = lambda *args, **kwargs: []
    fake_vector_store.get_all_files = lambda: []
    fake_vector_store.get_documents_by_file = lambda *args, **kwargs: []
    monkeypatch.setitem(sys.modules, "app.vector_store", fake_vector_store)
    return importlib.import_module("app.rag_chain")


def test_normalize_answer_label_matches_route(monkeypatch):
    rag_chain = _load_rag_chain(monkeypatch)

    answer = rag_chain._normalize_answer_label("general answer", {"mode": "hybrid"})

    assert answer != "general answer"
    assert "general answer" in answer


def test_sources_are_hidden_for_general_answers(monkeypatch):
    rag_chain = _load_rag_chain(monkeypatch)
    doc = SimpleNamespace(
        page_content="This is document content.",
        metadata={"file_name": "demo.md", "chunk_index": 0},
    )

    general_answer = rag_chain._normalize_answer_label("general answer", {"mode": "general"})
    assert rag_chain._sources_for_answer(general_answer, [doc]) == []

    document_answer = rag_chain._normalize_answer_label("document answer", {"mode": "document"})
    sources = rag_chain._sources_for_answer(document_answer, [doc])
    assert sources[0]["file_name"] == "demo.md"
    assert sources[0]["chunk_index"] == 0
    assert sources[0]["score"] is None
    assert sources[0]["methods"] == []
    assert sources[0]["snippet"] == "This is document content."


def test_required_parameter_answer_can_be_enforced(monkeypatch):
    rag_chain = _load_rag_chain(monkeypatch)
    doc = SimpleNamespace(
        page_content=(
            "| name | type | required |\n"
            "| prompt | string | required |\n"
            "| req_key | string | required |\n"
        ),
        metadata={},
    )

    answer = rag_chain._enforce_required_items(
        "Which parameters are required?",
        "prompt is required",
        {"mode": "document"},
        [doc],
    )

    assert "prompt" in answer
    assert "req_key" in answer


def test_document_probe_overrides_a_general_route_with_keyword_evidence(monkeypatch):
    rag_chain = _load_rag_chain(monkeypatch)
    doc = SimpleNamespace(
        page_content="The refund policy is seven days.",
        metadata={
            "file_id": "file-1",
            "file_name": "policy.md",
            "chunk_index": 0,
            "retrieval_methods": ["keyword"],
            "retrieval_score": 0.8,
            "vector_confidence": 0.0,
        },
    )
    probe = rag_chain.RetrievalResult(docs=[doc], debug=[], candidates=[doc])
    monkeypatch.setattr(rag_chain, "get_all_files", lambda: [{"file_id": "file-1"}])
    monkeypatch.setattr(rag_chain, "hybrid_search", lambda *args, **kwargs: probe)
    monkeypatch.setattr(rag_chain, "semantic_embedding_ready", lambda: False)

    route, retrieval, trace = rag_chain._retrieve_with_document_probe(
        "What is the refund policy?",
        {
            "mode": "general",
            "needs_documents": False,
            "relevant_file_ids": [],
            "can_use_general_knowledge": True,
        },
    )

    assert route["mode"] == "document"
    assert route["needs_documents"] is True
    assert retrieval.docs == [doc]
    assert trace["status"] == "accepted"
