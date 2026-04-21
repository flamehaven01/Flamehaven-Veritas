"""Hypothesis extractor for VERITAS — AI Critique Experimental Report Analysis Framework.

Extracts hypothesis statements, null hypotheses, and falsification
criteria from experimental report / paper text.

Attempts to import BioMedical-Paper-Harvester hypothesis_synthesis.py
(path: D:/Sanctum/BioMedical-Paper-Harvester) for BPH-integrated mode,
falls back to local pattern extraction otherwise.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

_BPH_PATH = r"D:\Sanctum\BioMedical-Paper-Harvester"

# Sentence splitter
_SENT_RE = re.compile(r"(?<=[.!?])\s+")

# Hypothesis claim patterns
_H_PATTERNS = [
    r"(?:we\s+)?hypothes[ie]s[ei]?\s+(?:that\s+)?(.+?[.!?])",
    r"hypothesis[:\s]+(.+?[.!?])",
    r"the\s+(?:main\s+)?(?:research\s+)?question\s+(?:is\s*)?[:\-]?\s*(.+?[.!?])",
    r"we\s+propose\s+(?:that\s+)?(.+?[.!?])",
    r"our\s+(?:primary\s+)?aim\s+(?:is\s+to\s+)?(.+?[.!?])",
    r"expected\s+(?:outcome|result|finding)[:\s]+(.+?[.!?])",
    r"this\s+(?:study|experiment|work)\s+(?:aims?\s+to\s+|seeks?\s+to\s+)(.+?[.!?])",
]

# Null hypothesis patterns
_H0_PATTERNS = [
    r"null\s+hypothesis[:\s]+(.+?[.!?])",
    r"h0[:\s]+(.+?[.!?])",
    r"no\s+significant\s+difference\s+(.+?[.!?])",
    r"there\s+is\s+no\s+(?:effect|difference|relationship)\s+(.+?[.!?])",
]

# Falsification criteria patterns
_FALSIF_PATTERNS = [
    r"(?:would\s+be\s+)?falsif(?:ied|iable)\s+(?:if|when)\s+(.+?[.!?])",
    r"disproved?\s+(?:if|when|by)\s+(.+?[.!?])",
    r"critical\s+test[:\s]+(.+?[.!?])",
    r"reject(?:ed)?\s+(?:if|when)\s+(.+?[.!?])",
    r"evidence\s+against[:\s]+(.+?[.!?])",
]


@dataclass
class ExtractionResult:
    """Hypothesis extraction output."""

    hypothesis: list[str] = field(default_factory=list)
    null_hypothesis: list[str] = field(default_factory=list)
    falsification_criteria: list[str] = field(default_factory=list)
    primary: str | None = None  # best-match hypothesis
    source: str = "local"

    def summary(self) -> str:
        parts = []
        if self.primary:
            parts.append(f"Primary hypothesis: {self.primary}")
        if self.null_hypothesis:
            parts.append(f"Null hypothesis: {self.null_hypothesis[0]}")
        if self.falsification_criteria:
            parts.append(f"Falsification criteria: {self.falsification_criteria[0]}")
        return "  ".join(parts) if parts else "(no hypothesis detected)"


def _extract_patterns(text: str, patterns: list[str]) -> list[str]:
    results: list[str] = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE | re.DOTALL):
            candidate = m.group(1).strip()
            # Cap at 200 chars to avoid capturing whole paragraphs
            if candidate and len(candidate) <= 200:
                results.append(candidate)
    return list(dict.fromkeys(results))  # deduplicate, preserve order


class HypothesisExtractor:
    """Extract hypothesis, null-H, and falsification criteria from text.

    Tries BioMedical-Paper-Harvester's hypothesis_synthesis module when
    available; falls back to local regex extraction.

    Usage::

        extractor = HypothesisExtractor()
        result = extractor.extract(text)
        print(result.primary)
    """

    def __init__(self) -> None:
        self._bph_synthesizer = None
        self._try_load_bph()

    def _try_load_bph(self) -> None:
        try:
            if _BPH_PATH not in sys.path:
                sys.path.insert(0, _BPH_PATH)
            from biomedical_harvester.hypothesis_synthesis import (  # type: ignore
                HypothesisSynthesizer,
            )

            self._bph_synthesizer = HypothesisSynthesizer()
        except Exception:
            self._bph_synthesizer = None

    def extract(self, text: str) -> ExtractionResult:
        """Extract hypothesis information from report text."""
        hypotheses = _extract_patterns(text, _H_PATTERNS)
        null_h = _extract_patterns(text, _H0_PATTERNS)
        falsif = _extract_patterns(text, _FALSIF_PATTERNS)
        primary = hypotheses[0] if hypotheses else None
        source = "local"

        # Enrich with BPH synthesizer when available
        if self._bph_synthesizer is not None:
            try:
                bph_result = self._bph_synthesizer.synthesize(text)
                if hasattr(bph_result, "primary") and bph_result.primary:
                    primary = str(bph_result.primary)
                if hasattr(bph_result, "hypotheses") and bph_result.hypotheses:
                    hypotheses = [str(h) for h in bph_result.hypotheses[:5]]
                source = "bph"
            except Exception:
                pass  # BPH synthesis failed; degrade gracefully to regex extraction

        return ExtractionResult(
            hypothesis=hypotheses,
            null_hypothesis=null_h,
            falsification_criteria=falsif,
            primary=primary,
            source=source,
        )
