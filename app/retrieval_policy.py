from typing import Any


def evaluate_document_evidence(
    candidates: list[Any],
    *,
    semantic_ready: bool,
    min_vector_confidence: float,
) -> dict[str, Any]:
    """Decide whether retrieval has enough evidence to override a general route."""
    for candidate in candidates:
        metadata = candidate.metadata or {}
        methods = set(metadata.get("retrieval_methods") or [])
        source = {
            "file_id": metadata.get("file_id"),
            "file_name": metadata.get("file_name") or metadata.get("source"),
            "chunk_index": metadata.get("chunk_index"),
            "methods": sorted(methods),
            "score": metadata.get("retrieval_score"),
            "vector_confidence": metadata.get("vector_confidence", 0.0),
        }
        if "graph" in methods:
            return {
                "accepted": True,
                "reason": "graph_evidence",
                "evidence": source,
            }
        if "keyword" in methods:
            return {
                "accepted": True,
                "reason": "keyword_evidence",
                "evidence": source,
            }
        confidence = float(metadata.get("vector_confidence") or 0.0)
        if semantic_ready and confidence >= min_vector_confidence:
            return {
                "accepted": True,
                "reason": "semantic_vector_evidence",
                "evidence": source,
            }

    return {
        "accepted": False,
        "reason": "no_verifiable_document_evidence",
        "evidence": None,
    }
