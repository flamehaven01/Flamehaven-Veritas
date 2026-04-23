"""IRF-Calc 6D text-pattern analyser for experimental reports.

Standalone scorer — no external dependencies.
Adapted from BioMedical-Paper-Harvester/biomedical_harvester/logos_validator.py
and retuned for SCI-EXP experimental report language.

Dimensions (all in [0.0, 1.0]):
  M  Methodic Doubt   — uncertainty acknowledgment
  A  Axiom/Hypothesis — foundational grounding
  D  Deduction        — logical rigor & inference chain
  I  Induction        — empirical support & numeric density
  F  Falsification    — testability, control, reproducibility
  P  Paradigm         — reference / prior-work alignment

composite = epsilon-smoothed geometric mean; threshold 0.65
"""

from __future__ import annotations

import math
import re

from ..types import IRF6DScores, StatValidity

# Passing thresholds
COMPOSITE_THRESHOLD: float = 0.65
COMPONENT_MIN: float = 0.30

# Pattern banks (lower-cased; matched against lower-cased text)
_M_MARKERS = [
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
]
_A_MARKERS = [
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
]
_D_MARKERS = [
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
]
_I_MARKERS = [
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
]
_F_MARKERS = [
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
]
_P_MARKERS = [
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
]


def _marker_density(text: str, markers: list[str], saturate_at: int = 5) -> float:
    """Count distinct marker hits; saturate at *saturate_at* → 1.0."""
    hits = sum(1 for m in markers if m in text)
    return min(hits / saturate_at, 1.0)


def _numeric_density(text: str) -> float:
    """Fraction of tokens that look like numbers (e.g. 0.95, 42, 3.14e-5)."""
    numbers = re.findall(r"\b\d+(?:[.,]\d+)?\b", text)
    words = text.split()
    if not words:
        return 0.0
    return min(len(numbers) / max(len(words) * 0.10, 1), 1.0)


def _sentence_count(text: str) -> int:
    return max(len(re.findall(r"[.!?]", text)), 1)


class IRFAnalyzer:
    """Text-pattern LOGOS IRF-6D scorer for experimental reports.

    Usage::

        analyzer = IRFAnalyzer()
        scores = analyzer.score(text)
        print(scores.composite, scores.passed)
    """

    def score(
        self,
        text: str,
        source: str = "local",
        stat_validity: StatValidity | None = None,
    ) -> IRF6DScores:
        """Return IRF6DScores from free-text experimental report.

        When *stat_validity* is provided (v3.3+), the F dimension is enriched:
        ``F = 0.6 * keyword_density + 0.4 * stat_validity.score``
        """
        t = text.lower()
        M = self._score_M(t)
        A = self._score_A(t)
        D = self._score_D(t)
        I = self._score_I(t)  # noqa: E741
        F = self._score_F(t, stat_validity)
        P = self._score_P(t)
        composite = self._geometric_mean([M, A, D, I, F, P])
        passed = composite >= COMPOSITE_THRESHOLD and all(
            v >= COMPONENT_MIN for v in [M, A, D, I, F, P]
        )
        return IRF6DScores(
            M=round(M, 4),
            A=round(A, 4),
            D=round(D, 4),
            I=round(I, 4),
            F=round(F, 4),
            P=round(P, 4),
            composite=round(composite, 4),
            passed=passed,
            source=source,
        )

    # ------------------------------------------------------------------ #
    #  Dimension scorers                                                   #
    # ------------------------------------------------------------------ #

    def _score_M(self, t: str) -> float:
        """Methodic Doubt — uncertainty acknowledgment & premise clarity."""
        return _marker_density(t, _M_MARKERS, 4)

    def _score_A(self, t: str) -> float:
        """Axiom — foundational grounding & hypothesis quality."""
        return _marker_density(t, _A_MARKERS, 4)

    def _score_D(self, t: str) -> float:
        """Deduction — logical rigor & inference chain."""
        return _marker_density(t, _D_MARKERS, 4)

    def _score_I(self, t: str) -> float:
        """Induction — empirical support combined with numeric density."""
        marker_score = _marker_density(t, _I_MARKERS, 5)
        numeric_score = _numeric_density(t)
        return min(1.0, 0.65 * marker_score + 0.35 * numeric_score)

    def _score_F(
        self, t: str, stat_validity: StatValidity | None = None
    ) -> float:
        """Falsification — testability, control, reproducibility.

        When stat_validity is available (v3.3+):
          F = 0.6 * keyword_density + 0.4 * stat_validity.score
        """
        kw = _marker_density(t, _F_MARKERS, 5)
        if stat_validity is not None:
            return min(1.0, 0.6 * kw + 0.4 * stat_validity.score)
        return kw

    def _score_P(self, t: str) -> float:
        """Paradigm — reference / prior-work alignment."""
        return _marker_density(t, _P_MARKERS, 4)

    # ------------------------------------------------------------------ #
    #  Utility                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _geometric_mean(values: list[float], eps: float = 1e-6) -> float:
        """Epsilon-smoothed geometric mean."""
        log_sum = sum(math.log(max(v, eps)) for v in values)
        return math.exp(log_sum / len(values))
