import json
import re
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from langchain_ollama import ChatOllama

from app.config import LLM_MODEL, OLLAMA_HOST


def check_ollama() -> None:
    url = OLLAMA_HOST.rstrip("/") + "/api/tags"
    try:
        with urlopen(url, timeout=2):
            return
    except (OSError, URLError) as exc:
        raise RuntimeError(f"Ollama service unavailable: {url}") from exc


def generate_text(prompt: str, timeout: int = 120) -> str:
    check_ollama()
    try:
        llm = ChatOllama(model=LLM_MODEL, base_url=OLLAMA_HOST)
        response = llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)
    except Exception:
        return generate_text_raw(prompt, timeout=timeout)


def generate_text_raw(prompt: str, timeout: int = 120) -> str:
    url = OLLAMA_HOST.rstrip("/") + "/api/generate"
    payload = json.dumps(
        {"model": LLM_MODEL, "prompt": prompt, "stream": False},
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data.get("response", "").strip()


def extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except Exception:
        return None
