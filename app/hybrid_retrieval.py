import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document

from app.light_graph import search_graph
from app.vector_store import get_all_files, get_documents_by_file, similarity_search_with_scores


WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{1,}|[\u4e00-\u9fff]{2,}")


@dataclass
class RetrievalResult:
    docs: list[Document]
    debug: list[dict[str, Any]]


def _tokenize(text: str) -> list[str]:
    tokens = [match.group(0).lower() for match in WORD_RE.finditer(text or "")]
    cjk_text = "".join(re.findall(r"[\u4e00-\u9fff]+", text or ""))
    tokens.extend(cjk_text[i : i + 2] for i in range(max(len(cjk_text) - 1, 0)))
    return [token for token in tokens if len(token) >= 2]


def _doc_key(doc: Document) -> tuple[str, Any, str]:
    meta = doc.metadata or {}
    return (
        str(meta.get("file_id", "")),
        meta.get("chunk_index", ""),
        (doc.page_content or "")[:80],
    )


def _copy_doc(doc: Document) -> Document:
    return Document(page_content=doc.page_content, metadata=dict(doc.metadata or {}))


def _normalize_scores(scores: dict[tuple[str, Any, str], float]) -> dict[tuple[str, Any, str], float]:
    if not scores:
        return {}
    max_score = max(scores.values()) or 1.0
    return {key: value / max_score for key, value in scores.items()}


def _all_candidate_docs(file_ids: list[str] | None = None) -> list[Document]:
    ids = file_ids or [doc["file_id"] for doc in get_all_files()]
    documents: list[Document] = []
    for file_id in ids:
        documents.extend(get_documents_by_file(file_id))
    return documents


