"""LOGOS IRF-Pipeline bridge for VERITAS — AI Critique Experimental Report Analysis Framework.

Attempts to use the real Flamehaven-LOGOS IRF pipeline (IRFPipeline) when
available at `D:/Sanctum/Flamehaven-LOGOS`.  Falls back to the offline
IRFAnalyzer when imports fail (no numpy, server unavailable, etc.).

Context building: extracts structural cues from report text to populate
the IRFPipeline context dict (premises, assumptions, observations, etc.).
"""
from __future__ import annotations

import re
import sys

from ..types import IRF6DScores
from .irf_analyzer import IRFAnalyzer

_LOGOS_PATH = r"D:\Sanctum\Flamehaven-LOGOS"


def _build_irf_context(text: str) -> dict:
    """Extract IRF context keys from free-text experimental report.

    Returns dict compatible with Flamehaven-LOGOS IRFPipeline.run(query, context).
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)

    def _collect(markers: list[str]) -> list[str]:
        return [s.strip() for s in sentences
                if any(m.lower() in s.lower() for m in markers)][:5]

    return {
        "premises":            _collect(["assume", "given", "premise", "based on"]),
        "assumptions":         _collect(["assumption", "we assume", "suppose"]),
        "domain_knowledge":    _collect(["prior", "background", "known", "established"]),
        "observations":        _collect(["observed", "measured", "found", "result"]),
        "counterexamples":     _collect(["however", "except", "but", "contradict"]),
        "falsifiable":         _collect(["falsif", "null", "test", "disprove"]),
        "paradigm":            _collect(["reference", "et al", "doi", "baseline"]),
        "theoretical_grounding": _collect(["theory", "model", "framework"]),
    }


class LogosBridge:
    """Run LOGOS IRF-6D scoring, preferring the real pipeline.

    Priority:
      1. Flamehaven-LOGOS IRFPipeline (requires numpy + local install)
      2. IRFAnalyzer (offline heuristic — always available)
    """

    def __init__(self) -> None:
        self._pipeline = None
        self._try_load_pipeline()
        self._local = IRFAnalyzer()

    def _try_load_pipeline(self) -> None:
        try:
            if _LOGOS_PATH not in sys.path:
                sys.path.insert(0, _LOGOS_PATH)
            from irf.pipeline import IRFPipeline  # type: ignore
            self._pipeline = IRFPipeline()
        except Exception:
            self._pipeline = None

    @property
    def source(self) -> str:
        return "logos_irf_pipeline" if self._pipeline is not None else "local"

    def analyze(self, text: str, central_claim: str | None = None) -> IRF6DScores:
        """Return IRF6DScores using best available backend.

        Args:
            text:          Full report text for context extraction.
            central_claim: Primary claim or hypothesis text (used as query).
        """
        query = central_claim or (text[:200] if text else "experimental report")
        if self._pipeline is not None:
            return self._run_pipeline(query, text)
        return self._local.score(text, source="local")

    def _run_pipeline(self, query: str, text: str) -> IRF6DScores:
        try:
            ctx = _build_irf_context(text)
            result = self._pipeline.run(query, ctx)
            sc = result.score
            # IRFResult has .continuous per-dimension dict + .passed
            dims   = sc.continuous if hasattr(sc, "continuous") else {}
            M = float(dims.get("M", 0.0))
            A = float(dims.get("A", 0.0))
            D = float(dims.get("D", 0.0))
            I = float(dims.get("I", 0.0))  # noqa: E741
            F = float(dims.get("F", 0.0))
            P = float(dims.get("P", 0.0))
            composite = float(sc.composite) if hasattr(sc, "composite") else (
                (M + A + D + I + F + P) / 6.0
            )
            return IRF6DScores(
                M=round(M, 4), A=round(A, 4), D=round(D, 4),
                I=round(I, 4), F=round(F, 4), P=round(P, 4),
                composite=round(composite, 4),
                passed=bool(getattr(sc, "passed", composite >= 0.65)),
                source="logos_irf_pipeline",
            )
        except Exception:
            # Pipeline available but raised — fall back gracefully
            return self._local.score(text, source="local")
