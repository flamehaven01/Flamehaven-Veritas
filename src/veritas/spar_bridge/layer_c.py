"""SciExp Layer C — Existence and Maturity probes.

C1: IRF maturity state        — classify reasoning depth as genuine/approximate/partial
C2: Reproducibility coverage  — based on repro_completeness ratio
C3: Bibliography adequacy     — based on bibliography_quality score
C4: Methodology disclosure    — UNKNOWN class = environment_conditional risk
"""

from __future__ import annotations

from typing import Any

from spar_framework.result_types import CheckResult


def build_layer_c(
    *,
    subject: dict[str, Any],
    source: str,
    gate: str,
    params: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> list[CheckResult]:
    del source, gate, params, context
    return [
        _check_c1(subject.get("irf_composite"), subject.get("irf_passed")),
        _check_c2(subject.get("repro_completeness")),
        _check_c3(subject.get("bibliography_quality")),
        _check_c4(subject.get("methodology_class")),
    ]


# ── checks ────────────────────────────────────────────────────────────────────

def _check_c1(irf_composite: float | None, irf_passed: bool | None) -> CheckResult:
    """IRF-based reasoning maturity: genuine >= 0.78, approximate >= 0.60, partial below."""
    if irf_composite is None:
        return CheckResult(
            check_id="C1",
            label="IRF Reasoning Maturity",
            status="APPROXIMATION",
            detail="LOGOS IRF-Calc not available. Reasoning maturity is environment_conditional "
                   "— cannot confirm genuine depth without IRF signal.",
        )
    if irf_composite >= 0.78 and irf_passed:
        return CheckResult(
            check_id="C1",
            label="IRF Reasoning Maturity",
            status="GENUINE",
            detail=f"irf_composite={irf_composite:.4f} >= 0.78 and passed. "
                   "Reasoning depth verified across all 6 dimensions (M/A/D/I/F/P).",
        )
    if irf_composite >= 0.60:
        return CheckResult(
            check_id="C1",
            label="IRF Reasoning Maturity",
            status="APPROXIMATION",
            detail=f"irf_composite={irf_composite:.4f}: reasoning present but below full LOGOS threshold. "
                   "Some dimensions may be weakly supported.",
        )
    return CheckResult(
        check_id="C1",
        label="IRF Reasoning Maturity",
        status="PARTIAL",
        detail=f"irf_composite={irf_composite:.4f} < 0.60. "
               "Reasoning is partial — significant dimension gaps detected.",
    )


def _check_c2(repro_completeness: float | None) -> CheckResult:
    """Reproducibility checklist coverage maturity."""
    if repro_completeness is None:
        return CheckResult(
            check_id="C2",
            label="Reproducibility Coverage",
            status="APPROXIMATION",
            detail="Reproducibility checklist not available. "
                   "Coverage maturity is environment_conditional.",
        )
    if repro_completeness >= 0.80:
        return CheckResult(
            check_id="C2",
            label="Reproducibility Coverage",
            status="GENUINE",
            detail=f"Reproducibility completeness {repro_completeness:.2%} >= 80%. "
                   "Strong method documentation coverage.",
        )
    if repro_completeness >= 0.50:
        return CheckResult(
            check_id="C2",
            label="Reproducibility Coverage",
            status="APPROXIMATION",
            detail=f"Reproducibility completeness {repro_completeness:.2%}: partial coverage. "
                   "Some ARRIVE/CONSORT criteria not met.",
        )
    return CheckResult(
        check_id="C2",
        label="Reproducibility Coverage",
        status="PARTIAL",
        detail=f"Reproducibility completeness {repro_completeness:.2%} < 50%. "
               "Insufficient method documentation for independent replication.",
    )


def _check_c3(bibliography_quality: float | None) -> CheckResult:
    """Bibliography quality signal for reference adequacy."""
    if bibliography_quality is None:
        return CheckResult(
            check_id="C3",
            label="Bibliography Adequacy",
            status="APPROXIMATION",
            detail="Bibliography analyzer not available. "
                   "Reference quality maturity is environment_conditional.",
        )
    if bibliography_quality >= 0.70:
        return CheckResult(
            check_id="C3",
            label="Bibliography Adequacy",
            status="GENUINE",
            detail=f"Bibliography quality={bibliography_quality:.4f} >= 0.70. "
                   "Reference surface supports claimed scope.",
        )
    if bibliography_quality >= 0.40:
        return CheckResult(
            check_id="C3",
            label="Bibliography Adequacy",
            status="APPROXIMATION",
            detail=f"Bibliography quality={bibliography_quality:.4f}: reference surface is partial. "
                   "Recency or breadth below recommended levels.",
        )
    return CheckResult(
        check_id="C3",
        label="Bibliography Adequacy",
        status="PARTIAL",
        detail=f"Bibliography quality={bibliography_quality:.4f} < 0.40. "
               "Weak reference surface — claims may lack adequate literature grounding.",
    )


def _check_c4(methodology_class: str | None) -> CheckResult:
    """Methodology disclosure maturity."""
    if methodology_class is None or methodology_class == "UNKNOWN":
        return CheckResult(
            check_id="C4",
            label="Methodology Disclosure",
            status="RESEARCH_ONLY",
            detail="Methodology class is UNKNOWN or undetectable. "
                   "Cannot confirm design validity without disclosed methodology. "
                   "State is research_only — not ready for governance-level review.",
        )
    standard_methods = {"RCT", "META_ANALYSIS", "COHORT", "EXPERIMENTAL"}
    if methodology_class in standard_methods:
        return CheckResult(
            check_id="C4",
            label="Methodology Disclosure",
            status="GENUINE",
            detail=f"Methodology={methodology_class} — standard design with well-defined "
                   "validity criteria. Full governance review applicable.",
        )
    return CheckResult(
        check_id="C4",
        label="Methodology Disclosure",
        status="APPROXIMATION",
        detail=f"Methodology={methodology_class} — recognised but non-standard design. "
               "Apply design-specific validity criteria before governance-level conclusions.",
    )
