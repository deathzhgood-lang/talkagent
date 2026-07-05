import re
from typing import Any
from urllib.error import HTTPError

from app import chat_store
from app.answer_checker import check_answer
from app.config import CHAT_HISTORY_ROUNDS, RETRIEVAL_K
from app.hybrid_retrieval import RetrievalResult, hybrid_search
from app.knowledge_index import get_document_summaries
from app.llm_client import generate_text
from app.question_router import route_question


ANSWER_PROMPT = """你是一个可工作的 AI 客服助手。

你需要根据路由结果回答：
- general：直接使用通用知识回答，不要假装来自文档。
- document：必须依据参考文档和检索片段回答，不要编造文档外的业务事实。
- hybrid：文档事实以参考文档为准，解释、方案设计、步骤建议可以结合通用知识。
- missing_evidence：说明文档中未找到相关依据，不要编造具体业务事实；可以给出通用建议或建议用户补充资料。

回答开头必须使用其中一个标签：
【通用回答】、【基于文档】、【综合回答】、【缺少依据】
"""


def _format_context(docs: list[Any]) -> str:
    parts = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}
        source = meta.get("file_name") or meta.get("source") or "未知文件"
        chunk_index = meta.get("chunk_index", "未知片段")
        parts.append(f"[{i}] 来源: {source}, 片段: {chunk_index}\n{doc.page_content}")
    return "\n\n".join(parts)


def _format_sources(docs: list[Any]) -> list[dict[str, Any]]:
    sources = []
    for doc in docs[:5]:
        meta = doc.metadata or {}
        text = doc.page_content.replace("\n", " ").strip()
        sources.append(
            {
                "file_name": meta.get("file_name") or meta.get("source") or "未知文件",
                "chunk_index": meta.get("chunk_index"),
                "score": meta.get("retrieval_score"),
                "methods": meta.get("retrieval_methods", []),
                "vector_score": meta.get("vector_score"),
                "keyword_score": meta.get("keyword_score"),
                "graph_score": meta.get("graph_score"),
                "snippet": text[:180],
            }
        )
    return sources


def _retrieval_mode(route: dict[str, Any]) -> str:
    mode = route.get("mode") or "mix"
    if mode == "document":
        return "naive"
    if mode == "hybrid":
        return "mix"
    if mode in {"naive", "local", "global", "mix"}:
        return mode
    return "mix"


def _retrieve_for_route(question: str, route: dict[str, Any]) -> RetrievalResult:
    if not route.get("needs_documents"):
        return RetrievalResult(docs=[], debug=[])
    file_ids = route.get("relevant_file_ids") or None
    queries = _expanded_queries(question)
    docs: list[Any] = []
    debug: list[dict[str, Any]] = []
    seen: set[tuple[str, Any, str]] = set()
    k = max(RETRIEVAL_K, 10) if _is_enumeration_question(question) else RETRIEVAL_K
    mode = _retrieval_mode(route)
    for query in queries:
        result = hybrid_search(query, k=k, file_ids=file_ids, mode=mode)
        for item in result.debug:
            item = dict(item)
            item["query"] = query
            item["mode"] = mode
            debug.append(item)
        for doc in result.docs:
            meta = doc.metadata or {}
            key = (
                meta.get("file_id", ""),
                meta.get("chunk_index", ""),
                doc.page_content[:80],
            )
            if key in seen:
                continue
            seen.add(key)
            docs.append(doc)
    return RetrievalResult(docs=docs[: max(k, RETRIEVAL_K)], debug=debug)


def _is_enumeration_question(question: str) -> bool:
    keywords = ["哪些", "哪几个", "列表", "参数", "必选", "必填", "必须", "required", "require"]
    return any(keyword.lower() in question.lower() for keyword in keywords)


def _expanded_queries(question: str) -> list[str]:
    queries = [question]
    if _is_enumeration_question(question):
        queries.extend(
            [
                f"{question} 必选 参数 必填 required 是否必填 是否必选 字段",
                f"{question} prompt Action Version req_key image_urls callback_url 参数表",
                "必选参数 必填参数 required 参数 字段 prompt",
            ]
        )
    return queries


def _sources_for_answer(answer: str, docs: list[Any]) -> list[dict[str, Any]]:
    if not docs:
        return []
    normalized = answer.strip()
    if normalized.startswith("【通用回答】") or normalized.startswith("【缺少依据】"):
        return []
    return _format_sources(docs)


