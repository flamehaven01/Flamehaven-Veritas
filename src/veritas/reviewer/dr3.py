"""DR3 Protocol — Disputed Review Resolution Round.

Triggered when consensus_omega < 0.60 (irreconcilable reviewer conflict).
Extracted from LOGOS DR3Protocol (logos/dr3_protocol.py).

DR3 tiebreaker rule:
    1. Use BALANCED persona as authoritative tiebreaker
    2. Apply soft penalty: final_omega = balanced_omega * DR3_PENALTY_FACTOR
    3. Annotate output with conflict metadata

The 0.90 penalty factor reflects epistemic uncertainty when reviewers cannot
agree — the final score is slightly discounted to signal contested quality.
"""

from __future__ import annotations

from dataclasses import dataclass

from .consensus import ConsensusResult

# Consensus floor below which DR3 is triggered
DR3_TRIGGER_THRESHOLD: float = 0.60

# Soft penalty applied to tiebreaker omega when DR3 fires
DR3_PENALTY_FACTOR: float = 0.90

_TIEBREAKER_PERSONA: str = "balanced"


@dataclass
class DR3Resolution:
    """Output of DR3 conflict resolution."""

    conflict_detected: bool
    tiebreaker_persona: str
    final_omega: float
    resolution_note: str

    def as_dict(self) -> dict[str, object]:
        return {
            "conflict_detected": self.conflict_detected,
            "tiebreaker_persona": self.tiebreaker_persona,
            "final_omega": self.final_omega,
            "resolution_note": self.resolution_note,
        }

    def summary_line(self) -> str:
        if not self.conflict_detected:
            return "DR3: Not triggered (consensus >= 0.60)"
        return (
            f"DR3: CONFLICT — tiebreaker={self.tiebreaker_persona} "
            f"final_omega={self.final_omega:.3f} | {self.resolution_note}"
        )


class DR3Protocol:
    """Resolve multi-reviewer conflicts via tiebreaker + penalty.

    Usage::

        dr3 = DR3Protocol()
        resolution = dr3.resolve(consensus, per_persona_omegas)
    """

    def __init__(
        self,
        trigger_threshold: float = DR3_TRIGGER_THRESHOLD,
        penalty_factor: float = DR3_PENALTY_FACTOR,
        tiebreaker: str = _TIEBREAKER_PERSONA,
    ) -> None:
        self._trigger = trigger_threshold
        self._penalty = penalty_factor
        self._tiebreaker = tiebreaker

    def resolve(
        self,
        consensus: ConsensusResult,
        per_persona_omegas: dict[str, float],
    ) -> DR3Resolution:
        """Evaluate whether DR3 applies; return resolution with final omega."""
        if consensus.consensus_omega >= self._trigger:
            return DR3Resolution(
                conflict_detected=False,
                tiebreaker_persona=self._tiebreaker,
                final_omega=consensus.consensus_omega,
                resolution_note="Consensus >= 0.60; no conflict detected.",
            )
        # DR3 triggered — use tiebreaker persona with penalty
        tb_omega = per_persona_omegas.get(self._tiebreaker, consensus.consensus_omega)
        penalized = round(tb_omega * self._penalty, 4)
        note = (
            f"consensus_omega={consensus.consensus_omega:.3f} < {self._trigger:.2f}; "
            f"spread={consensus.spread:.3f}. "
            f"Tiebreaker ({self._tiebreaker}) omega={tb_omega:.3f} "
            f"× penalty({self._penalty}) = {penalized:.3f}."
        )
        return DR3Resolution(
            conflict_detected=True,
            tiebreaker_persona=self._tiebreaker,
            final_omega=penalized,
            resolution_note=note,
        )
