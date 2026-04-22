"""CrossValidator — multi-reviewer consensus computation.

Extracted from Flamehaven-LOGOS CrossValidator (logos/cross_validator.py),
adapted for VERITAS peer-review simulation.

Consensus algorithm:
    omega_mean   = arithmetic mean of all persona calibrated omegas
    omega_var    = population variance across persona omegas
    reached      = True when (max - min) <= CONSENSUS_SPREAD_THRESHOLD

Recommendation mapping:
    omega >= 0.78  -> ACCEPT
    omega >= 0.60  -> REVISE
    omega <  0.60  -> REJECT
"""

from __future__ import annotations

from dataclasses import dataclass

# Consensus is reached when the max spread is within this bound
CONSENSUS_SPREAD_THRESHOLD: float = 0.30

# Recommendation breakpoints (mirrors LOGOS CalibrationGate defaults)
_ACCEPT_THRESHOLD: float = 0.78
_REVISE_THRESHOLD: float = 0.60


def _recommendation(omega: float) -> str:
    if omega >= _ACCEPT_THRESHOLD:
        return "ACCEPT"
    if omega >= _REVISE_THRESHOLD:
        return "REVISE"
    return "REJECT"


@dataclass
class ConsensusResult:
    """Aggregated cross-reviewer consensus output."""

    omegas: dict[str, float]
    consensus_omega: float
    variance: float
    spread: float
    reached: bool
    recommendation: str

    def as_dict(self) -> dict[str, object]:
        return {
            "omegas": dict(self.omegas),
            "consensus_omega": self.consensus_omega,
            "variance": self.variance,
            "spread": self.spread,
            "reached": self.reached,
            "recommendation": self.recommendation,
        }

    def summary_line(self) -> str:
        status = "REACHED" if self.reached else "LOW"
        return (
            f"Consensus: omega={self.consensus_omega:.3f} "
            f"var={self.variance:.4f} spread={self.spread:.3f} "
            f"[{status}] → {self.recommendation}"
        )


class CrossValidator:
    """Compute consensus from per-persona omega scores.

    Usage::

        cv = CrossValidator()
        result = cv.check_consensus({"strict": 0.72, "balanced": 0.79, "lenient": 0.81})
    """

    def __init__(
        self,
        spread_threshold: float = CONSENSUS_SPREAD_THRESHOLD,
    ) -> None:
        self._spread_threshold = spread_threshold

    def check_consensus(self, omegas: dict[str, float]) -> ConsensusResult:
        """Compute consensus metrics from {persona_name: calibrated_omega} dict."""
        if not omegas:
            return ConsensusResult(
                omegas={},
                consensus_omega=0.0,
                variance=0.0,
                spread=0.0,
                reached=False,
                recommendation="REJECT",
            )
        vals = list(omegas.values())
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        spread = max(vals) - min(vals)
        reached = spread <= self._spread_threshold
        return ConsensusResult(
            omegas=dict(omegas),
            consensus_omega=round(mean, 4),
            variance=round(variance, 6),
            spread=round(spread, 4),
            reached=reached,
            recommendation=_recommendation(mean),
        )


def check_consensus(
    omegas: dict[str, float],
    spread_threshold: float = CONSENSUS_SPREAD_THRESHOLD,
) -> ConsensusResult:
    """Module-level convenience wrapper for CrossValidator."""
    return CrossValidator(spread_threshold).check_consensus(omegas)
