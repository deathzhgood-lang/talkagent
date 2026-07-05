import os
from pathlib import Path
from typing import List

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document

from app.config import SUPPORTED_EXTENSIONS, UPLOAD_DIR
from app.ocr import IMAGE_EXTENSIONS, load_ocr_documents


def _get_loader(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return PyPDFLoader(file_path)
    if ext == ".docx":
        return Docx2txtLoader(file_path)
    if ext in (".txt", ".md"):
        return TextLoader(file_path, encoding="utf-8")
    raise ValueError(f"不支持的文件格式: {ext}")


def load_file(file_path: str) -> List[Document]:
    ext = os.path.splitext(file_path)[1].lower()
    documents: list[Document] = []

    if ext in IMAGE_EXTENSIONS:
        documents.extend(load_ocr_documents(file_path))
        return documents

    loader = _get_loader(file_path)
    documents.extend(loader.load())
    if ext in {".pdf", ".docx"}:
        documents.extend(load_ocr_documents(file_path))
    return documents


def load_file_from_bytes(file_bytes: bytes, file_name: str) -> List[Document]:
    safe_name = Path(file_name).name
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式: {ext}，支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    save_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(save_path, "wb") as f:
        f.write(file_bytes)

    return load_file(save_path)
