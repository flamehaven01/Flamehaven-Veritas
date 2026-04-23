"""Journal profiles — acceptance threshold configurations per journal tier.

Each profile defines:
  accept_omega  : minimum omega for ACCEPT recommendation
  revise_omega  : minimum omega for MAJOR/MINOR REVISION (reject if below)
  step_weights  : per-step IRF dimension multipliers applied before omega recalibration
  name          : human-readable label

Algorithm reference (v3.3):
  calibrated_omega = clamp(
      sum(step.score * profile.step_weights.get(step.step_id, 1.0) * step.weight
          for step in report.steps)
      / sum(step.weight for step in report.steps),
      0.0, 1.0
  )
  verdict = ACCEPT if calibrated >= accept_omega
            REVISE if calibrated >= revise_omega
            REJECT otherwise

Profile data is pure config — no logic lives here.
This file is exempt from the 250-line ceiling (pure data definition).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class JournalVerdict(Enum):
    """Submission recommendation after journal calibration."""

    ACCEPT = "ACCEPT"
    REVISE = "REVISE"
    REJECT = "REJECT"


@dataclass(frozen=True)
class JournalProfile:
    """Immutable profile for a journal tier.

    Attributes:
        key          : Short identifier used in CLI (e.g. 'nature', 'ieee').
        name         : Human-readable journal/tier name.
        accept_omega : Omega threshold for ACCEPT recommendation.
        revise_omega : Omega threshold for REVISE recommendation (reject if below).
        step_weights : Multipliers per step_id. Missing keys default to 1.0.
        description  : Short one-line description.
    """

    key: str
    name: str
    accept_omega: float
    revise_omega: float
    step_weights: dict = field(default_factory=dict, compare=False)
    description: str = ""

    def verdict_for(self, omega: float) -> JournalVerdict:
        """Return verdict enum for a raw omega value (before calibration)."""
        if omega >= self.accept_omega:
            return JournalVerdict.ACCEPT
        if omega >= self.revise_omega:
            return JournalVerdict.REVISE
        return JournalVerdict.REJECT

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "accept_omega": self.accept_omega,
            "revise_omega": self.revise_omega,
            "step_weights": dict(self.step_weights),
            "description": self.description,
        }


# ---------------------------------------------------------------------------
# Built-in profiles
# ---------------------------------------------------------------------------
# Step IDs: "1" = Claim Integrity, "2" = Traceability, "3" = Series Continuity,
#           "4" = Publication Readiness, "5" = Priority Fix
# Higher multiplier → that dimension weighs more in calibrated_omega.

JOURNAL_PROFILES: dict[str, JournalProfile] = {
    "nature": JournalProfile(
        key="nature",
        name="Nature / Nature Portfolio",
        accept_omega=0.92,
        revise_omega=0.75,
        step_weights={"1": 1.6, "2": 1.6, "3": 1.2, "4": 1.0, "5": 1.4},
        description="Top-tier multidisciplinary; claims and reproducibility heavily weighted.",
    ),
    "ieee": JournalProfile(
        key="ieee",
        name="IEEE Transactions (generic)",
        accept_omega=0.85,
        revise_omega=0.68,
        step_weights={"1": 1.3, "2": 1.5, "3": 1.2, "4": 1.1, "5": 1.2},
        description="Engineering/CS focus; data traceability and methodology continuity prioritized.",
    ),
    "lancet": JournalProfile(
        key="lancet",
        name="The Lancet / Lancet family",
        accept_omega=0.90,
        revise_omega=0.72,
        step_weights={"1": 1.4, "2": 1.5, "3": 1.3, "4": 1.2, "5": 1.5},
        description="Clinical medicine; intervention claims and statistical integrity paramount.",
    ),
    "q1": JournalProfile(
        key="q1",
        name="CORE Q1 / Scopus Q1 (generic)",
        accept_omega=0.85,
        revise_omega=0.65,
        step_weights={"1": 1.2, "2": 1.2, "3": 1.1, "4": 1.0, "5": 1.1},
        description="High-impact indexed journals; balanced weighting across all steps.",
    ),
    "q2": JournalProfile(
        key="q2",
        name="CORE Q2 / Scopus Q2 (generic)",
        accept_omega=0.78,
        revise_omega=0.60,
        step_weights={"1": 1.1, "2": 1.1, "3": 1.0, "4": 1.0, "5": 1.0},
        description="Mid-tier indexed journals; slight emphasis on claims.",
    ),
    "q3": JournalProfile(
        key="q3",
        name="CORE Q3 / Scopus Q3 (generic)",
        accept_omega=0.70,
        revise_omega=0.55,
        step_weights={"1": 1.0, "2": 1.0, "3": 1.0, "4": 1.0, "5": 1.0},
        description="Lower-tier indexed journals; uniform step weighting.",
    ),
    "default": JournalProfile(
        key="default",
        name="Default (pre-v3.3 behavior)",
        accept_omega=0.78,
        revise_omega=0.60,
        step_weights={},
        description="Fallback profile matching the VERITAS v3.2 scoring behavior.",
    ),
}


def get_profile(key: str) -> JournalProfile:
    """Return JournalProfile for key. Raises KeyError for unknown keys."""
    key = key.lower().strip()
    if key not in JOURNAL_PROFILES:
        valid = ", ".join(sorted(JOURNAL_PROFILES))
        raise KeyError(f"Unknown journal profile '{key}'. Valid: {valid}")
    return JOURNAL_PROFILES[key]
