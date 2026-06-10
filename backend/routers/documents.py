import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from config import CHUNK_OVERLAP, CHUNK_SIZE
from document_processor import process_document
from vector_store import vector_store

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".md", ".jpg", ".jpeg", ".png"}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Solo se aceptan archivos PDF, Markdown (.md) o imágenes (.jpg, .jpeg, .png)")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        chunks = process_document(tmp_path, file.filename, CHUNK_SIZE, CHUNK_OVERLAP)
        count = vector_store.add_document(chunks)
        return {
            "message": f"'{file.filename}' procesado exitosamente",
            "chunks_created": count,
            "filename": file.filename,
        }
    except Exception as exc:
        raise HTTPException(500, f"Error procesando documento: {exc}")
    finally:
        os.unlink(tmp_path)


@router.get("")
async def list_documents():
    return {"documents": vector_store.list_documents(), "stats": vector_store.get_stats()}


@router.delete("/{filename:path}")
async def delete_document(filename: str):
    deleted = vector_store.delete_document(filename)
    if deleted == 0:
        raise HTTPException(404, f"Documento '{filename}' no encontrado")
    return {"message": f"'{filename}' eliminado", "chunks_deleted": deleted}
