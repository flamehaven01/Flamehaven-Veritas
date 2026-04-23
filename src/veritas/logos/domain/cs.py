"""CS / Software Engineering domain ruleset for VERITAS IRF-6D scoring.

Marker vocabulary derived from IEEE Transactions, ACM proceedings, and
arXiv CS preprint conventions. Key distinctions from biomedical:
  - D dimension: proof-oriented language (theorem, lemma, QED, corollary)
  - I dimension: benchmark-driven evidence (F1, throughput, latency, ablation)
  - F dimension: artifact reproducibility (seed, docker, open source, artifact)
  - P dimension: SOTA / related-work alignment (arxiv, state-of-the-art, baseline)
"""

from __future__ import annotations

from .base import DomainRuleset

CS = DomainRuleset(
    domain_key="cs",
    name="Computer Science / Software Engineering",
    # Methodic Doubt — scope acknowledgment, open issues
    m_markers=(
        "limitation",
        "caveat",
        "corner case",
        "edge case",
        "not handled",
        "out of scope",
        "future work",
        "open issue",
        "we do not address",
        "unknown",
        "unclear",
        "may ",
        "might ",
    ),
    # Axiom / Hypothesis — theoretical grounding
    a_markers=(
        "hypothesis",
        "we claim",
        "theorem",
        "lemma",
        "definition",
        "assumption",
        "model",
        "we propose",
        "conjecture",
        "research question",
        "motivated by",
        "based on",
    ),
    # Deduction — proof chains, inference, formal reasoning
    d_markers=(
        "therefore",
        "hence",
        "thus",
        "by induction",
        "by contradiction",
        "it follows",
        "proof",
        "corollary",
        "qed",
        "we show",
        "implies",
        "conclude",
    ),
    # Induction — benchmark-driven empirical evidence
    i_markers=(
        "benchmark",
        "accuracy",
        "f1",
        "precision",
        "recall",
        "throughput",
        "latency",
        "n=",
        "dataset",
        "evaluation",
        "ablation",
        "experiment",
        "result",
        "measured",
    ),
    # Falsification — reproducibility, artifact availability
    f_markers=(
        "reproducible",
        "open source",
        "seed",
        "deterministic",
        "baseline",
        "ablation study",
        "artifact",
        "docker",
        "github",
        "protocol",
        "null hypothesis",
        "controlled",
        "falsif",
    ),
    # Paradigm — prior work, SOTA, citations
    p_markers=(
        "related work",
        "prior work",
        "et al",
        "arxiv",
        "doi",
        "state-of-the-art",
        "sota",
        "compared to",
        "baseline",
        "reference",
        "cited",
        "previous work",
    ),
    composite_threshold=0.65,
    component_min=0.30,
    saturate_at={"M": 4, "A": 4, "D": 4, "I": 5, "F": 5, "P": 4},
)
