"""RAG Context Builder — assembles per-step context from retrieved chunks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .retriever import SciExpRetriever


STEP_QUERIES: dict[str, str] = {
    "0": "experiment type methodology design classification",
    "1": "hypothesis claim prediction quantitative measurement unit",
    "2": "raw data figure table measurement instrument reference",
    "3": "protocol version iteration cycle series continuity",
    "4": "statistical analysis peer review publication format citation",
    "5": "critical flaw priority fix urgent revision hold",
}


@dataclass
class StepContext:
    step_id: str
    text: str
    chunks: list[str] = field(default_factory=list)


def build_all_contexts(
    retriever: SciExpRetriever,
    top_k: int = 4,
) -> dict[str, StepContext]:
    """Build RAG context for each pipeline step."""
    contexts: dict[str, StepContext] = {}
    for step_id, query in STEP_QUERIES.items():
        text = retriever.build_context(query, top_k=top_k)
        ctxobj = StepContext(step_id=step_id, text=text)
        contexts[step_id] = ctxobj
    return contexts


def enrich_prose(prose: str, context: StepContext, max_tokens: int = 300) -> str:
    """Append relevant context snippets to prose if context is non-trivial."""
    if not context.text.strip():
        return prose
    snippet = context.text[:max_tokens].strip()
    # Only append if context adds new information
    if any(w in snippet.lower() for w in prose.lower().split()[:5]):
        return prose
    return f"{prose}\n[Context] {snippet}..."
