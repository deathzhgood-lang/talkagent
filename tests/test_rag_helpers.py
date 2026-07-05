import importlib
from types import ModuleType, SimpleNamespace


def _load_rag_chain(monkeypatch):
    fake_vector_store = ModuleType("app.vector_store")
    fake_vector_store.similarity_search = lambda *args, **kwargs: []
    monkeypatch.setitem(importlib.import_module("sys").modules, "app.vector_store", fake_vector_store)
    return importlib.import_module("app.rag_chain")


def test_normalize_answer_label_matches_route(monkeypatch):
    rag_chain = _load_rag_chain(monkeypatch)

    answer = rag_chain._normalize_answer_label("【通用回答】可以结合文档和经验分析。", {"mode": "hybrid"})

    assert answer.startswith("【综合回答】")
    assert "可以结合文档和经验分析。" in answer


def test_sources_are_hidden_for_general_answers(monkeypatch):
    rag_chain = _load_rag_chain(monkeypatch)
    doc = SimpleNamespace(
        page_content="这是一段文档内容。",
        metadata={"file_name": "demo.md", "chunk_index": 0},
    )

    assert rag_chain._sources_for_answer("【通用回答】这是通用解释。", [doc]) == []

    sources = rag_chain._sources_for_answer("【基于文档】这是文档解释。", [doc])
    assert sources == [{"file_name": "demo.md", "chunk_index": 0, "snippet": "这是一段文档内容。"}]


def test_required_parameter_answer_can_be_enforced(monkeypatch):
    rag_chain = _load_rag_chain(monkeypatch)
    doc = SimpleNamespace(
        page_content=(
            "| 参数 | 类型 | 是否必填 |\n"
            "| prompt | string | 必填 |\n"
            "| req_key | string | 必填 |\n"
        ),
        metadata={},
    )

    answer = rag_chain._enforce_required_items(
        "这个接口有哪些必填参数？",
        "【基于文档】必填参数包括 prompt。",
        {"mode": "document"},
        [doc],
    )

    assert "prompt" in answer
    assert "req_key" in answer
    assert answer.startswith("【基于文档】")