def _keyword_search(
    query: str,
    file_ids: list[str] | None = None,
    limit: int = 20,
) -> list[tuple[Document, float]]:
    query_terms = _tokenize(query)
    if not query_terms:
        return []

    candidates = _all_candidate_docs(file_ids)
    if not candidates:
        return []

    query_counts = Counter(query_terms)
    doc_tokens = [_tokenize(doc.page_content) for doc in candidates]
    doc_freq: Counter[str] = Counter()
    for tokens in doc_tokens:
        doc_freq.update(set(tokens))

    total_docs = len(candidates)
    scored: list[tuple[Document, float]] = []
    avg_len = sum(len(tokens) for tokens in doc_tokens) / max(total_docs, 1)
    avg_len = avg_len or 1.0

    for doc, tokens in zip(candidates, doc_tokens):
        counts = Counter(tokens)
        doc_len = len(tokens) or 1
        score = 0.0
        for term, qf in query_counts.items():
            tf = counts.get(term, 0)
            if not tf:
                if term in (doc.page_content or "").lower():
                    score += 0.4 * qf
                continue
            idf = math.log(1 + (total_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            denom = tf + 1.5 * (1 - 0.75 + 0.75 * doc_len / avg_len)
            score += idf * (tf * 2.5 / denom) * qf
        if score > 0:
            scored.append((doc, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


def _graph_search_docs(
    query: str,
    file_ids: list[str] | None = None,
    limit: int = 20,
) -> list[tuple[Document, float, dict[str, Any]]]:
    hits = search_graph(query, file_ids=file_ids, limit=limit)
    if not hits:
        return []

    docs_by_file: dict[str, list[Document]] = {}
    results: list[tuple[Document, float, dict[str, Any]]] = []
    for hit in hits:
        file_id = hit.get("file_id")
        if not file_id:
            continue
        docs_by_file.setdefault(file_id, get_documents_by_file(file_id))
        chunk_index = hit.get("chunk_index")
        matched = None
        for doc in docs_by_file[file_id]:
            if (doc.metadata or {}).get("chunk_index") == chunk_index:
                matched = doc
                break
        if matched is None and docs_by_file[file_id]:
            matched = docs_by_file[file_id][0]
        if matched is not None:
            results.append((matched, float(hit.get("score", 0.0)), hit))
    return results


def hybrid_search(
    query: str,
    k: int,
    file_ids: list[str] | None = None,
    mode: str = "mix",
    candidate_multiplier: int = 4,
) -> RetrievalResult:
    candidate_k = max(k * candidate_multiplier, 20)
    mode = mode or "mix"

    vector_weight = 0.45
    keyword_weight = 0.35
    graph_weight = 0.20
    if mode == "local":
        vector_weight, keyword_weight, graph_weight = 0.25, 0.35, 0.40
    elif mode == "global":
        vector_weight, keyword_weight, graph_weight = 0.35, 0.25, 0.40
    elif mode in {"naive", "document"}:
        vector_weight, keyword_weight, graph_weight = 0.55, 0.40, 0.05

    documents: dict[tuple[str, Any, str], Document] = {}
    method_scores: dict[str, dict[tuple[str, Any, str], float]] = {
        "vector": {},
        "keyword": {},
        "graph": {},
    }
    method_details: dict[tuple[str, Any, str], set[str]] = defaultdict(set)
    graph_hits: dict[tuple[str, Any, str], dict[str, Any]] = {}

    for doc, distance in similarity_search_with_scores(query, k=candidate_k, file_ids=file_ids):
        copied = _copy_doc(doc)
        key = _doc_key(copied)
        documents[key] = copied
        score = 1.0 / (1.0 + max(float(distance), 0.0))
        method_scores["vector"][key] = max(method_scores["vector"].get(key, 0.0), score)
        method_details[key].add("vector")

    for doc, score in _keyword_search(query, file_ids=file_ids, limit=candidate_k):
        copied = _copy_doc(doc)
        key = _doc_key(copied)
        documents.setdefault(key, copied)
        method_scores["keyword"][key] = max(method_scores["keyword"].get(key, 0.0), score)
        method_details[key].add("keyword")

    if mode in {"local", "global", "hybrid", "mix"}:
        for doc, score, hit in _graph_search_docs(query, file_ids=file_ids, limit=candidate_k):
            copied = _copy_doc(doc)
            key = _doc_key(copied)
            documents.setdefault(key, copied)
            method_scores["graph"][key] = max(method_scores["graph"].get(key, 0.0), score)
            method_details[key].add("graph")
            graph_hits[key] = hit

    normalized = {method: _normalize_scores(scores) for method, scores in method_scores.items()}
    final_scores: dict[tuple[str, Any, str], float] = {}
    for key in documents:
        final_scores[key] = (
            vector_weight * normalized["vector"].get(key, 0.0)
            + keyword_weight * normalized["keyword"].get(key, 0.0)
            + graph_weight * normalized["graph"].get(key, 0.0)
        )

    ranked_keys = sorted(final_scores, key=lambda key: final_scores[key], reverse=True)
    ranked_docs: list[Document] = []
    debug: list[dict[str, Any]] = []
    for rank, key in enumerate(ranked_keys[:k], start=1):
        doc = documents[key]
        methods = sorted(method_details.get(key, []))
        doc.metadata["retrieval_score"] = round(final_scores[key], 4)
        doc.metadata["retrieval_methods"] = methods
        doc.metadata["vector_score"] = round(normalized["vector"].get(key, 0.0), 4)
        doc.metadata["keyword_score"] = round(normalized["keyword"].get(key, 0.0), 4)
        doc.metadata["graph_score"] = round(normalized["graph"].get(key, 0.0), 4)
        if key in graph_hits:
            doc.metadata["graph_matched_terms"] = graph_hits[key].get("matched_terms", [])
        ranked_docs.append(doc)
        debug.append(
            {
                "rank": rank,
                "file_id": key[0],
                "chunk_index": key[1],
                "file_name": doc.metadata.get("file_name") or doc.metadata.get("source"),
                "score": doc.metadata["retrieval_score"],
                "methods": methods,
                "vector_score": doc.metadata["vector_score"],
                "keyword_score": doc.metadata["keyword_score"],
                "graph_score": doc.metadata["graph_score"],
            }
        )

    return RetrievalResult(docs=ranked_docs, debug=debug)
