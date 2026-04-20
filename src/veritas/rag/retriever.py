"""RAG Retriever — wraps Flamehaven-Filesearch EmbeddingGenerator + in-memory vector store."""
from __future__ import annotations

import math
import sys

_FF_ROOT = r"D:\Sanctum\Flamehaven-Filesearch"


class _SimpleVectorStore:
    """Minimal cosine-similarity in-memory store (no external deps)."""

    def __init__(self):
        self._docs:  list[dict]       = []
        self._vecs:  list[list[float]] = []

    def add(self, chunk: dict, vector: list[float]) -> None:
        self._docs.append(chunk)
        self._vecs.append(vector)

    def search(self, query_vec: list[float], top_k: int = 5) -> list[dict]:
        if not self._vecs:
            return []
        scored = [
            (self._cosine(query_vec, v), doc)
            for v, doc in zip(self._vecs, self._docs, strict=False)
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot  = sum(x * y for x, y in zip(a, b, strict=False))
        norm = math.sqrt(sum(x**2 for x in a)) * math.sqrt(sum(x**2 for x in b))
        return dot / norm if norm else 0.0


class SciExpRetriever:
    """Semantic retriever for VERITAS context enrichment.

    Uses Flamehaven Gravitas Vectorizer (deterministic, zero-dependency)
    when available, otherwise falls back to simple TF-IDF-like hashing.
    """

    def __init__(self):
        self._store = _SimpleVectorStore()
        self._embedder = _load_embedder()

    def index_chunks(self, chunks: list[dict]) -> int:
        """Index a list of chunks. Returns count indexed."""
        count = 0
        for chunk in chunks:
            text = chunk.get("text", "")
            if not text.strip():
                continue
            vec = self._embed(text)
            self._store.add(chunk, vec)
            count += 1
        return count

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Retrieve top-k most relevant chunks for a query."""
        vec = self._embed(query)
        return self._store.search(vec, top_k=top_k)

    def build_context(self, query: str, top_k: int = 5) -> str:
        """Return concatenated text of top-k chunks for a query."""
        hits = self.retrieve(query, top_k=top_k)
        return "\n\n---\n\n".join(h.get("text", "") for h in hits)

    # ── private ────────────────────────────────────────────────────────────────

    def _embed(self, text: str) -> list[float]:
        if self._embedder is not None:
            try:
                vec = self._embedder.generate(text)
                return vec.tolist() if hasattr(vec, "tolist") else list(vec)
            except Exception:
                pass  # embedder call failed; fall through to TF-IDF fallback
        return _fallback_embed(text)


def _load_embedder():
    try:
        if _FF_ROOT not in sys.path:
            sys.path.insert(0, _FF_ROOT)
        from flamehaven_filesearch.engine.embedding_generator import EmbeddingGenerator
        return EmbeddingGenerator()
    except Exception:
        return None


def _fallback_embed(text: str, dim: int = 384) -> list[float]:
    """Simple hash-based deterministic embedding (no deps)."""
    import hashlib
    words = text.lower().split()[:512]
    vec = [0.0] * dim
    for w in words:
        h = int(hashlib.md5(w.encode()).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(x**2 for x in vec)) or 1.0
    return [x / norm for x in vec]
