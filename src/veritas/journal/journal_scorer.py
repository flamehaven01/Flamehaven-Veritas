"""JournalScorer — applies journal-specific weight calibration to CritiqueReport omega.

Algorithm (v3.3):
  1. For each StepResult, multiply its fractional contribution by profile.step_weights.get(step_id, 1.0)
  2. Re-normalise to [0.0, 1.0]
  3. Apply verdict threshold from JournalProfile
  4. Compute omega_delta = calibrated_omega - raw_omega (positive = journal rewards this paper's strengths)

No external imports — all computation is pure Python arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..types import CritiqueReport
from .journal_profiles import JournalProfile, JournalVerdict, get_profile


@dataclass
class JournalScoringResult:
    """Output of JournalScorer.score()."""

    journal_key: str
    journal_name: str
    raw_omega: float
    calibrated_omega: float
    omega_delta: float         # calibrated - raw; positive means journal rewards paper
    verdict: JournalVerdict
    accept_threshold: float
    revise_threshold: float
    step_contributions: dict   # step_id -> {"raw": float, "weighted": float, "multiplier": float}

    def as_dict(self) -> dict:
        return {
            "journal_key": self.journal_key,
            "journal_name": self.journal_name,
            "raw_omega": round(self.raw_omega, 4),
            "calibrated_omega": round(self.calibrated_omega, 4),
            "omega_delta": round(self.omega_delta, 4),
            "verdict": self.verdict.value,
            "accept_threshold": self.accept_threshold,
            "revise_threshold": self.revise_threshold,
            "step_contributions": {
                k: {kk: round(vv, 4) for kk, vv in v.items()}
                for k, v in self.step_contributions.items()
            },
        }


class JournalScorer:
    """Computes journal-calibrated omega from a CritiqueReport.

    Usage::
        scorer = JournalScorer()
        result = scorer.score(report, journal="nature")
        print(result.verdict.value, result.calibrated_omega)
    """

    def score(
        self, report: CritiqueReport, journal: str = "default"
    ) -> JournalScoringResult:
        """Score a CritiqueReport against a journal profile.

        Args:
            report:  Completed CritiqueReport from SciExpCritiqueEngine.critique().
            journal: Journal key string (e.g. 'nature', 'ieee', 'q1'). Default: 'default'.

        Returns:
            JournalScoringResult with calibrated omega, verdict, and step breakdown.

        Raises:
            KeyError: If journal key is not found in JOURNAL_PROFILES.
        """
        profile = get_profile(journal)
        return self._compute(report, profile)

    def score_with_profile(
        self, report: CritiqueReport, profile: JournalProfile
    ) -> JournalScoringResult:
        """Score using a pre-resolved JournalProfile object."""
        return self._compute(report, profile)

    # ── private ──────────────────────────────────────────────────────────────

    def _compute(self, report: CritiqueReport, profile: JournalProfile) -> JournalScoringResult:
        raw_omega = report.omega_score
        active_steps = [s for s in report.steps if not s.not_applicable]

        if not active_steps:
            # No steps — use raw omega with no calibration
            return JournalScoringResult(
                journal_key=profile.key,
                journal_name=profile.name,
                raw_omega=raw_omega,
                calibrated_omega=raw_omega,
                omega_delta=0.0,
                verdict=profile.verdict_for(raw_omega),
                accept_threshold=profile.accept_omega,
                revise_threshold=profile.revise_omega,
                step_contributions={},
            )

        # Compute per-step quality scores from findings (traceability-based)
        # Then apply profile multipliers in a proper weighted average:
        #   calibrated = sum(q_i * m_i * w_i) / sum(m_i * w_i)
        weighted_sum = 0.0
        weight_total = 0.0
        contributions = {}

        for step in active_steps:
            multiplier = profile.step_weights.get(step.step_id, 1.0)
            step_quality = self._step_quality(step)          # [0.0, 1.0]
            effective_weight = step.weight * multiplier
            weighted_sum += step_quality * effective_weight
            weight_total += effective_weight
            contributions[step.step_id] = {
                "raw": step_quality,
                "weighted": round(step_quality * multiplier, 4),
                "multiplier": multiplier,
            }

        if weight_total == 0.0:
            calibrated = raw_omega
        else:
            calibrated = min(max(weighted_sum / weight_total, 0.0), 1.0)

        return JournalScoringResult(
            journal_key=profile.key,
            journal_name=profile.name,
            raw_omega=raw_omega,
            calibrated_omega=calibrated,
            omega_delta=calibrated - raw_omega,
            verdict=profile.verdict_for(calibrated),
            accept_threshold=profile.accept_omega,
            revise_threshold=profile.revise_omega,
            step_contributions=contributions,
        )

    @staticmethod
    def _step_quality(step) -> float:
        """Compute a [0.0, 1.0] quality score for one step from its findings.

        No findings → 1.0 (no issues detected).
        Each NOT_TRACEABLE finding contributes full penalty (1.0).
        Each PARTIALLY_TRACEABLE finding contributes half penalty (0.5).
        TRACEABLE findings contribute no penalty.
        Final score = 1.0 - (total_penalty / total_findings), clamped to [0, 1].
        """
        if not step.findings:
            return 1.0
        from ..types import TraceabilityClass

        NOT = TraceabilityClass.NOT_TRACEABLE
        PART = TraceabilityClass.PARTIALLY_TRACEABLE
        penalty = sum(
            1.0 if f.traceability == NOT else 0.5 if f.traceability == PART else 0.0
            for f in step.findings
        )
        return max(1.0 - penalty / len(step.findings), 0.0)
