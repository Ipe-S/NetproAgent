import json
from typing import AsyncIterator, Dict, Any, List

import httpx

from config import OLLAMA_BASE_URL, OLLAMA_MODEL

_SYSTEM_PROMPT = (
    "Eres un asistente útil que responde preguntas basándose en los documentos proporcionados. "
    "Usa únicamente la información del contexto para responder. "
    "Si la información no está en el contexto, indícalo claramente. "
    "Responde en el mismo idioma que la pregunta."
)


def _build_prompt(question: str, chunks: List[Dict[str, Any]]) -> str:
    context = "\n\n".join(
        f"[Fragmento {i + 1} — {c['metadata']['filename']}]:\n{c['text']}"
        for i, c in enumerate(chunks)
    )
    return f"Contexto de los documentos:\n{context}\n\nPregunta: {question}\n\nResponde basándote en el contexto anterior."


async def stream_response(question: str, chunks: List[Dict[str, Any]]) -> AsyncIterator[str]:
    prompt = _build_prompt(question, chunks)
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "system": _SYSTEM_PROMPT, "stream": True},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    if not data.get("done", False):
                        yield data.get("response", "")


async def check_health() -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return {"status": "ok", "models": models}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
