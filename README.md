# RAG Chat App

Sistema RAG local con FastAPI + ChromaDB + Ollama + HTML/JS vanilla.

## Requisitos previos

- Python 3.10+
- [Ollama](https://ollama.com/) instalado y corriendo

## Instalación

### 1. Instalar Ollama y descargar un modelo

```bash
# Descargar un modelo (elige uno según tu RAM)
ollama pull llama3.2        # 2B, ligero (~2GB)
ollama pull llama3.1        # 8B, mejor calidad (~5GB)
ollama pull mistral         # 7B, muy bueno (~4GB)
```

### 2. Instalar dependencias Python

```bash
cd appAgente
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar .env con tu modelo preferido
# OLLAMA_MODEL=llama3.2
```

### 4. Iniciar el servidor

```bash
cd backend
python main.py
```

Abre [http://localhost:8000](http://localhost:8000) en tu navegador.

## Uso

1. **Cargar documentos**: arrastra archivos PDF o `.md` al área de la izquierda
2. **Espera** a que se procesen (aparecerán en la lista con el número de fragmentos)
3. **Haz preguntas** en el chat sobre el contenido de tus documentos

## Estructura del proyecto

```
appAgente/
├── backend/
│   ├── main.py                 # FastAPI app y punto de entrada
│   ├── config.py               # Variables de configuración
│   ├── document_processor.py   # Extracción de texto y chunking
│   ├── vector_store.py         # ChromaDB: embeddings y búsqueda
│   ├── llm_client.py           # Cliente Ollama (streaming SSE)
│   └── routers/
│       ├── documents.py        # POST/GET/DELETE /api/documents
│       └── chat.py             # POST /api/chat, GET /api/health
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── chroma_db/                  # Base vectorial (se crea automáticamente)
├── requirements.txt
└── .env.example
```

## Variables de configuración (.env)

| Variable | Default | Descripción |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.2` | Modelo Ollama a usar |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL de Ollama |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Modelo de embeddings (descarga automática) |
| `CHUNK_SIZE` | `500` | Tamaño de fragmentos en caracteres |
| `CHUNK_OVERLAP` | `50` | Solapamiento entre fragmentos |
| `TOP_K_RESULTS` | `5` | Fragmentos a recuperar por consulta |

## Endpoints API

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/health` | Estado del servidor y Ollama |
| `GET` | `/api/documents` | Lista documentos cargados |
| `POST` | `/api/documents/upload` | Sube un PDF o Markdown |
| `DELETE` | `/api/documents/{filename}` | Elimina un documento |
| `POST` | `/api/chat` | Chat con streaming SSE |
