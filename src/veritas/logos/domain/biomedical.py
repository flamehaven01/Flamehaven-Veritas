"""Biomedical domain ruleset — default VERITAS IRF-6D scoring domain.

Marker banks migrated verbatim from logos/irf_analyzer.py module-level
constants (_M_MARKERS ... _P_MARKERS). Behavior is identical to all
prior VERITAS versions; this module is the canonical source of truth
for the biomedical marker vocabulary.
"""

from __future__ import annotations

from .base import DomainRuleset

BIOMEDICAL = DomainRuleset(
    domain_key="biomedical",
    name="Biomedical / Experimental Science",
    # Methodic Doubt — uncertainty acknowledgment
    m_markers=(
        "limitation",
        "uncertain",
        "assumption",
        "caveat",
        "unknown",
        "unclear",
        "may ",
        "might ",
        "possibly",
        "open question",
        "not yet confirmed",
        "incomplete",
        "pending",
        "cannot confirm",
    ),
    # Axiom / Hypothesis — foundational grounding
    a_markers=(
        "hypothesis",
        "rationale",
        "expected",
        "theoretical",
        "premise",
        "research question",
        "we propose",
        "based on",
        "prior work",
        "background",
        "motivated by",
        "our assumption",
    ),
    # Deduction — logical rigor & inference chain
    d_markers=(
        "therefore",
        "hence",
        "thus",
        "consequently",
        "it follows",
        "implies",
        "conclude",
        "shows that",
        "demonstrates",
        "establishes",
        "proving",
        "proof",
    ),
    # Induction — empirical support & numeric density
    i_markers=(
        "result",
        "data",
        "measure",
        "observ",
        "collect",
        "n=",
        "sample",
        "trial",
        "iteration",
        "recorded",
        "experiment",
        "test ",
        "run ",
        "epoch",
    ),
    # Falsification — testability, control, reproducibility
    f_markers=(
        "reproducib",
        "replicate",
        "protocol",
        "control",
        "null ",
        "p-value",
        "p value",
        "confidence interval",
        "blind",
        "randomiz",
        "falsif",
        "method",
        "step-by-step",
        "procedure",
    ),
    # Paradigm — reference / prior-work alignment
    p_markers=(
        "reference",
        "doi:",
        "doi.org",
        "et al",
        "cite",
        "cited",
        "prior cycle",
        "baseline",
        "previous version",
        "v1.",
        "v2.",
        "v3.",
        "prior experiment",
        "earlier work",
    ),
    composite_threshold=0.65,
    component_min=0.30,
    saturate_at={"M": 4, "A": 4, "D": 4, "I": 5, "F": 5, "P": 4},
)
