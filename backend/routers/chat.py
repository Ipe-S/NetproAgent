import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from llm_client import check_health, stream_response
from vector_store import vector_store
from config import TOP_K_RESULTS

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    top_k: Optional[int] = None


@router.post("/chat")
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(400, "El mensaje no puede estar vacío")

    if vector_store.get_stats()["total_chunks"] == 0:
        raise HTTPException(400, "No hay documentos cargados. Sube documentos primero.")

    top_k = request.top_k or TOP_K_RESULTS
    chunks = vector_store.search(request.message, n_results=top_k)

    async def event_stream():
        sources = list({c["metadata"]["filename"] for c in chunks})
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
        async for token in stream_response(request.message, chunks):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "ollama": await check_health(),
        "knowledge_base": vector_store.get_stats(),
    }
