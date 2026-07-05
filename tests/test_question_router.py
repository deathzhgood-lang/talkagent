from app.question_router import _normalize_route


def test_general_route_clears_document_fields():
    route = _normalize_route(
        {
            "mode": "general",
            "needs_documents": True,
            "relevant_file_ids": ["file-1"],
            "reason": "通用概念问题",
        }
    )

    assert route["mode"] == "general"
    assert route["needs_documents"] is False
    assert route["relevant_file_ids"] == []
    assert route["can_use_general_knowledge"] is True


def test_document_route_without_file_ids_becomes_missing_evidence():
    route = _normalize_route(
        {
            "mode": "document",
            "needs_documents": True,
            "relevant_file_ids": [],
            "reason": "需要文档依据但没有匹配文档",
        }
    )

    assert route["mode"] == "missing_evidence"
    assert route["needs_documents"] is False


def test_missing_evidence_with_file_ids_promotes_to_document_route():
    route = _normalize_route(
        {
            "mode": "missing_evidence",
            "needs_documents": False,
            "relevant_file_ids": ["file-1"],
        }
    )

    assert route["mode"] == "document"
    assert route["needs_documents"] is True
    assert route["relevant_file_ids"] == ["file-1"]


def test_mix_route_is_supported():
    route = _normalize_route(
        {
            "mode": "mix",
            "needs_documents": True,
            "relevant_file_ids": ["file-1"],
        }
    )

    assert route["mode"] == "mix"
    assert route["needs_documents"] is True
    assert route["can_use_general_knowledge"] is True


def test_mix_route_without_file_ids_can_search_all_documents():
    route = _normalize_route(
        {
            "mode": "mix",
            "needs_documents": True,
            "relevant_file_ids": [],
        }
    )

    assert route["mode"] == "mix"
    assert route["needs_documents"] is True
    assert route["relevant_file_ids"] == []
