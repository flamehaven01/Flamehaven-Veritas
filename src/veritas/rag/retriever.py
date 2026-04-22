"""VERITAS RAG Retriever — extracted from Flamehaven-Filesearch (native, zero new deps).

Source: D:\\Sanctum\\Flamehaven-Filesearch\\flamehaven_filesearch\\engine\\

Extracted algorithms:
  BM25          — hybrid_search.py:13-74   (k1=1.5, b=0.75, Robertson formula)
  rrf_fusion    — hybrid_search.py:77-100  (k=60, Reciprocal Rank Fusion)
  chunk_text    — text_chunker.py:59-202   (heading-aware sliding window)
  SciExpRetriever — hybrid BM25 + cosine + RRF pipeline

Dependencies: math, re, collections (stdlib). numpy OPTIONAL (already in VERITAS extras).
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from typing import Any

# ── BM25 (Robertson formula) ──────────────────────────────────────────────────


class BM25:
    """BM25 probabilistic ranker (k1=1.5, b=0.75).

    Extracted from Flamehaven-Filesearch hybrid_search.py:13-74.
    Supports Korean (\\uac00-\\ud7a3) + English + digits.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size: int = 0
        self.avgdl: float = 0.0
        self._doc_freqs: list[Counter[str]] = []
        self._doc_len: list[int] = []
        self._idf: dict[str, float] = {}

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9\uac00-\ud7a3]+", text.lower())

    def fit(self, corpus: list[str]) -> None:
        """Build BM25 index from corpus."""
        self.corpus_size = len(corpus)
        tokenized = [self._tokenize(doc) for doc in corpus]
        self._doc_len = [len(d) for d in tokenized]
        self.avgdl = sum(self._doc_len) / self.corpus_size if self.corpus_size else 0.0

        df: dict[str, int] = defaultdict(int)
        self._doc_freqs = []
        for doc in tokenized:
            self._doc_freqs.append(Counter(doc))
            for tok in set(doc):
                df[tok] += 1

        n = self.corpus_size
        self._idf = {tok: math.log((n - freq + 0.5) / (freq + 0.5) + 1) for tok, freq in df.items()}

    def score(self, query: str, doc_id: int) -> float:
        """BM25 score for a single (query, document) pair."""
        if doc_id >= len(self._doc_freqs) or not self.avgdl:
            return 0.0
        tf_map = self._doc_freqs[doc_id]
        dl = self._doc_len[doc_id]
        s = 0.0
        for tok in self._tokenize(query):
            if tok not in tf_map:
                continue
            tf = tf_map[tok]
            idf = self._idf.get(tok, 0.0)
            num = tf * (self.k1 + 1)
            den = tf + self.k1 * (1 - self.b + self.b * (dl / self.avgdl))
            s += idf * (num / den)
        return s

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Return top-k scored results as [{"id": int, "score": float}]."""
        scores = [{"id": i, "score": self.score(query, i)} for i in range(self.corpus_size)]
        scores = [s for s in scores if s["score"] > 0]
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]


# ── Reciprocal Rank Fusion ─────────────────────────────────────────────────────


def rrf_fusion(
    results_list: list[list[dict[str, Any]]],
    k: int = 60,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Merge multiple ranked lists via Reciprocal Rank Fusion.

    RRF(d) = sum(1 / (k + rank)) across all result lists.
    Extracted from Flamehaven-Filesearch hybrid_search.py:77-100.
    """
    rrf_scores: dict[Any, float] = defaultdict(float)
    first_seen: dict[Any, dict[str, Any]] = {}
    for ranked in results_list:
        for rank, item in enumerate(ranked, start=1):
            doc_id = item["id"]
            rrf_scores[doc_id] += 1.0 / (k + rank)
            first_seen.setdefault(doc_id, item)
    fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    out: list[dict[str, Any]] = []
    for doc_id, rrf_score in fused[:top_k]:
        entry = first_seen[doc_id].copy()
        entry["rrf_score"] = rrf_score
        entry["score"] = min(1.0, rrf_score / 2.0)
        out.append(entry)
    return out


# ── Text Chunker ───────────────────────────────────────────────────────────────

_WORDS_PER_TOKEN = 0.75
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_PARA_SPLIT_RE = re.compile(r"\n{2,}")


def _estimate_tokens(text: str) -> int:
    return int(len(text.split()) / _WORDS_PER_TOKEN)


