"""Maps a VERITAS CritiqueReport to a SPAR subject dict."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from veritas.types import CritiqueReport


def report_to_subject(report: CritiqueReport) -> dict[str, Any]:
    """Flatten CritiqueReport into a SPAR subject dict.

    All numeric fields are 0-1 floats.  None means the sub-engine was absent.
    """
    total = sum(len(s.findings) for s in report.steps)
    from veritas.types import TraceabilityClass
    traceable = sum(
        1 for s in report.steps for f in s.findings
        if f.traceability == TraceabilityClass.TRACEABLE
    )
    partial = sum(
        1 for s in report.steps for f in s.findings
        if f.traceability == TraceabilityClass.PARTIALLY_TRACEABLE
    )
    not_tr = sum(
        1 for s in report.steps for f in s.findings
        if f.traceability == TraceabilityClass.NOT_TRACEABLE
    )
    traceability_ratio = traceable / total if total else 1.0

    repro_completeness: float | None = None
    if report.reproducibility_checklist is not None:
        items = report.reproducibility_checklist.items or {}
        tot = len(items)
        sat = sum(1 for v in items.values() if v is True)
        repro_completeness = sat / tot if tot else None

    return {
        # Core VERITAS signals
        "omega_score":             report.omega_score,
        "traceability_ratio":      round(traceability_ratio, 4),
        "not_traceable_count":     not_tr,
        "partially_traceable_count": partial,
        "precheck_mode":           report.precheck.mode.value,
        "round_number":            report.round_number,
        "experiment_class":        report.experiment_class.value if report.experiment_class else None,
        # LOGOS enrichment (may be None)
        "irf_composite":           report.irf_scores.composite if report.irf_scores else None,
        "irf_passed":              report.irf_scores.passed if report.irf_scores else None,
        "methodology_class":       report.methodology_class.value if report.methodology_class else None,
        # Repo-derived
        "bibliography_quality":    (
            report.bibliography_stats.quality_score if report.bibliography_stats else None
        ),
        "repro_completeness":      repro_completeness,
    }
