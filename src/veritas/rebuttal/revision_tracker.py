"""RevisionTracker — compares two CritiqueReports to compute Revision Completeness Score.

Algorithm (v3.3):
  Given report_v1, report_v2:
    delta_omega  = v2.omega - v1.omega
    v1_issues    = {finding.code for step in v1.steps for finding in step.findings}
    v2_issues    = {finding.code for step in v2.steps for finding in step.findings}
    addressed    = v1_issues - v2_issues   (issues no longer present in v2)
    rcs          = |addressed| / |v1_issues|   (0.0 → 1.0)
    grade        = COMPLETE(>=0.80) | PARTIAL(>=0.50) | INSUFFICIENT(<0.50)

  Also compares priority_fix text using token-overlap heuristic:
    overlap_ratio = |tokens(v1_priority) ∩ tokens(v2_priority)| /
                    max(|tokens(v1_priority)|, 1)
  A falling overlap_ratio signals the priority concern changed (i.e., was addressed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from ..types import CritiqueReport

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class RevisionGrade(Enum):
    """Revision completeness assessment grade."""

    COMPLETE = "COMPLETE"       # RCS >= 0.80
    PARTIAL = "PARTIAL"         # RCS >= 0.50
    INSUFFICIENT = "INSUFFICIENT"  # RCS < 0.50


@dataclass
class RevisionResult:
    """Output of RevisionTracker.compare()."""

    delta_omega: float
    addressed_count: int
    total_v1_issues: int
    rcs: float
    revision_grade: RevisionGrade
    addressed_codes: list[str] = field(default_factory=list)
    remaining_codes: list[str] = field(default_factory=list)
    priority_overlap_ratio: float = 0.0
    improved: bool = False  # True if delta_omega > 0 AND rcs > 0

    def as_dict(self) -> dict:
        return {
            "delta_omega": round(self.delta_omega, 4),
            "addressed_count": self.addressed_count,
            "total_v1_issues": self.total_v1_issues,
            "rcs": round(self.rcs, 4),
            "revision_grade": self.revision_grade.value,
            "addressed_codes": self.addressed_codes,
            "remaining_codes": self.remaining_codes,
            "priority_overlap_ratio": round(self.priority_overlap_ratio, 4),
            "improved": self.improved,
        }


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"\b\w{3,}\b")


class RevisionTracker:
    """Compares two CritiqueReports to produce a RevisionResult.

    Usage::
        tracker = RevisionTracker()
        result = tracker.compare(report_v1, report_v2)
    """

    def compare(self, v1: CritiqueReport, v2: CritiqueReport) -> RevisionResult:
        """Compute revision completeness between v1 and v2 of a report.

        Args:
            v1: CritiqueReport from the first submission (original).
            v2: CritiqueReport from the revised submission.

        Returns:
            RevisionResult with RCS, grade, addressed/remaining issue codes, delta_omega.
        """
        delta_omega = v2.omega_score - v1.omega_score

        v1_codes = self._extract_finding_codes(v1)
        v2_codes = self._extract_finding_codes(v2)

        addressed_set = v1_codes - v2_codes
        remaining_set = v1_codes & v2_codes

        total = max(len(v1_codes), 1)  # avoid div-by-zero when no findings
        rcs = len(addressed_set) / total

        grade = self._grade(rcs)
        overlap = self._priority_overlap(v1.priority_fix, v2.priority_fix)

        # Edge case: no findings but omega improved → treat as PARTIAL
        if not v1_codes and delta_omega > 0.0:
            rcs = 0.5
            grade = RevisionGrade.PARTIAL

        return RevisionResult(
            delta_omega=delta_omega,
            addressed_count=len(addressed_set),
            total_v1_issues=len(v1_codes),
            rcs=rcs,
            revision_grade=grade,
            addressed_codes=sorted(addressed_set),
            remaining_codes=sorted(remaining_set),
            priority_overlap_ratio=overlap,
            improved=delta_omega > 0 and rcs > 0,
        )

    # ── private ──────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_finding_codes(report: CritiqueReport) -> set[str]:
        """Collect all StepFinding.code values across all steps."""
        codes: set[str] = set()
        for step in report.steps:
            for finding in step.findings:
                if finding.code:
                    codes.add(finding.code)
        return codes

    @staticmethod
    def _grade(rcs: float) -> RevisionGrade:
        if rcs >= 0.80:
            return RevisionGrade.COMPLETE
        if rcs >= 0.50:
            return RevisionGrade.PARTIAL
        return RevisionGrade.INSUFFICIENT

    @staticmethod
    def _priority_overlap(text_v1: str, text_v2: str) -> float:
        """Token-level Jaccard overlap of the two priority_fix strings.

        Falling ratio indicates the v2 priority concern changed (possibly addressed).
        """
        if not text_v1:
            return 1.0
        t1 = set(_TOKEN_RE.findall(text_v1.lower()))
        t2 = set(_TOKEN_RE.findall(text_v2.lower()))
        if not t1:
            return 1.0
        intersection = t1 & t2
        return len(intersection) / len(t1)
