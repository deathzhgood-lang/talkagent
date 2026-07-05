from langchain_core.documents import Document

from app import light_graph


def test_light_graph_build_search_and_remove(tmp_path, monkeypatch):
    graph_path = tmp_path / "light_graph" / "index.json"
    monkeypatch.setattr(light_graph, "GRAPH_DIR", graph_path.parent)
    monkeypatch.setattr(light_graph, "GRAPH_PATH", graph_path)

    chunks = [
        Document(
            page_content="TalkAgent uses ChromaDB for vector retrieval.",
            metadata={"chunk_index": 0},
        )
    ]

    light_graph.build_graph_for_document("file-1", "demo.md", chunks)
    hits = light_graph.search_graph("ChromaDB retrieval")

    assert hits
    assert hits[0]["file_id"] == "file-1"
    assert hits[0]["chunk_index"] == 0

    light_graph.remove_document_from_graph("file-1")

    assert light_graph.search_graph("ChromaDB retrieval") == []
