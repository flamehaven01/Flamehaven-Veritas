"""ReviewSimEngine — orchestrates multi-persona peer-review simulation.

Runs N reviewer personas (STRICT/BALANCED/LENIENT) in sequence, computes
calibrated omegas per persona, then aggregates via CrossValidator and DR3.

Thread safety: each call creates a fresh SciExpCritiqueEngine, so this engine
is safe to call from multiple threads (batch processing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..types import IRF6DScores
from .consensus import ConsensusResult, check_consensus
from .dr3 import DR3Protocol, DR3Resolution
from .persona import PersonaConfig, calibrate_omega, select_personas

_ACCEPT_THRESHOLD: float = 0.78
_REVISE_THRESHOLD: float = 0.60


def _recommendation(omega: float) -> str:
    if omega >= _ACCEPT_THRESHOLD:
        return "ACCEPT"
    if omega >= _REVISE_THRESHOLD:
        return "REVISE"
    return "REJECT"


@dataclass
class PersonaReview:
    """Critique result for a single reviewer persona."""

    persona: str
    min_omega: float
    base_omega: float
    calibrated_omega: float
    recommendation: str
    irf_dims: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "persona": self.persona,
            "min_omega": self.min_omega,
            "base_omega": self.base_omega,
            "calibrated_omega": self.calibrated_omega,
            "recommendation": self.recommendation,
            "irf_dims": dict(self.irf_dims),
        }

    def summary_line(self) -> str:
        return (
            f"  {self.persona:<12} base={self.base_omega:.3f}  "
            f"calibrated={self.calibrated_omega:.3f}  → {self.recommendation}"
        )


@dataclass
class ReviewSimResult:
    """Full output of a multi-reviewer simulation."""

    per_reviewer: list[PersonaReview]
    consensus: ConsensusResult
    dr3: DR3Resolution
    final_omega: float
    final_recommendation: str

    def as_dict(self) -> dict[str, object]:
        return {
            "per_reviewer": [r.as_dict() for r in self.per_reviewer],
            "consensus": self.consensus.as_dict(),
            "dr3": self.dr3.as_dict(),
            "final_omega": self.final_omega,
            "final_recommendation": self.final_recommendation,
        }

    def render_text(self) -> str:
        n = len(self.per_reviewer)
        lines = [
            f"VERITAS Review Simulation — {n} reviewer(s)",
            "-" * 48,
        ]
        for rev in self.per_reviewer:
            lines.append(rev.summary_line())
        lines.append("-" * 48)
        lines.append(self.consensus.summary_line())
        lines.append(self.dr3.summary_line())
        lines.append("-" * 48)
        lines.append(
            f"FINAL  omega={self.final_omega:.4f}  "
            f"→ [{self.final_recommendation}]"
        )
        return "\n".join(lines)


def _irf_to_dims(irf: IRF6DScores | None) -> dict[str, float]:
    if irf is None:
        return {}
    return {
        "M": round(irf.M, 4),
        "A": round(irf.A, 4),
        "D": round(irf.D, 4),
        "I": round(irf.I, 4),
        "F": round(irf.F, 4),
        "P": round(irf.P, 4),
    }


class ReviewSimEngine:
    """Run multi-persona peer-review simulation on a text corpus.

    Usage::

        engine = ReviewSimEngine()
        result = engine.run(text, reviewers=3)
        print(result.render_text())
    """

    def __init__(self, dr3_protocol: DR3Protocol | None = None) -> None:
        self._dr3 = dr3_protocol or DR3Protocol()

    def run(self, text: str, reviewers: int = 3) -> ReviewSimResult:
        """Run N reviewer personas and aggregate results.

        Args:
            text:      Full document text to critique.
            reviewers: Number of personas (2-3); capped at 3.

        Returns:
            ReviewSimResult with per-reviewer breakdowns + consensus.
        """
        from ..engine import SciExpCritiqueEngine

        personas: list[PersonaConfig] = select_personas(reviewers)
        base_engine = SciExpCritiqueEngine()

        # All personas critique the same text (engine is stateless per call)
        base_report = base_engine.critique(text)
        base_omega: float = base_report.omega_score or 0.0
        irf: IRF6DScores | None = base_report.irf_scores

        per_reviewer: list[PersonaReview] = []
        omegas: dict[str, float] = {}

        for persona in personas:
            if irf is not None:
                calibrated = calibrate_omega(irf, persona.dim_weights)
            else:
                # No IRF scores — apply persona min_omega as scaling factor
                scale = persona.min_omega / 0.78  # relative to balanced baseline
                calibrated = round(min(1.0, base_omega * scale), 4)

            rec = _recommendation_for_persona(calibrated, persona)
            per_reviewer.append(
                PersonaReview(
                    persona=persona.name,
                    min_omega=persona.min_omega,
                    base_omega=round(base_omega, 4),
                    calibrated_omega=calibrated,
                    recommendation=rec,
                    irf_dims=_irf_to_dims(irf),
                )
            )
            omegas[persona.name] = calibrated

        consensus = check_consensus(omegas)
        dr3 = self._dr3.resolve(consensus, omegas)
        final_omega = dr3.final_omega
        return ReviewSimResult(
            per_reviewer=per_reviewer,
            consensus=consensus,
            dr3=dr3,
            final_omega=final_omega,
            final_recommendation=_recommendation(final_omega),
        )


def _recommendation_for_persona(calibrated: float, persona: PersonaConfig) -> str:
    """Recommendation based on persona's own min_omega threshold."""
    if calibrated >= persona.min_omega:
        return "ACCEPT"
    # Below persona threshold — classify by absolute level
    if calibrated >= 0.60:
        return "REVISE"
    return "REJECT"
