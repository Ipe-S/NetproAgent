import base64
import fitz  # PyMuPDF
import httpx
import re
from pathlib import Path
from typing import List, Dict, Any

from config import OLLAMA_BASE_URL, OLLAMA_VISION_MODEL


def extract_text_from_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


def extract_text_from_md(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def extract_text_from_image(file_path: str) -> str:
    with open(file_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")
    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_VISION_MODEL,
            "prompt": "Transcribe todo el texto visible en esta imagen. Devuelve únicamente el texto, sin descripciones ni comentarios.",
            "images": [image_b64],
            "stream": False,
        },
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json().get("response", "")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            para_break = text.rfind("\n\n", start, end)
            if para_break > start + overlap:
                end = para_break
            else:
                sentence_end = max(
                    text.rfind(". ", start, end),
                    text.rfind("! ", start, end),
                    text.rfind("? ", start, end),
                )
                if sentence_end > start + overlap:
                    end = sentence_end + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap

    return chunks


def process_document(
    file_path: str, filename: str, chunk_size: int = 500, overlap: int = 50
) -> List[Dict[str, Any]]:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        text = extract_text_from_pdf(file_path)
    elif ext == ".md":
        text = extract_text_from_md(file_path)
    elif ext in {".jpg", ".jpeg", ".png"}:
        text = extract_text_from_image(file_path)
    else:
        raise ValueError(f"Tipo de archivo no soportado: {ext}")

    chunks = chunk_text(text, chunk_size, overlap)
    return [
        {
            "text": chunk,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "filename": filename,
        }
        for i, chunk in enumerate(chunks)
    ]
