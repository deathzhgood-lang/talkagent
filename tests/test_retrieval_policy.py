from langchain_core.documents import Document

from app.retrieval_policy import evaluate_document_evidence


def _document(methods, vector_confidence=0.0):
    return Document(
        page_content="Evidence",
        metadata={
            "file_id": "file-1",
            "file_name": "policy.md",
            "chunk_index": 0,
            "retrieval_methods": methods,
            "retrieval_score": 0.8,
            "vector_confidence": vector_confidence,
        },
    )


def test_keyword_evidence_can_override_a_general_route():
    decision = evaluate_document_evidence(
        [_document(["keyword"])],
        semantic_ready=False,
        min_vector_confidence=0.58,
    )

    assert decision["accepted"] is True
    assert decision["reason"] == "keyword_evidence"


def test_vector_evidence_requires_a_real_semantic_embedder():
    candidate = _document(["vector"], vector_confidence=0.8)

    fallback_decision = evaluate_document_evidence(
        [candidate], semantic_ready=False, min_vector_confidence=0.58
    )
    semantic_decision = evaluate_document_evidence(
        [candidate], semantic_ready=True, min_vector_confidence=0.58
    )

    assert fallback_decision["accepted"] is False
    assert semantic_decision["accepted"] is True
    assert semantic_decision["reason"] == "semantic_vector_evidence"
