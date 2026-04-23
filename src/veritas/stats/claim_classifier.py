"""Claim typology classifier for VERITAS v3.3.

Classifies the dominant academic claim type in a document (or its abstract)
using marker-bank density scoring.  Each marker bank represents a distinct
discourse register:

  EMPIRICAL      — "measured", "observed", "experiment showed", p-values …
  THEORETICAL    — "propose", "framework", "model assumes", "theorem" …
  COMPARATIVE    — "compared to", "baseline", "outperforms", "versus" …
  METHODOLOGICAL — "protocol", "procedure", "step-by-step", "pipeline" …

The type with the highest density wins.  Ties (within ±0.05) resolve to
UNKNOWN, signalling that the paper blends multiple claim types.
"""

from __future__ import annotations

import re

from ..types import ClaimType

# ---------------------------------------------------------------------------
# Marker banks  (lowercased — all comparison done on lower text)
# ---------------------------------------------------------------------------

_EMPIRICAL_MARKERS: list[str] = [
    r"p\s*[=<>]\s*0\.\d+",  # p-value expressions
    r"\bsignificant(?:ly)?\b",
    r"\bobserved\b",
    r"\bmeasured\b",
    r"\bexperiment(?:al|ally)?\b",
    r"\bempirically?\b",
    r"\bdata\s+(?:show|suggest|indicate)\b",
    r"\bresults?\s+(?:show|indicate|confirm|suggest)\b",
    r"\bcorrelat(?:e|es|ed|ion)\b",
    r"\beffect\s+size\b",
    r"\bconfidence\s+interval\b",
    r"\bstatistic(?:al|ally)?\b",
]

_THEORETICAL_MARKERS: list[str] = [
    r"\bpropos(?:e|ed|ing)\b",
    r"\btheorem\b",
    r"\blemma\b",
    r"\bproof\b",
    r"\bformali(?:z|s)(?:e|ed|ation)\b",
    r"\bmodel\s+assumes?\b",
    r"\bframework\b",
    r"\baxiom\b",
    r"\bprincipl(?:e|es)\b",
    r"\btheoretical(?:ly)?\b",
    r"\banalytic(?:al|ally)?\s+(?:model|solution|framework)\b",
    r"\bderive[sd]?\b",
]

_COMPARATIVE_MARKERS: list[str] = [
    r"\bcompared?\s+(?:to|with)\b",
    r"\bbaseline\b",
    r"\boutperform(?:s|ed)?\b",
    r"\bversus\b",
    r"\bvs\.?\b",
    r"\bstate[- ]of[- ]the[- ]art\b",
    r"\bsota\b",
    r"\bbenchmark(?:ed)?\b",
    r"\bablation\b",
    r"\bsuperior\s+to\b",
    r"\bbetter\s+than\b",
    r"\bimprovement\s+over\b",
]

_METHODOLOGICAL_MARKERS: list[str] = [
    r"\bprocedure\b",
    r"\bprotocol\b",
    r"\bpipeline\b",
    r"\balgorithm\b",
    r"\bstep[- ]by[- ]step\b",
    r"\bworkflow\b",
    r"\bimplementation\b",
    r"\barchitecture\b",
    r"\bdesign\s+(?:of|for|pattern)\b",
    r"\bsystem\s+design\b",
    r"\bpropose\s+a\s+(?:novel\s+)?(?:method|approach|technique|framework)\b",
    r"\bour\s+(?:method|approach|system|framework)\b",
]

_BANKS: dict[ClaimType, list[str]] = {
    ClaimType.EMPIRICAL: _EMPIRICAL_MARKERS,
    ClaimType.THEORETICAL: _THEORETICAL_MARKERS,
    ClaimType.COMPARATIVE: _COMPARATIVE_MARKERS,
    ClaimType.METHODOLOGICAL: _METHODOLOGICAL_MARKERS,
}

_COMPILED: dict[ClaimType, list[re.Pattern[str]]] = {
    ct: [re.compile(m, re.I) for m in markers] for ct, markers in _BANKS.items()
}

# Tie threshold: if top two scores differ by <= this, result is UNKNOWN
_TIE_THRESHOLD = 0.05


class ClaimClassifier:
    """Classify the dominant academic claim type from document text.

    Usage::

        cc = ClaimClassifier()
        claim_type = cc.classify(abstract_text)
    """

    def classify(self, text: str) -> ClaimType:
        """Return the dominant ``ClaimType`` found in *text*.

        Prefers Abstract section if caller has already extracted it;
        otherwise analyses the full text (first 3000 chars for speed).
        """
        scan = text[:3000] if len(text) > 3000 else text
        scores = self._score_all(scan)
        return self._decide(scores)

    # ------------------------------------------------------------------

    def _score_all(self, text: str) -> dict[ClaimType, float]:
        """Compute normalised density for each claim type."""
        result: dict[ClaimType, float] = {}
        for ct, patterns in _COMPILED.items():
            hits = sum(1 for p in patterns if p.search(text))
            result[ct] = hits / len(patterns)  # fraction of bank matched
        return result

    def _decide(self, scores: dict[ClaimType, float]) -> ClaimType:
        if not scores:
            return ClaimType.UNKNOWN
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_type, top_score = sorted_types[0]
        if top_score == 0.0:
            return ClaimType.UNKNOWN
        if len(sorted_types) >= 2:
            _, second_score = sorted_types[1]
            if (top_score - second_score) <= _TIE_THRESHOLD:
                return ClaimType.UNKNOWN
        return top_type
