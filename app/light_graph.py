import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from langchain_core.documents import Document

from app.config import DATA_DIR


GRAPH_DIR = Path(DATA_DIR) / "light_graph"
GRAPH_PATH = GRAPH_DIR / "index.json"

ASCII_TERM_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{1,}")
CJK_TERM_RE = re.compile(r"[\u4e00-\u9fff]{2,12}")
BACKTICK_TERM_RE = re.compile(r"`([^`]{2,80})`")

STOP_TERMS = {
    "http",
    "https",
    "true",
    "false",
    "none",
    "null",
    "string",
    "number",
    "object",
    "array",
    "file",
    "page",
}


def _empty_index() -> dict[str, Any]:
    return {
        "version": 1,
        "documents": {},
        "entities": {},
        "relations": [],
    }


def _read_index() -> dict[str, Any]:
    if not GRAPH_PATH.exists():
        return _empty_index()
    try:
        with open(GRAPH_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _empty_index()
    if not isinstance(data, dict):
        return _empty_index()
    data.setdefault("version", 1)
    data.setdefault("documents", {})
    data.setdefault("entities", {})
    data.setdefault("relations", [])
    return data


def _write_index(index: dict[str, Any]) -> None:
    os.makedirs(GRAPH_DIR, exist_ok=True)
    with open(GRAPH_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _normalize_term(term: str) -> str:
    term = re.sub(r"\s+", " ", term.strip(" `,.;:，。；：|/\\()[]{}<>"))
    return term[:80]


def _iter_terms(text: str) -> Iterable[str]:
    for match in BACKTICK_TERM_RE.finditer(text):
        yield _normalize_term(match.group(1))
    for match in ASCII_TERM_RE.finditer(text):
        yield _normalize_term(match.group(0))
    for match in CJK_TERM_RE.finditer(text):
        yield _normalize_term(match.group(0))


def extract_terms(text: str, limit: int = 24) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for term in _iter_terms(text):
        if len(term) < 2:
            continue
        key = term.lower()
        if key in STOP_TERMS or key in seen:
            continue
        seen.add(key)
        terms.append(term)
        if len(terms) >= limit:
            break
    return terms


def _chunk_index(metadata: dict[str, Any]) -> int | str:
    value = metadata.get("chunk_index", "")
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _relation_label(text: str) -> str:
    lowered = text.lower()
    if "使用" in text or "uses" in lowered or "use " in lowered:
        return "uses"
    if "包含" in text or "include" in lowered or "contains" in lowered:
        return "contains"
    if "依赖" in text or "depends" in lowered or "requires" in lowered:
        return "depends_on"
    if "用于" in text or "for " in lowered:
        return "used_for"
    return "related_to"


def _build_chunk_record(doc: Document) -> dict[str, Any]:
    text = doc.page_content or ""
    terms = extract_terms(text)
    entities = terms[:10]
    relations = []
    for left, right in zip(entities, entities[1:]):
        relations.append(
            {
                "source": left,
                "target": right,
                "type": _relation_label(text),
            }
        )
    return {
        "chunk_index": _chunk_index(doc.metadata or {}),
        "entities": entities,
        "keywords": terms,
        "relations": relations[:8],
        "snippet": text.replace("\n", " ").strip()[:240],
    }


def build_graph_for_document(
    file_id: str,
    file_name: str,
    chunks: list[Document],
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    index = _read_index()
    remove_document_from_graph(file_id, persist=False, index=index)

    chunk_records = [_build_chunk_record(chunk) for chunk in chunks]
    summary_terms = []
    if summary:
        summary_text = " ".join(
            str(value)
            for key in ("title", "topic", "can_answer", "key_facts", "tags")
            for value in (
                summary.get(key, [])
                if isinstance(summary.get(key), list)
                else [summary.get(key, "")]
            )
        )
        summary_terms = extract_terms(summary_text, limit=32)

    entity_counter: Counter[str] = Counter()
    for record in chunk_records:
        entity_counter.update(record["entities"])
    entity_counter.update(summary_terms)

    document_record = {
        "file_id": file_id,
        "file_name": file_name,
        "entities": [term for term, _count in entity_counter.most_common(64)],
        "chunks": chunk_records,
    }
    index["documents"][file_id] = document_record

    for entity, count in entity_counter.items():
        entity_info = index["entities"].setdefault(
            entity,
            {"name": entity, "mentions": [], "weight": 0.0},
        )
        entity_info["mentions"].append(
            {"file_id": file_id, "file_name": file_name, "count": count}
        )
        entity_info["weight"] = float(entity_info.get("weight", 0.0)) + math.log1p(count)

    for record in chunk_records:
        for relation in record["relations"]:
            index["relations"].append(
                {
                    **relation,
                    "file_id": file_id,
                    "file_name": file_name,
                    "chunk_index": record["chunk_index"],
                }
            )

    _write_index(index)
    return document_record


def remove_document_from_graph(
    file_id: str,
    persist: bool = True,
    index: dict[str, Any] | None = None,
) -> None:
    index = index or _read_index()
    index["documents"].pop(file_id, None)
    index["relations"] = [
        relation
        for relation in index.get("relations", [])
        if relation.get("file_id") != file_id
    ]

    entities: dict[str, Any] = {}
    for doc in index.get("documents", {}).values():
        for entity in doc.get("entities", []):
            info = entities.setdefault(entity, {"name": entity, "mentions": [], "weight": 0.0})
            count = sum(
                1
                for chunk in doc.get("chunks", [])
                if entity in chunk.get("entities", [])
            )
            info["mentions"].append(
                {
                    "file_id": doc.get("file_id"),
                    "file_name": doc.get("file_name"),
                    "count": count,
                }
            )
            info["weight"] += math.log1p(max(count, 1))
    index["entities"] = entities

    if persist:
        _write_index(index)


def _query_tokens(query: str) -> set[str]:
    tokens = {term.lower() for term in extract_terms(query, limit=32)}
    tokens.update(token.lower() for token in re.findall(r"[\w.-]{2,}", query))
    return tokens


def search_graph(
    query: str,
    file_ids: list[str] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    index = _read_index()
    allowed = set(file_ids or [])
    query_tokens = _query_tokens(query)
    if not query_tokens:
        return []

    hits: list[dict[str, Any]] = []
    for file_id, doc in index.get("documents", {}).items():
        if allowed and file_id not in allowed:
            continue
        for chunk in doc.get("chunks", []):
            chunk_terms = {term.lower() for term in chunk.get("keywords", [])}
            entity_terms = {term.lower() for term in chunk.get("entities", [])}
            overlap = query_tokens & chunk_terms
            entity_overlap = query_tokens & entity_terms
            if not overlap and not entity_overlap:
                continue
            score = len(overlap) + len(entity_overlap) * 2
            hits.append(
                {
                    "file_id": file_id,
                    "file_name": doc.get("file_name"),
                    "chunk_index": chunk.get("chunk_index"),
                    "score": float(score),
                    "matched_terms": sorted(overlap | entity_overlap),
                    "snippet": chunk.get("snippet", ""),
                }
            )

    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[:limit]


def get_graph_stats() -> dict[str, int]:
    index = _read_index()
    return {
        "documents": len(index.get("documents", {})),
        "entities": len(index.get("entities", {})),
        "relations": len(index.get("relations", [])),
    }
