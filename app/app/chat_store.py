import json
import os
import uuid
from datetime import datetime
from typing import Any

from app.config import CONVERSATIONS_DIR


DEFAULT_TITLE = "新对话"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _path(conversation_id: str) -> str:
    return os.path.join(CONVERSATIONS_DIR, f"{conversation_id}.json")


def create_conversation(title: str | None = None) -> dict[str, Any]:
    conversation_id = str(uuid.uuid4())
    conversation = {
        "id": conversation_id,
        "title": title or DEFAULT_TITLE,
        "created_at": _now(),
        "updated_at": _now(),
        "messages": [],
    }
    save_conversation(conversation)
    return conversation


def save_conversation(conversation: dict[str, Any]) -> None:
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)
    conversation["updated_at"] = _now()
    with open(_path(conversation["id"]), "w", encoding="utf-8") as f:
        json.dump(conversation, f, ensure_ascii=False, indent=2)


def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    path = _path(conversation_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_conversations() -> list[dict[str, Any]]:
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)
    conversations: list[dict[str, Any]] = []
    for name in os.listdir(CONVERSATIONS_DIR):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(CONVERSATIONS_DIR, name), "r", encoding="utf-8") as f:
            data = json.load(f)
        conversations.append(
            {
                "id": data["id"],
                "title": data.get("title", "未命名对话"),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "message_count": len(data.get("messages", [])),
            }
        )
    return sorted(conversations, key=lambda item: item.get("updated_at", ""), reverse=True)


def delete_conversation(conversation_id: str) -> bool:
    path = _path(conversation_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    conversation = get_conversation(conversation_id)
    if conversation is None:
        title = content[:30] if role == "user" else DEFAULT_TITLE
        conversation = create_conversation(title=title)
        conversation_id = conversation["id"]

    if conversation.get("title") == DEFAULT_TITLE and role == "user":
        conversation["title"] = content[:30]

    message: dict[str, Any] = {
        "role": role,
        "content": content,
        "timestamp": _now(),
    }
    if sources is not None:
        message["sources"] = sources
    conversation.setdefault("messages", []).append(message)
    save_conversation(conversation)
    return conversation


def format_recent_history(conversation_id: str | None, rounds: int) -> str:
    if not conversation_id:
        return ""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        return ""
    messages = conversation.get("messages", [])[-rounds * 2 :]
    lines = []
    for message in messages:
        role = "用户" if message.get("role") == "user" else "助手"
        lines.append(f"{role}: {message.get('content', '')}")
    return "\n".join(lines)
