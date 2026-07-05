import io
import base64
import json
import sys
import zipfile
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen

from langchain_core.documents import Document

from app.config import (
    ENABLE_OCR,
    ENABLE_VISION_OCR,
    OCR_DPI,
    OCR_LANGUAGE,
    OCR_MAX_PAGES,
    OLLAMA_HOST,
    VISION_MODEL,
)


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
DEPS_DIR = Path(__file__).resolve().parent.parent / ".deps"
if DEPS_DIR.exists() and str(DEPS_DIR) not in sys.path:
    sys.path.insert(0, str(DEPS_DIR))
_rapidocr_engine = None


def get_ocr_status() -> tuple[bool, str]:
    rapid_ok, rapid_reason = get_rapidocr_status()
    if rapid_ok:
        return True, rapid_reason
    if ENABLE_VISION_OCR:
        vision_ok, vision_reason = get_vision_status()
        if vision_ok:
            return True, vision_reason
    if not ENABLE_OCR:
        return False, "OCR disabled by ENABLE_OCR=false"
    try:
        import pytesseract

        version = pytesseract.get_tesseract_version()
        return True, f"Tesseract OCR available: {version}"
    except Exception as exc:
        return False, (
            "OCR engine unavailable. Install Tesseract OCR and make sure "
            f"tesseract.exe is in PATH. Detail: {exc}"
        )


def get_rapidocr_status() -> tuple[bool, str]:
    try:
        import rapidocr_onnxruntime  # noqa: F401

        return True, "RapidOCR available"
    except Exception as exc:
        return False, f"RapidOCR unavailable: {exc}"


def get_vision_status() -> tuple[bool, str]:
    if not ENABLE_VISION_OCR:
        return False, "Vision OCR disabled by ENABLE_VISION_OCR=false"
    try:
        url = OLLAMA_HOST.rstrip("/") + "/api/tags"
        with urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        models = {item.get("name", "").split(":")[0] for item in data.get("models", [])}
        if VISION_MODEL.split(":")[0] in models:
            return True, f"Ollama vision model available: {VISION_MODEL}"
        return False, f"Ollama vision model not found: {VISION_MODEL}"
    except Exception as exc:
        return False, f"Ollama vision unavailable: {exc}"


def load_ocr_documents(file_path: str) -> list[Document]:
    path = Path(file_path)
    ext = path.suffix.lower()

    available, reason = get_ocr_status()
    if not available:
        return _image_placeholders(path, reason)

    if ext == ".pdf":
        return _ocr_pdf(path)
    if ext == ".docx":
        return _ocr_docx(path)
    if ext in IMAGE_EXTENSIONS:
        doc = _ocr_image_file(path, {"source": str(path), "file_type": "image", "ocr": True})
        return [doc] if doc is not None else []
    return []


def _extract_text_from_image(image) -> str:
    rapid_text = _rapidocr_text_from_image(image)
    if rapid_text:
        return rapid_text
    vision_text = _vision_text_from_image(image)
    if vision_text:
        return vision_text
    try:
        return _ocr_text_from_image(image)
    except Exception:
        return ""