def _normalize_answer_label(answer: str, route: dict[str, Any]) -> str:
    labels = ("【通用回答】", "【基于文档】", "【综合回答】", "【缺少依据】")
    stripped = answer.strip()
    body = stripped
    for label in labels:
        if stripped.startswith(label):
            body = stripped[len(label) :].lstrip()
            break

    mode = route.get("mode")
    if mode == "general":
        label = "【通用回答】"
    elif mode in {"hybrid", "mix", "global"}:
        label = "【综合回答】"
    elif mode == "missing_evidence":
        label = "【缺少依据】"
    else:
        label = "【基于文档】"
    return f"{label}{body}"


def _extract_required_items(docs: list[Any]) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    seen: set[str] = set()
    required_words = ("必选", "必填", "必须", "required", "Required", "是")

    for doc in docs:
        for raw_line in doc.page_content.splitlines():
            line = raw_line.strip().strip("|").strip()
            if not line or not any(word in line for word in required_words):
                continue

            candidates: list[str] = []
            match = re.match(r"^`?([A-Za-z_][A-Za-z0-9_.-]*)`?\s*[：:]\s*(必选|必填|必须|required|Required)", line)
            if match:
                candidates.append(match.group(1))

            if "|" in raw_line:
                cells = [cell.strip(" `") for cell in raw_line.split("|") if cell.strip()]
                if cells and any(word in raw_line for word in ("必选", "必填", "required", "Required", "是")):
                    candidates.append(cells[0])

            for token in re.findall(r"`([A-Za-z_][A-Za-z0-9_.-]*)`", line):
                candidates.append(token)

            for name in candidates:
                if not name or name.lower() in {"参数", "字段", "name", "参数名"}:
                    continue
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                items.append((name, line))
    return items


def _is_required_parameter_question(question: str) -> bool:
    q = question.lower()
    if any(word in q for word in ("required", "must", "mandatory")) and any(
        word in q for word in ("parameter", "parameters", "field", "fields", "api")
    ):
        return True
    return any(word in q for word in ("必选", "必填", "必须", "required")) and any(
        word in q for word in ("参数", "字段", "接口", "哪些", "哪几个")
    )


def _enforce_required_items(question: str, answer: str, route: dict[str, Any], docs: list[Any]) -> str:
    if not docs or not _is_required_parameter_question(question):
        return answer
    items = _extract_required_items(docs)
    if not items:
        return answer

    missing = [name for name, _line in items if name not in answer]
    has_optional_as_required = any(word in answer for word in ("seed", "width", "height")) and not any(
        name.lower() in {"seed", "width", "height"} for name, _line in items
    )
    if not missing and not has_optional_as_required:
        return answer

    lines = ["【基于文档】根据文档，必选参数包括："]
    for index, (name, source_line) in enumerate(items, start=1):
        lines.append(f"{index}. **{name}**：{source_line}")
    lines.append("\n以上为从文档中标注为“必选/必填/必须/required”的参数抽取结果。")
    return "\n".join(lines)


def answer_question(question: str, conversation_id: str | None = None) -> dict[str, Any]:
    history = chat_store.format_recent_history(conversation_id, CHAT_HISTORY_ROUNDS)
    route = route_question(question, history)
    retrieval = _retrieve_for_route(question, route)
    docs = retrieval.docs
    doc_context = _format_context(docs)
    doc_summaries = get_document_summaries(route.get("relevant_file_ids", []))

    prompt = f"""{ANSWER_PROMPT}

历史对话：
{history or "无"}

路由结果：
{route}

相关文档摘要：
{doc_summaries or "无"}

检索片段：
{doc_context or "无"}

用户问题：
{question}

请给出最终回答："""

    try:
        answer = generate_text(prompt, timeout=120)
        check_context = "\n\n".join(part for part in [doc_summaries, doc_context] if part)
        answer = check_answer(question, answer, route, check_context)
        answer = _normalize_answer_label(answer, route)
        answer = _enforce_required_items(question, answer, route, docs)
    except Exception as exc:
        reason = str(exc)
        if isinstance(exc, HTTPError):
            reason = f"HTTP {exc.code}: {exc.reason}"
        if docs:
            answer = (
                "【缺少依据】本地大模型暂时不可用，先返回检索到的相关文档片段摘要。\n\n"
                f"不可用原因: {reason}\n\n"
                + "\n\n".join(doc.page_content[:500] for doc in docs[:2])
            )
        else:
            answer = f"【缺少依据】本地大模型暂时不可用，且没有可参考的文档内容。\n\n不可用原因: {reason}"

    return {
        "answer": answer,
        "sources": _sources_for_answer(answer, docs),
        "conversation_id": conversation_id,
        "route": route,
        "retrieval_debug": retrieval.debug,
    }
