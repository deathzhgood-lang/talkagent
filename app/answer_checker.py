from typing import Any

from app.llm_client import extract_json_object, generate_text


def check_answer(
    question: str,
    answer: str,
    route: dict[str, Any],
    context: str,
) -> str:
    if route.get("mode") == "general":
        return answer

    prompt = f"""你是客服回答的事实自查器。请检查回答是否忠于参考文档。

自查规则：
- 如果回答包含文档没有支持的具体业务事实，请修正或删除。
- 如果遗漏了参考文档中的关键限制或关键事实，请补充。
- 如果问题在问“哪些参数/必选项/必填项/列表”，必须逐项检查参考文档中标注为“必选、必填、必须、required、是否必填=是、是否必选=是”的项目，不能漏项。
- 如果初稿漏掉了某个必选参数，请在 final_answer 中补全并说明“已补充遗漏项”。
- 通用建议可以保留，但不能伪装成文档事实。
- 输出严格 JSON，不要 Markdown 代码块。

JSON 格式：
{{
  "needs_revision": true/false,
  "final_answer": "修正后的最终回答"
}}

问题：
{question}

路由判断：
{route}

参考文档：
{context or "无"}

初稿回答：
{answer}
"""
    try:
        raw = generate_text(prompt, timeout=90)
        data = extract_json_object(raw) or {}
        final_answer = str(data.get("final_answer", "")).strip() or answer
        return _ensure_prefix(final_answer, route)
    except Exception:
        return _ensure_prefix(answer, route)


def _ensure_prefix(answer: str, route: dict[str, Any]) -> str:
    prefixes = ("【通用回答】", "【基于文档】", "【综合回答】", "【缺少依据】")
    if answer.strip().startswith(prefixes):
        return answer
    mode = route.get("mode")
    if mode == "general":
        prefix = "【通用回答】"
    elif mode == "hybrid":
        prefix = "【综合回答】"
    elif mode == "missing_evidence":
        prefix = "【缺少依据】"
    else:
        prefix = "【基于文档】"
    return f"{prefix}{answer}"
