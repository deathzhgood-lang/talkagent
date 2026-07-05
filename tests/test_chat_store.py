from app import chat_store


def test_chat_store_persists_messages_and_recent_history(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_store, "CONVERSATIONS_DIR", str(tmp_path))

    conversation = chat_store.create_conversation(title="测试会话")
    conversation_id = conversation["id"]

    chat_store.add_message(conversation_id, "user", "什么是 RAG？")
    chat_store.add_message(
        conversation_id,
        "assistant",
        "【通用回答】RAG 是检索增强生成。",
        sources=[{"file_name": "demo.md", "chunk_index": 0, "snippet": "RAG"}],
    )

    loaded = chat_store.get_conversation(conversation_id)
    assert loaded is not None
    assert loaded["title"] == "测试会话"
    assert len(loaded["messages"]) == 2
    assert loaded["messages"][1]["sources"][0]["file_name"] == "demo.md"

    history = chat_store.format_recent_history(conversation_id, rounds=1)
    assert "用户: 什么是 RAG？" in history
    assert "助手: 【通用回答】RAG 是检索增强生成。" in history


def test_list_conversations_orders_by_updated_time(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_store, "CONVERSATIONS_DIR", str(tmp_path))
    times = iter(
        [
            "2026-06-23T10:00:00",
            "2026-06-23T10:00:00",
            "2026-06-23T10:00:00",
            "2026-06-23T10:00:01",
            "2026-06-23T10:00:01",
            "2026-06-23T10:00:01",
            "2026-06-23T10:00:02",
            "2026-06-23T10:00:02",
            "2026-06-23T10:00:02",
        ]
    )
    monkeypatch.setattr(chat_store, "_now", lambda: next(times))

    first = chat_store.create_conversation(title="first")
    second = chat_store.create_conversation(title="second")
    chat_store.add_message(second["id"], "user", "更新第二个会话")

    conversations = chat_store.list_conversations()
    assert conversations[0]["id"] == second["id"]
    assert {item["id"] for item in conversations} == {first["id"], second["id"]}
