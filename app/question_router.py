from typing import Any

from app.knowledge_index import get_directory_text
from app.llm_client import extract_json_object, generate_text


DOCUMENT_MODES = {"document", "hybrid", "naive", "local", "global", "mix"}
STRICT_DOCUMENT_MODES = {"document", "hybrid", "local"}
VALID_MODES = {"general", "missing_evidence", *DOCUMENT_MODES}


def route_question(question: str, history: str = "") -> dict[str, Any]:
    directory = get_directory_text()
    prompt = f"""你是客服智能体的问题路由器。请根据用户问题和知识库目录判断是否需要查文档。

模式说明：
- general：通用知识、技术概念、一般建议，不需要文档。
- document：必须依据文档回答的问题，例如产品政策、价格、合同、售后、联系方式、业务规则。
- hybrid：需要结合文档事实和通用知识进行分析/方案设计。
- missing_evidence：问题需要业务依据，但目录中没有看起来相关的文档。

请输出严格 JSON：
{{
  "mode": "general|naive|local|global|mix|document|hybrid|missing_evidence",
  "needs_documents": true/false,
  "relevant_file_ids": ["..."],
  "reason": "一句话说明判断原因",
  "can_use_general_knowledge": true/false
}}

历史对话：
{history or "无"}

知识库目录：
{directory}

用户问题：
{question}
"""
    try:
        raw = generate_text(prompt, timeout=90)
        data = extract_json_object(raw) or {}
        return _normalize_route(data)
    except Exception:
        return _fallback_route(question, directory)


def _normalize_route(data: dict[str, Any]) -> dict[str, Any]:
    mode = str(data.get("mode", "general")).strip()
    if mode not in VALID_MODES:
        mode = "general"
    file_ids = data.get("relevant_file_ids") or []
    if not isinstance(file_ids, list):
        file_ids = []
    file_ids = [str(item) for item in file_ids if item]
    needs_documents = bool(data.get("needs_documents", mode in DOCUMENT_MODES))
    if mode == "general":
        needs_documents = False
        file_ids = []
    if mode == "missing_evidence" and file_ids:
        mode = "document"
        needs_documents = True
    if mode in STRICT_DOCUMENT_MODES and not file_ids:
        mode = "missing_evidence"
        needs_documents = False
    return {
        "mode": mode,
        "needs_documents": needs_documents,
        "relevant_file_ids": file_ids,
        "reason": str(data.get("reason", "")),
        "can_use_general_knowledge": bool(data.get("can_use_general_knowledge", mode in {"general", "hybrid", "global", "mix"})),
    }


def _fallback_route(question: str, directory: str) -> dict[str, Any]:
    business_terms = [
        "价格",
        "电话",
        "售后",
        "退货",
        "合同",
        "订单",
        "发票",
        "政策",
        "流程",
        "地址",
        "质保",
        "保修",
    ]
    needs_docs = any(term in question for term in business_terms)
    return {
        "mode": "document" if needs_docs and "文档ID：" in directory else "general",
        "needs_documents": needs_docs and "文档ID：" in directory,
        "relevant_file_ids": [],
        "reason": "路由模型不可用，使用关键词兜底判断。",
        "can_use_general_knowledge": not needs_docs,
    }
