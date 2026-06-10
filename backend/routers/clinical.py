import json
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from clinical_session import clinical_session
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, TOP_K_RESULTS
from vector_store import vector_store

router = APIRouter(prefix="/api/clinical", tags=["clinical"])

SPECIALIST_LABELS = {
    "to": "Terapeuta Ocupacional",
    "psicologia": "Psicólogo Cognitivo-Conductual",
    "neurologia": "Neurólogo en Neurodivergencia",
}

_SYSTEM = (
    "Eres un sistema de síntesis clínica interdisciplinar especializado en neurodivergencia. "
    "Tu tarea es generar un REPORTE INTERDISCIPLINAR DE NEURODIVERGENCIA unificado, "
    "conectando los hallazgos de tres especialistas independientes. "
    "Conecta los datos, no los repitas. Aplica siempre un marco neuroafirmativo. "
    "Sé clínico, preciso y empático."
)


def _consolidation_prompt(inputs: dict, chunks: list) -> str:
    doc_context = ""
    if chunks:
        fragments = "\n\n".join(
            f"[Fragmento {i + 1} — {c['metadata']['filename']}]:\n{c['text']}"
            for i, c in enumerate(chunks)
        )
        doc_context = f"## CONTEXTO DE DOCUMENTOS CARGADOS:\n{fragments}\n\n"

    return (
        f"{doc_context}"
        f"## DATOS DEL TERAPEUTA OCUPACIONAL:\n{inputs['to']}\n\n"
        f"## DATOS DEL PSICÓLOGO COGNITIVO-CONDUCTUAL:\n{inputs['psicologia']}\n\n"
        f"## DATOS DEL NEURÓLOGO:\n{inputs['neurologia']}\n\n"
        "Genera el reporte con la siguiente estructura EXACTA:\n\n"
        "📋 REPORTE INTERDISCIPLINAR DE NEURODIVERGENCIA\n\n"
        "**1. SÍNTESIS INTEGRATIVA DEL CASO**\n"
        "(Resumen que cruza hallazgos biológicos, psicológicos y funcionales. "
        "No repitas datos, conéctalos. Apóyate en el contexto documental si es relevante.)\n\n"
        "**2. PERSPECTIVA POR ESPECIALIDAD**\n"
        "- **Análisis Neurológico:** (Juicio clínico, funciones ejecutivas, "
        "bases orgánicas y observaciones médicas)\n"
        "- **Análisis Psicológico:** (Estado socioemocional, conducta, "
        "dinámicas de afrontamiento)\n"
        "- **Análisis de Terapia Ocupacional:** (Perfil sensorial, impacto "
        "en la vida diaria, barreras del entorno)\n\n"
        "**3. PLAN DE ACCIÓN Y SUGERENCIAS (CONVERGENCIA)**\n"
        "(Lista de estrategias prioritarias donde las tres disciplinas se apoyan "
        "mutuamente. Para cada estrategia indica qué aporta cada especialidad.)"
    )


class InputRequest(BaseModel):
    specialist: Literal["to", "psicologia", "neurologia"]
    text: str


@router.post("/input")
async def receive_input(req: InputRequest):
    if not req.text.strip():
        raise HTTPException(400, "El texto no puede estar vacío")
    clinical_session.set_input(req.specialist, req.text)
    return {
        "message": f"Input de {SPECIALIST_LABELS[req.specialist]} recibido.",
        "status": clinical_session.status(),
    }


@router.get("/status")
async def get_status():
    return {"status": clinical_session.status()}


@router.post("/clear")
async def clear_session():
    clinical_session.clear()
    return {"message": "Sesión clínica reiniciada."}


@router.post("/consolidate")
async def consolidate():
    status = clinical_session.status()
    missing = [SPECIALIST_LABELS[k] for k, v in status.items() if not v]
    if missing:
        raise HTTPException(400, f"Faltan datos de: {', '.join(missing)}")

    inputs = clinical_session.get_all()
    query = " ".join(inputs.values())
    chunks = vector_store.search(query, n_results=TOP_K_RESULTS) if vector_store.get_stats()["total_chunks"] > 0 else []

    prompt = _consolidation_prompt(inputs, chunks)

    async def event_stream():
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "system": _SYSTEM,
                    "prompt": prompt,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if not data.get("done", False):
                            yield f"data: {json.dumps({'type': 'token', 'content': data.get('response', '')})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
