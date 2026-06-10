import hashlib
from typing import List, Dict, Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL, TOP_K_RESULTS


class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
        self.model = SentenceTransformer(EMBEDDING_MODEL)

    def _chunk_id(self, filename: str, chunk_index: int) -> str:
        return hashlib.md5(f"{filename}_{chunk_index}".encode()).hexdigest()

    def add_document(self, chunks: List[Dict[str, Any]]) -> int:
        if not chunks:
            return 0
        texts = [c["text"] for c in chunks]
        embeddings = self.model.encode(texts).tolist()
        ids = [self._chunk_id(c["filename"], c["chunk_index"]) for c in chunks]
        metadatas = [
            {
                "filename": c["filename"],
                "chunk_index": c["chunk_index"],
                "total_chunks": c["total_chunks"],
            }
            for c in chunks
        ]
        self.collection.upsert(
            ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas
        )
        return len(chunks)

    def search(self, query: str, n_results: int = None) -> List[Dict[str, Any]]:
        n_results = n_results or TOP_K_RESULTS
        count = self.collection.count()
        if count == 0:
            return []
        n_results = min(n_results, count)
        embedding = self.model.encode([query]).tolist()
        results = self.collection.query(
            query_embeddings=embedding,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        return [
            {
                "text": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            }
            for i, doc in enumerate(results["documents"][0])
        ]

    def delete_document(self, filename: str) -> int:
        results = self.collection.get(where={"filename": filename})
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
        return len(results["ids"])

    def list_documents(self) -> List[Dict[str, Any]]:
        results = self.collection.get(include=["metadatas"])
        docs: Dict[str, Dict] = {}
        for meta in results["metadatas"]:
            fname = meta["filename"]
            if fname not in docs:
                docs[fname] = {
                    "filename": fname,
                    "total_chunks": meta["total_chunks"],
                }
        return list(docs.values())

    def get_stats(self) -> Dict[str, Any]:
        docs = self.list_documents()
        return {
            "total_chunks": self.collection.count(),
            "total_documents": len(docs),
        }


vector_store = VectorStore()