def _vision_text_from_image(image) -> str:
    vision_ok, _reason = get_vision_status()
    if not vision_ok:
        return ""

    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    image_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    payload = json.dumps(
        {
            "model": VISION_MODEL,
            "prompt": (
                "请用中文提取并描述这张图片里的关键信息。"
                "如果有文字、表格、流程图、截图、图表或数字，请尽量完整转写。"
            ),
            "images": [image_base64],
            "stream": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        OLLAMA_HOST.rstrip("/") + "/api/generate",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data.get("response", "").strip()
    except Exception:
        return ""


def _rapidocr_text_from_image(image) -> str:
    global _rapidocr_engine
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR

        if _rapidocr_engine is None:
            _rapidocr_engine = RapidOCR()
        result, _elapsed = _rapidocr_engine(np.array(image.convert("RGB")))
        if not result:
            return ""
        lines = []
        for item in result:
            if len(item) >= 2:
                text = item[1]
                score = item[2] if len(item) >= 3 else 1
                if text and score >= 0.45:
                    lines.append(str(text))
        return "\n".join(lines).strip()
    except Exception:
        return ""


def _ocr_text_from_image(image) -> str:
    import pytesseract

    try:
        return pytesseract.image_to_string(image, lang=OCR_LANGUAGE).strip()
    except Exception:
        if OCR_LANGUAGE != "eng":
            return pytesseract.image_to_string(image, lang="eng").strip()
        raise


def _ocr_image_file(path: Path, metadata: dict) -> Document | None:
    from PIL import Image

    with Image.open(path) as image:
        text = _extract_text_from_image(image.convert("RGB"))
    if not text:
        return None
    return Document(page_content=f"[OCR 图片文字]\n{text}", metadata=metadata)


def _ocr_pdf(path: Path) -> list[Document]:
    import fitz
    from PIL import Image

    documents: list[Document] = []
    pdf = fitz.open(path)
    scale = OCR_DPI / 72
    matrix = fitz.Matrix(scale, scale)
    max_pages = min(len(pdf), OCR_MAX_PAGES)

    for page_index in range(max_pages):
        page = pdf[page_index]
        text = page.get_text("text").strip()
        images = page.get_images(full=True)
        if text and not images:
            continue

        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
        ocr_text = _extract_text_from_image(image)
        if ocr_text:
            documents.append(
                Document(
                    page_content=f"[OCR 第 {page_index + 1} 页图片文字]\n{ocr_text}",
                    metadata={
                        "source": str(path),
                        "page": page_index,
                        "ocr": True,
                        "file_type": "pdf",
                    },
                )
            )
    pdf.close()
    return documents


def _ocr_docx(path: Path) -> list[Document]:
    from PIL import Image

    documents: list[Document] = []
    with zipfile.ZipFile(path) as archive:
        image_names = [
            name
            for name in archive.namelist()
            if name.startswith("word/media/")
            and Path(name).suffix.lower() in IMAGE_EXTENSIONS
        ]
        for index, name in enumerate(image_names):
            with archive.open(name) as image_file:
                image = Image.open(io.BytesIO(image_file.read())).convert("RGB")
            ocr_text = _extract_text_from_image(image)
            if ocr_text:
                documents.append(
                    Document(
                        page_content=f"[OCR DOCX 图片 {index + 1}: {Path(name).name}]\n{ocr_text}",
                        metadata={
                            "source": str(path),
                            "image_name": Path(name).name,
                            "image_index": index,
                            "ocr": True,
                            "file_type": "docx",
                        },
                    )
                )
    return documents


def _image_placeholders(path: Path, reason: str) -> list[Document]:
    ext = path.suffix.lower()
    placeholders: list[Document] = []
    if ext == ".pdf":
        placeholders.extend(_pdf_image_placeholders(path, reason))
    elif ext == ".docx":
        placeholders.extend(_docx_image_placeholders(path, reason))
    elif ext in IMAGE_EXTENSIONS:
        placeholders.append(_placeholder_document(path, reason, "image"))
    return placeholders


def _pdf_image_placeholders(path: Path, reason: str) -> Iterable[Document]:
    try:
        import fitz

        pdf = fitz.open(path)
        max_pages = min(len(pdf), OCR_MAX_PAGES)
        for page_index in range(max_pages):
            image_count = len(pdf[page_index].get_images(full=True))
            text = pdf[page_index].get_text("text").strip()
            if image_count or not text:
                yield _placeholder_document(
                    path,
                    reason,
                    "pdf",
                    {
                        "page": page_index,
                        "image_count": image_count,
                    },
                )
        pdf.close()
    except Exception:
        return


def _docx_image_placeholders(path: Path, reason: str) -> Iterable[Document]:
    try:
        with zipfile.ZipFile(path) as archive:
            image_names = [
                name
                for name in archive.namelist()
                if name.startswith("word/media/")
                and Path(name).suffix.lower() in IMAGE_EXTENSIONS
            ]
        for index, name in enumerate(image_names):
            yield _placeholder_document(
                path,
                reason,
                "docx",
                {
                    "image_index": index,
                    "image_name": Path(name).name,
                },
            )
    except Exception:
        return


def _placeholder_document(
    path: Path,
    reason: str,
    file_type: str,
    extra_metadata: dict | None = None,
) -> Document:
    metadata = {
        "source": str(path),
        "file_type": file_type,
        "ocr": False,
        "ocr_unavailable": True,
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return Document(
        page_content=(
            "[图片内容未OCR]\n"
            f"文件 {path.name} 包含图片内容，但当前未能执行 OCR。"
            f"原因: {reason}"
        ),
        metadata=metadata,
    )
