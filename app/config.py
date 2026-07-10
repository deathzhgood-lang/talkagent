import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# Ollama
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "codex-app")

# Embedding
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
MODEL_CACHE_DIR = str(BASE_DIR / os.getenv("MODEL_CACHE_DIR", "models"))

# OCR
ENABLE_OCR = os.getenv("ENABLE_OCR", "true").lower() in {"1", "true", "yes", "on"}
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "chi_sim+eng")
OCR_DPI = int(os.getenv("OCR_DPI", "180"))
OCR_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES", "30"))
ENABLE_VISION_OCR = os.getenv("ENABLE_VISION_OCR", "true").lower() in {"1", "true", "yes", "on"}
VISION_MODEL = os.getenv("VISION_MODEL", "moondream")

# Text splitting
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))

# Retrieval and chat
RETRIEVAL_K = int(os.getenv("RETRIEVAL_K", "10"))
CHAT_HISTORY_ROUNDS = int(os.getenv("CHAT_HISTORY_ROUNDS", "10"))

# Storage
DATA_DIR = str(BASE_DIR / os.getenv("DATA_DIR", "data"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")
CONVERSATIONS_DIR = os.path.join(DATA_DIR, "conversations")
KNOWLEDGE_INDEX_DIR = os.path.join(DATA_DIR, "knowledge_index")
OBSERVABILITY_DIR = os.path.join(DATA_DIR, "observability")
TRACE_DB_PATH = os.path.join(OBSERVABILITY_DIR, "traces.sqlite3")

# Supported files
SUPPORTED_EXTENSIONS = set(
    ext.strip().lower()
    for ext in os.getenv(
        "SUPPORTED_EXTENSIONS", ".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
    ).split(",")
)

# Service ports
GRADIO_PORT = int(os.getenv("GRADIO_PORT", "7860"))
API_PORT = int(os.getenv("API_PORT", "8000"))

for directory in [
    DATA_DIR,
    UPLOAD_DIR,
    CHROMA_DIR,
    CONVERSATIONS_DIR,
    KNOWLEDGE_INDEX_DIR,
    OBSERVABILITY_DIR,
    MODEL_CACHE_DIR,
]:
    os.makedirs(directory, exist_ok=True)
