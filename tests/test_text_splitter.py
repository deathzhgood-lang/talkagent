from langchain_core.documents import Document

from app.text_splitter import split_documents


def test_split_documents_assigns_chunk_index():
    text = "第一段介绍 RAG 系统。第二段介绍文档分块。第三段介绍向量检索。"
    chunks = split_documents([Document(page_content=text)], chunk_size=18, chunk_overlap=4)

    assert len(chunks) > 1
    assert [chunk.metadata["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.page_content.strip() for chunk in chunks)

