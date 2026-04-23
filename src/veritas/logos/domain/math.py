"""Mathematics domain ruleset for VERITAS IRF-6D scoring.

Marker vocabulary derived from formal mathematical writing conventions:
journal articles (Annals of Mathematics, JAMS), proof assistants (Lean,
Coq), and LaTeX preprint norms. Key distinctions from biomedical:
  - A dimension: proof-foundational vocabulary (axiom, lemma, corollary)
  - D dimension: proof construction (QED, by induction, iff, we show)
  - F dimension: formal verifiability (constructive proof, tight bound, rigorous)
  - I dimension: case analysis and counterexample patterns (for all, there exists)
"""

from __future__ import annotations

from .base import DomainRuleset

MATH = DomainRuleset(
    domain_key="math",
    name="Mathematics / Formal Proof",
    # Methodic Doubt — open conjectures, unknowns, scope limits
    m_markers=(
        "conjecture",
        "open question",
        "we assume",
        "not yet proven",
        "unclear",
        "limitation",
        "caveat",
        "unknown",
        "open problem",
        "may ",
        "might ",
        "incomplete",
    ),
    # Axiom / Hypothesis — foundational structures
    a_markers=(
        "axiom",
        "definition",
        "theorem",
        "lemma",
        "corollary",
        "proposition",
        "suppose",
        "let ",
        "given that",
        "we assume",
        "hypothesis",
        "premise",
    ),
    # Deduction — formal proof steps
    d_markers=(
        "therefore",
        "hence",
        "thus",
        "it follows",
        "qed",
        "proof",
        "implies",
        "by induction",
        "by contradiction",
        "if and only if",
        "iff",
        "we show",
        "we prove",
    ),
    # Induction — case analysis, numeric examples, existence
    i_markers=(
        "counterexample",
        "example",
        "n=",
        "case",
        "for all",
        "there exists",
        "computed",
        "numerical",
        "verified",
        "observed",
        "result",
        "instance",
    ),
    # Falsification — formal verifiability, bounds
    f_markers=(
        "constructive proof",
        "falsifiable",
        "checkable",
        "verifiable",
        "rigorous",
        "tight bound",
        "lower bound",
        "upper bound",
        "necessary and sufficient",
        "provable",
        "decidable",
        "reproducible",
    ),
    # Paradigm — prior results, references
    p_markers=(
        "reference",
        "et al",
        "cited",
        "doi",
        "prior result",
        "classical result",
        "well-known",
        "following",
        "builds on",
        "based on",
        "previous work",
        "lemma of",
    ),
    composite_threshold=0.65,
    component_min=0.30,
    saturate_at={"M": 4, "A": 4, "D": 4, "I": 5, "F": 5, "P": 4},
)
