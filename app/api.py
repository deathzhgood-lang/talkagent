from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app import chat_store
from app import trace_store
from app.document_loader import load_file_from_bytes
from app.hybrid_retrieval import hybrid_search
from app.knowledge_index import remove_document_from_index, summarize_document
from app.light_graph import build_graph_for_document, remove_document_from_graph
from app.rag_chain import answer_question
from app.text_splitter import split_documents
from app.vector_store import add_documents, delete_by_file, get_all_files, get_index_embedding_status, get_stats


router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class RetrievalTestRequest(BaseModel):
    query: str
    mode: str = "mix"
    file_ids: list[str] | None = None
    top_k: int = 8


@router.post("/upload")
async def upload_documents(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    uploaded = []
    for file in files:
        content = await file.read()
        docs = load_file_from_bytes(content, file.filename or "uploaded.txt")
        chunks = split_documents(docs)
        file_id = add_documents(chunks, file.filename or "uploaded.txt")
        summary = summarize_document(file_id, file.filename or "uploaded.txt", chunks)
        build_graph_for_document(file_id, file.filename or "uploaded.txt", chunks, summary)
        uploaded.append(
            {
                "file_id": file_id,
                "file_name": file.filename,
                "chunk_count": len(chunks),
            }
        )
    return {"uploaded": uploaded}


@router.get("/documents")
def documents() -> dict[str, Any]:
    return {"documents": get_all_files(), "stats": get_stats()}


@router.delete("/documents/{file_id}")
def delete_document(file_id: str) -> dict[str, Any]:
    deleted = delete_by_file(file_id)
    remove_document_from_index(file_id)
    remove_document_from_graph(file_id)
    return {"deleted_chunks": deleted}


@router.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    conversation_id = request.conversation_id
    if not conversation_id:
        conversation = chat_store.create_conversation(title=request.message[:30])
        conversation_id = conversation["id"]

    chat_store.add_message(conversation_id, "user", request.message)
    result = answer_question(request.message, conversation_id)
    chat_store.add_message(
        conversation_id,
        "assistant",
        result["answer"],
        sources=result.get("sources", []),
    )
    result["conversation_id"] = conversation_id
    return result


@router.post("/retrieval-test")
def retrieval_test(request: RetrievalTestRequest) -> dict[str, Any]:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query cannot be empty")
    top_k = max(1, min(request.top_k, 20))
    result = hybrid_search(
        request.query,
        k=top_k,
        file_ids=request.file_ids,
        mode=request.mode,
    )
    chunks = []
    for doc in result.docs:
        meta = doc.metadata or {}
        chunks.append(
            {
                "file_id": meta.get("file_id"),
                "file_name": meta.get("file_name") or meta.get("source"),
                "chunk_index": meta.get("chunk_index"),
                "score": meta.get("retrieval_score"),
                "methods": meta.get("retrieval_methods", []),
                "vector_score": meta.get("vector_score"),
                "vector_confidence": meta.get("vector_confidence"),
                "keyword_score": meta.get("keyword_score"),
                "graph_score": meta.get("graph_score"),
                "snippet": (doc.page_content or "").replace("\n", " ")[:240],
            }
        )
    return {"chunks": chunks, "debug": result.debug}


@router.get("/system-status")
def system_status() -> dict[str, Any]:
    return {"knowledge_base": get_stats(), "embedding": get_index_embedding_status()}


@router.get("/traces")
def traces(search: str = "", limit: int = 50) -> dict[str, Any]:
    """Search local audit traces by question, file name, or candidate text."""
    return {"traces": trace_store.list_runs(search=search, limit=limit)}


@router.get("/traces/{trace_id}")
def trace_detail(trace_id: str) -> dict[str, Any]:
    trace = trace_store.get_run(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return trace


@router.get("/conversations")
def conversations() -> dict[str, Any]:
    return {"conversations": chat_store.list_conversations()}


@router.get("/conversations/{conversation_id}")
def conversation_detail(conversation_id: str) -> dict[str, Any]:
    conversation = chat_store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conversation


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict[str, Any]:
    deleted = chat_store.delete_conversation(conversation_id)
    return {"deleted": deleted}