def _make_chunk(text: str, headings: list[str]) -> dict[str, Any]:
    return {"text": text, "pages": [], "headings": headings}


def _split_by_sentences(text: str, max_tokens: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for sent in sentences:
        st = _estimate_tokens(sent)
        if st > max_tokens:
            # Sentence too long — split by words directly
            if current:
                chunks.append(" ".join(current))
                current, current_tokens = [], 0
            words = sent.split()
            step = max(1, int(max_tokens * _WORDS_PER_TOKEN))
            for i in range(0, len(words), step):
                chunks.append(" ".join(words[i : i + step]))
            continue
        if current_tokens + st > max_tokens and current:
            chunks.append(" ".join(current))
            current, current_tokens = [], 0
        current.append(sent)
        current_tokens += st
    if current:
        chunks.append(" ".join(current))
    return chunks


def _split_section(body: str, headings: list[str], max_tokens: int) -> list[dict[str, Any]]:
    if _estimate_tokens(body) <= max_tokens:
        return [_make_chunk(body, headings)]
    chunks: list[dict[str, Any]] = []
    paragraphs = [p.strip() for p in _PARA_SPLIT_RE.split(body) if p.strip()]
    current_parts: list[str] = []
    current_tokens = 0
    for para in paragraphs:
        para_tokens = _estimate_tokens(para)
        if para_tokens > max_tokens:
            if current_parts:
                chunks.append(_make_chunk("\n\n".join(current_parts), headings))
                current_parts, current_tokens = [], 0
            for sub in _split_by_sentences(para, max_tokens):
                chunks.append(_make_chunk(sub, headings))
            continue
        if current_tokens + para_tokens > max_tokens and current_parts:
            chunks.append(_make_chunk("\n\n".join(current_parts), headings))
            current_parts, current_tokens = [], 0
        current_parts.append(para)
        current_tokens += para_tokens
    if current_parts:
        chunks.append(_make_chunk("\n\n".join(current_parts), headings))
    return chunks


def _split_into_sections(text: str) -> list[dict[str, Any]]:
    heading_matches = list(_HEADING_RE.finditer(text))
    if not heading_matches:
        return [{"body": text, "headings": []}]
    sections: list[dict[str, Any]] = []
    heading_stack: list[str] = []
    preamble = text[: heading_matches[0].start()].strip()
    if preamble:
        sections.append({"body": preamble, "headings": []})
    for i, match in enumerate(heading_matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        if level <= len(heading_stack):
            heading_stack = heading_stack[: level - 1]
        heading_stack.append(title)
        start = match.end()
        end = heading_matches[i + 1].start() if i + 1 < len(heading_matches) else len(text)
        body = text[start:end].strip()
        sections.append({"body": body, "headings": list(heading_stack)})
    return sections


def _merge_small_chunks(
    chunks: list[dict[str, Any]],
    min_tokens: int,
    max_tokens: int,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for chunk in chunks:
        if (
            merged
            and _estimate_tokens(chunk["text"]) < min_tokens
            and _estimate_tokens(merged[-1]["text"]) + _estimate_tokens(chunk["text"]) <= max_tokens
        ):
            merged[-1]["text"] = merged[-1]["text"] + "\n\n" + chunk["text"]
        else:
            merged.append(chunk)
    return merged


def chunk_text(
    text: str,
    max_tokens: int = 512,
    min_tokens: int = 64,
    merge_peers: bool = True,
) -> list[dict[str, Any]]:
    """Split text into RAG-ready chunks (heading-aware sliding window).

    Extracted from Flamehaven-Filesearch text_chunker.py:59-202.

    Returns list of dicts: {"text": str, "pages": list[int], "headings": list[str]}
    """
    if not text or not text.strip():
        return []
    sections = _split_into_sections(text)
    raw_chunks: list[dict[str, Any]] = []
    for section in sections:
        body = section["body"].strip()
        if body:
            raw_chunks.extend(_split_section(body, section["headings"], max_tokens))
    if merge_peers and len(raw_chunks) > 1:
        raw_chunks = _merge_small_chunks(raw_chunks, min_tokens, max_tokens)
    return raw_chunks


# ── Cosine vector store ────────────────────────────────────────────────────────


def _fallback_embed(text: str, dim: int = 384) -> list[float]:
    """Deterministic hash-based embedding (pure Python, no external deps)."""
    words = text.lower().split()[:512]
    vec = [0.0] * dim
    for w in words:
        h = int(hashlib.md5(w.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(x**2 for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cosine_pure(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm = math.sqrt(sum(x**2 for x in a)) * math.sqrt(sum(x**2 for x in b))
    return dot / norm if norm else 0.0


class _VectorStore:
    """In-memory cosine similarity store. Uses numpy when available."""

    def __init__(self) -> None:
        self._docs: list[dict[str, Any]] = []
        self._vecs: list[list[float]] = []

    def add(self, chunk: dict[str, Any], vector: list[float]) -> None:
        self._docs.append(chunk)
        self._vecs.append(vector)

    def search(self, query_vec: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        if not self._vecs:
            return []
        try:
            import numpy as np

            mat = np.array(self._vecs, dtype=np.float32)
            q = np.array(query_vec, dtype=np.float32)
            norms_mat = np.linalg.norm(mat, axis=1)
            norms_mat[norms_mat == 0] = 1.0
            q_norm = np.linalg.norm(q) or 1.0
            sims = (mat / norms_mat[:, None]) @ (q / q_norm)
            indices = np.argsort(sims)[::-1][:top_k]
            return [{"id": int(i), "score": float(sims[i]), **self._docs[i]} for i in indices]
        except ImportError:
            scored = [(i, _cosine_pure(query_vec, v)) for i, v in enumerate(self._vecs)]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [{"id": i, "score": s, **self._docs[i]} for i, s in scored[:top_k]]


# ── Hybrid retriever ───────────────────────────────────────────────────────────


class SciExpRetriever:
    """Hybrid BM25 + cosine-similarity + RRF retriever for VERITAS context enrichment.

    Fully native — extracted algorithms from Flamehaven-Filesearch.
    Zero new pip dependencies.

    Usage::

        r = SciExpRetriever()
        r.index(long_text)              # chunk + index document
        hits = r.retrieve("hypothesis") # hybrid BM25+cosine+RRF
        ctx = r.build_context("hypothesis")  # text string for prompt injection
    """

    def __init__(self, max_tokens: int = 512, top_k: int = 5) -> None:
        self._max_tokens = max_tokens
        self._top_k = top_k
        self._corpus: list[str] = []
        self._chunks: list[dict[str, Any]] = []
        self._bm25 = BM25()
        self._vstore = _VectorStore()
        self._indexed = False

    def index(self, text: str) -> int:
        """Chunk text and build BM25 + vector indices. Returns chunk count."""
        chunks = chunk_text(text, max_tokens=self._max_tokens)
        return self.index_chunks(chunks)

    def index_chunks(self, chunks: list[dict[str, Any]]) -> int:
        """Index pre-chunked dicts. Returns count indexed."""
        count = 0
        for chunk in chunks:
            body = chunk.get("text", "")
            if not body.strip():
                continue
            self._chunks.append(chunk)
            self._corpus.append(body)
            vec = _fallback_embed(body)
            self._vstore.add({"chunk_id": len(self._chunks) - 1, **chunk}, vec)
            count += 1
        if count:
            self._bm25.fit(self._corpus)
            self._indexed = True
        return count

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """Retrieve top-k relevant chunks via hybrid BM25 + cosine + RRF."""
        k = top_k or self._top_k
        if not self._indexed:
            return []
        bm25_hits = [
            {"id": h["id"], "score": h["score"]} for h in self._bm25.search(query, top_k=k * 2)
        ]
        q_vec = _fallback_embed(query)
        cos_hits = [
            {"id": h["chunk_id"], "score": h["score"]}
            for h in self._vstore.search(q_vec, top_k=k * 2)
            if "chunk_id" in h
        ]
        fused = rrf_fusion([bm25_hits, cos_hits], k=60, top_k=k)
        results: list[dict[str, Any]] = []
        for item in fused:
            cid = item.get("id")
            if cid is not None and 0 <= cid < len(self._chunks):
                results.append(self._chunks[cid])
        return results

    def build_context(self, query: str, top_k: int | None = None) -> str:
        """Return concatenated chunk text for prompt injection."""
        hits = self.retrieve(query, top_k=top_k)
        return "\n\n---\n\n".join(h.get("text", "") for h in hits)
