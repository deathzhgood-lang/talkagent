from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app import chat_store
from app.document_loader import load_file_from_bytes
from app.knowledge_index import remove_document_from_index, summarize_document
from app.rag_chain import answer_question
from app.text_splitter import split_documents
from app.vector_store import add_documents, delete_by_file, get_all_files, get_stats


router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


@router.post("/upload")
async def upload_documents(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    uploaded = []
    for file in files:
        content = await file.read()
        docs = load_file_from_bytes(content, file.filename or "uploaded.txt")
        chunks = split_documents(docs)
        file_id = add_documents(chunks, file.filename or "uploaded.txt")
        summarize_document(file_id, file.filename or "uploaded.txt", chunks)
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
