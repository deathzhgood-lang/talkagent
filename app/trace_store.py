import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import TRACE_DB_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _from_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _connect() -> sqlite3.Connection:
    Path(TRACE_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(TRACE_DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def initialize() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS trace_runs (
                trace_id TEXT PRIMARY KEY,
                conversation_id TEXT,
                question TEXT NOT NULL,
                status TEXT NOT NULL,
                route_mode TEXT,
                answer_label TEXT,
                answer_excerpt TEXT,
                error TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                duration_ms INTEGER
            );

            CREATE TABLE IF NOT EXISTS trace_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                duration_ms INTEGER,
                FOREIGN KEY(trace_id) REFERENCES trace_runs(trace_id)
            );

            CREATE TABLE IF NOT EXISTS trace_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                retrieval_query TEXT NOT NULL,
                rank INTEGER NOT NULL,
                file_id TEXT,
                file_name TEXT,
                chunk_index TEXT,
                score REAL,
                vector_score REAL,
                keyword_score REAL,
                graph_score REAL,
                methods TEXT NOT NULL,
                matched_terms TEXT NOT NULL,
                content TEXT NOT NULL,
                used_in_context INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(trace_id) REFERENCES trace_runs(trace_id)
            );

            CREATE INDEX IF NOT EXISTS idx_trace_runs_started_at
                ON trace_runs(started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_trace_candidates_trace_id
                ON trace_candidates(trace_id);
            """
        )


def start_run(question: str, conversation_id: str | None = None) -> str:
    initialize()
    trace_id = str(uuid.uuid4())
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO trace_runs(trace_id, conversation_id, question, status, started_at)
            VALUES (?, ?, ?, 'running', ?)
            """,
            (trace_id, conversation_id, question, _now()),
        )
    add_event(
        trace_id,
        stage="request_received",
        status="completed",
        summary="收到一次问答请求。",
        payload={"question_length": len(question)},
    )
    return trace_id


def add_event(
    trace_id: str,
    stage: str,
    status: str,
    summary: str,
    payload: dict[str, Any] | None = None,
    duration_ms: int | None = None,
) -> None:
    with _connect() as connection:
        sequence = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM trace_events WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO trace_events(
                trace_id, sequence, stage, status, summary, payload, created_at, duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                sequence,
                stage,
                status,
                summary,
                _json(payload or {}),
                _now(),
                duration_ms,
            ),
        )


def record_candidates(
    trace_id: str,
    retrieval_query: str,
    candidates: list[Any],
    context_documents: list[Any],
) -> None:
    context_keys = {
        _document_key(document)
        for document in context_documents
    }
    rows = []
    for rank, document in enumerate(candidates, start=1):
        metadata = document.metadata or {}
        rows.append(
            (
                trace_id,
                retrieval_query,
                rank,
                str(metadata.get("file_id", "")),
                str(metadata.get("file_name") or metadata.get("source") or ""),
                str(metadata.get("chunk_index", "")),
                metadata.get("retrieval_score"),
                metadata.get("vector_score"),
                metadata.get("keyword_score"),
                metadata.get("graph_score"),
                _json(metadata.get("retrieval_methods", [])),
                _json(metadata.get("graph_matched_terms", [])),
                (document.page_content or "")[:4000],
                int(_document_key(document) in context_keys),
            )
        )

    if not rows:
        return
    with _connect() as connection:
        connection.executemany(
            """
            INSERT INTO trace_candidates(
                trace_id, retrieval_query, rank, file_id, file_name, chunk_index, score,
                vector_score, keyword_score, graph_score, methods, matched_terms, content,
                used_in_context
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def complete_run(
    trace_id: str,
    *,
    route_mode: str | None = None,
    answer: str | None = None,
    error: str | None = None,
) -> None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT started_at FROM trace_runs WHERE trace_id = ?", (trace_id,)
        ).fetchone()
        if row is None:
            return
        started_at = datetime.fromisoformat(row["started_at"])
        duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        answer_text = answer or ""
        answer_label = _answer_label(answer_text)
        connection.execute(
            """
            UPDATE trace_runs
            SET status = ?, route_mode = ?, answer_label = ?, answer_excerpt = ?, error = ?,
                completed_at = ?, duration_ms = ?
            WHERE trace_id = ?
            """,
            (
                "failed" if error else "completed",
                route_mode,
                answer_label,
                answer_text[:1000],
                error,
                _now(),
                duration_ms,
                trace_id,
            ),
        )


def list_runs(search: str = "", limit: int = 50) -> list[dict[str, Any]]:
    initialize()
    keyword = f"%{search.strip()}%"
    safe_limit = max(1, min(limit, 200))
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT run.*,
                   (SELECT COUNT(*) FROM trace_candidates candidate
                    WHERE candidate.trace_id = run.trace_id) AS candidate_count
            FROM trace_runs run
            WHERE run.trace_id LIKE ?
               OR run.question LIKE ?
               OR EXISTS (
                    SELECT 1 FROM trace_candidates candidate
                    WHERE candidate.trace_id = run.trace_id
                      AND (candidate.file_name LIKE ? OR candidate.content LIKE ?)
               )
            ORDER BY run.started_at DESC
            LIMIT ?
            """,
            (keyword, keyword, keyword, keyword, safe_limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_run(trace_id: str) -> dict[str, Any] | None:
    initialize()
    with _connect() as connection:
        run = connection.execute(
            "SELECT * FROM trace_runs WHERE trace_id = ?", (trace_id,)
        ).fetchone()
        if run is None:
            return None
        events = connection.execute(
            "SELECT * FROM trace_events WHERE trace_id = ? ORDER BY sequence",
            (trace_id,),
        ).fetchall()
        candidates = connection.execute(
            """
            SELECT * FROM trace_candidates
            WHERE trace_id = ?
            ORDER BY retrieval_query, rank
            """,
            (trace_id,),
        ).fetchall()

    result = dict(run)
    result["events"] = [
        {
            **dict(event),
            "payload": _from_json(event["payload"], {}),
        }
        for event in events
    ]
    result["candidates"] = [
        {
            **dict(candidate),
            "methods": _from_json(candidate["methods"], []),
            "matched_terms": _from_json(candidate["matched_terms"], []),
            "used_in_context": bool(candidate["used_in_context"]),
        }
        for candidate in candidates
    ]
    return result


def _document_key(document: Any) -> tuple[str, str, str]:
    metadata = document.metadata or {}
    return (
        str(metadata.get("file_id", "")),
        str(metadata.get("chunk_index", "")),
        (document.page_content or "")[:80],
    )


def _answer_label(answer: str) -> str | None:
    labels = ("【通用回答】", "【基于文档】", "【综合回答】", "【缺少依据】")
    return next((label for label in labels if answer.startswith(label)), None)
