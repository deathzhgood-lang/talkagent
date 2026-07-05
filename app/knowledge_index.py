import json
import os
import re
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from app.config import KNOWLEDGE_INDEX_DIR
from app.llm_client import extract_json_object, generate_text


INDEX_JSON = Path(KNOWLEDGE_INDEX_DIR) / "index.json"


def _read_index() -> dict[str, Any]:
    if not INDEX_JSON.exists():
        return {"documents": []}
    with open(INDEX_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_index(index: dict[str, Any]) -> None:
    os.makedirs(KNOWLEDGE_INDEX_DIR, exist_ok=True)
    with open(INDEX_JSON, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _sample_text(chunks: list[Document], limit: int = 6000) -> str:
    parts = []
    total = 0
    for chunk in chunks:
        text = chunk.page_content.strip()
        if not text:
            continue
        remaining = limit - total
        if remaining <= 0:
            break
        parts.append(text[:remaining])
        total += len(parts[-1])
    return "\n\n".join(parts)


def _fallback_summary(file_name: str, chunks: list[Document]) -> dict[str, Any]:
    text = _sample_text(chunks, limit=1600)
    words = re.findall(r"[\u4e00-\u9fffA-Za-z0-9_./:-]{2,}", text)
    tags = []
    for word in words:
        if word not in tags:
            tags.append(word)
        if len(tags) >= 12:
            break
    return {
        "title": file_name,
        "topic": text[:120] or "空文档",
        "can_answer": tags[:8],
        "key_facts": [],
        "limits": [],
        "tags": tags,
    }


def summarize_document(file_id: str, file_name: str, chunks: list[Document]) -> dict[str, Any]:
    sample = _sample_text(chunks)
    if not sample:
        summary = _fallback_summary(file_name, chunks)
    else:
        prompt = f"""请为客服知识库中的文档生成结构化摘要。

要求：
- 只根据给出的文档内容总结，不要编造。
- 输出严格 JSON，不要 Markdown 代码块。
- 字段包括 title, topic, can_answer, key_facts, limits, tags。
- can_answer/key_facts/limits/tags 都是字符串数组。
- 如果文档包含接口参数、字段表、请求参数、必选/必填项，请在 key_facts 中逐项列出所有必选参数，格式例如：“必选参数：prompt - 提示词”。
- 不要只列公共参数；业务参数中的必填项也必须列入 key_facts。

文件名：{file_name}
文档内容：
{sample}
"""
        try:
            raw = generate_text(prompt, timeout=120)
            summary = extract_json_object(raw) or _fallback_summary(file_name, chunks)
        except Exception:
            summary = _fallback_summary(file_name, chunks)

    summary["file_id"] = file_id
    summary["file_name"] = file_name
    _save_document_summary(summary)
    rebuild_global_index(summary)
    return summary


def _save_document_summary(summary: dict[str, Any]) -> None:
    path = Path(KNOWLEDGE_INDEX_DIR) / f"{summary['file_id']}.md"
    lines = [
        f"# 文档：{summary.get('file_name', summary.get('title', '未知文档'))}",
        "",
        f"- 文档ID：{summary['file_id']}",
        f"- 主题：{summary.get('topic', '')}",
        "",
        "## 可回答的问题",
    ]
    lines.extend(f"- {item}" for item in summary.get("can_answer", []))
    lines.extend(["", "## 关键事实"])
    lines.extend(f"- {item}" for item in summary.get("key_facts", []))
    lines.extend(["", "## 重要限制"])
    lines.extend(f"- {item}" for item in summary.get("limits", []))
    lines.extend(["", "## 检索标签", ", ".join(summary.get("tags", []))])
    path.write_text("\n".join(lines), encoding="utf-8")


def rebuild_global_index(latest_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    index = _read_index()
    documents = index.get("documents", [])
    if latest_summary:
        documents = [doc for doc in documents if doc.get("file_id") != latest_summary.get("file_id")]
        documents.append(
            {
                "file_id": latest_summary["file_id"],
                "file_name": latest_summary.get("file_name", ""),
                "topic": latest_summary.get("topic", ""),
                "can_answer": latest_summary.get("can_answer", []),
                "key_facts": latest_summary.get("key_facts", [])[:8],
                "limits": latest_summary.get("limits", [])[:5],
                "tags": latest_summary.get("tags", []),
            }
        )
    index = {"documents": documents}
    _write_index(index)
    return index


def remove_document_from_index(file_id: str) -> None:
    index = _read_index()
    index["documents"] = [doc for doc in index.get("documents", []) if doc.get("file_id") != file_id]
    _write_index(index)
    path = Path(KNOWLEDGE_INDEX_DIR) / f"{file_id}.md"
    if path.exists():
        path.unlink()


def get_directory_text() -> str:
    index = _read_index()
    documents = index.get("documents", [])
    if not documents:
        return "当前知识库目录为空。"
    lines = ["# 知识库目录"]
    for doc in documents:
        lines.extend(
            [
                "",
                f"## {doc.get('file_name', '未知文档')}",
                f"- 文档ID：{doc.get('file_id', '')}",
                f"- 主题：{doc.get('topic', '')}",
                f"- 适合回答：{'；'.join(doc.get('can_answer', []))}",
                f"- 关键事实：{'；'.join(doc.get('key_facts', []))}",
                f"- 标签：{', '.join(doc.get('tags', []))}",
            ]
        )
    return "\n".join(lines)


def get_document_summaries(file_ids: list[str]) -> str:
    parts = []
    for file_id in file_ids:
        path = Path(KNOWLEDGE_INDEX_DIR) / f"{file_id}.md"
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)
