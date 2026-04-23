"""veritas.rebuttal — Reviewer Rebuttal + Revision Intelligence (v3.3)."""

from .rebuttal_engine import RebuttalEngine, RebuttalItem, RebuttalReport
from .revision_tracker import RevisionGrade, RevisionResult, RevisionTracker

__all__ = [
    "RebuttalEngine",
    "RebuttalItem",
    "RebuttalReport",
    "RevisionTracker",
    "RevisionResult",
    "RevisionGrade",
]
