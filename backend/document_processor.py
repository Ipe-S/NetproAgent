import fitz  # PyMuPDF
import re
from pathlib import Path
from typing import List, Dict, Any


def extract_text_from_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


def extract_text_from_md(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


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
