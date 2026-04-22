"""Reviewer personas — calibrated omega thresholds (extracted from LOGOS CalibrationGate).

Each persona applies dimension-specific weights to the IRF-6D score vector,
producing a calibrated_omega that reflects the reviewer's analytical bias.

Calibration formula (adapted from LOGOS CalibrationGate v2.7.2):
    calibrated = sum(w_d * score_d for d in MADIFP) / sum(w_d)

Weight rationale:
    strict   — elevated M+D (methodology rigor) + F (falsifiability)
    balanced — unit weights, mirrors standard VERITAS scoring
    lenient  — down-weighted M+D+F, rewards novelty via A+I+P
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..types import IRF6DScores

# IRF-6D dimension keys in canonical order
_DIMS = ("M", "A", "D", "I", "F", "P")


@dataclass(frozen=True)
class PersonaConfig:
    """Calibration profile for a single peer-reviewer persona."""

    name: str
    min_omega: float
    dim_weights: dict[str, float]
    description: str

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "min_omega": self.min_omega,
            "dim_weights": dict(self.dim_weights),
            "description": self.description,
        }


def calibrate_omega(irf: IRF6DScores, weights: dict[str, float]) -> float:
    """Apply per-dimension weights and return calibrated omega (0-1).

    Args:
        irf:     IRF-6D scores from LOGOS pipeline or local analyzer.
        weights: Per-dimension multiplier map; missing dims default to 1.0.

    Returns:
        Weighted mean of the 6 IRF dimensions, clamped to [0, 1].
    """
    raw = {"M": irf.M, "A": irf.A, "D": irf.D, "I": irf.I, "F": irf.F, "P": irf.P}
    total_w = sum(weights.get(d, 1.0) for d in _DIMS)
    if total_w == 0.0:
        return irf.composite
    weighted_sum = sum(weights.get(d, 1.0) * raw[d] for d in _DIMS)
    return round(min(1.0, max(0.0, weighted_sum / total_w)), 4)


# ── Canonical persona presets ─────────────────────────────────────────────────

STRICT = PersonaConfig(
    name="strict",
    min_omega=0.85,
    dim_weights={"M": 1.4, "A": 1.0, "D": 1.4, "I": 1.0, "F": 1.3, "P": 1.0},
    description=(
        "High methodology & reproducibility standards. "
        "Represents a rigorous primary reviewer who demands strong "
        "falsifiability (F) and methodological soundness (M, D)."
    ),
)

BALANCED = PersonaConfig(
    name="balanced",
    min_omega=0.78,
    dim_weights={"M": 1.0, "A": 1.0, "D": 1.0, "I": 1.0, "F": 1.0, "P": 1.0},
    description=(
        "Standard VERITAS calibration (unit weights). "
        "Mirrors the baseline critique engine scoring. "
        "Acts as tiebreaker in DR3 conflict resolution."
    ),
)

LENIENT = PersonaConfig(
    name="lenient",
    min_omega=0.70,
    dim_weights={"M": 0.85, "A": 1.0, "D": 0.85, "I": 1.0, "F": 0.80, "P": 1.0},
    description=(
        "Novelty-weighted calibration. Down-weights methodology strictness. "
        "Represents a subject-matter expert who values innovative insights "
        "over perfect reproducibility."
    ),
)

# Ordered by strictness (ascending min_omega)
_PERSONAS_ALL: list[PersonaConfig] = [STRICT, BALANCED, LENIENT]


def select_personas(n: int) -> list[PersonaConfig]:
    """Return the first N personas from [STRICT, BALANCED, LENIENT].

    n=2 → [STRICT, BALANCED]
    n=3 → [STRICT, BALANCED, LENIENT]
    n>3 → [STRICT, BALANCED, LENIENT] (capped)
    """
    n = max(2, min(n, len(_PERSONAS_ALL)))
    return _PERSONAS_ALL[:n]
