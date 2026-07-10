from langchain_core.documents import Document

from app import trace_store
from app import rag_chain


def test_trace_store_records_searchable_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(trace_store, "TRACE_DB_PATH", str(tmp_path / "traces.sqlite3"))

    trace_id = trace_store.start_run("How does the refund policy work?", "chat-1")
    trace_store.add_event(
        trace_id,
        stage="route_decided",
        status="completed",
        summary="Selected document retrieval.",
        payload={"mode": "document", "reason": "policy question"},
        duration_ms=12,
    )
    candidate = Document(
        page_content="Refund requests are accepted within seven days.",
        metadata={
            "file_id": "file-1",
            "file_name": "refund-policy.md",
            "chunk_index": 2,
            "retrieval_score": 0.81,
            "vector_score": 0.75,
            "keyword_score": 1.0,
            "graph_score": 0.0,
            "retrieval_methods": ["keyword", "vector"],
        },
    )
    trace_store.record_candidates(trace_id, "refund policy", [candidate], [candidate])
    trace_store.complete_run(trace_id, route_mode="document", answer="【基于文档】Seven days.")

    records = trace_store.list_runs(search="seven days")
    assert [record["trace_id"] for record in records] == [trace_id]
    assert records[0]["candidate_count"] == 1

    trace = trace_store.get_run(trace_id)
    assert trace is not None
    assert trace["status"] == "completed"
    assert trace["events"][1]["payload"]["mode"] == "document"
    assert trace["candidates"][0]["used_in_context"] is True
    assert trace["candidates"][0]["methods"] == ["keyword", "vector"]


def test_answer_question_persists_an_auditable_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(trace_store, "TRACE_DB_PATH", str(tmp_path / "traces.sqlite3"))
    monkeypatch.setattr(rag_chain.chat_store, "format_recent_history", lambda *_args: "")
    monkeypatch.setattr(
        rag_chain,
        "route_question",
        lambda *_args: {
            "mode": "general",
            "needs_documents": False,
            "relevant_file_ids": [],
            "reason": "General knowledge request.",
            "can_use_general_knowledge": True,
        },
    )
    monkeypatch.setattr(rag_chain, "generate_text", lambda *_args, **_kwargs: "A concise answer.")

    result = rag_chain.answer_question("What is RAG?", "chat-1")

    trace = trace_store.get_run(result["trace_id"])
    assert trace is not None
    assert trace["status"] == "completed"
    assert [event["stage"] for event in trace["events"]] == [
        "request_received",
        "history_compiled",
        "route_decided",
        "retrieval_completed",
        "context_built",
        "answer_generated",
        "answer_checked",
        "response_completed",
    ]
