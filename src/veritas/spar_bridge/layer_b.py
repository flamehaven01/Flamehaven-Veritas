"""SciExp Layer B — Interpretation Validity checks.

B1: Publication-readiness claim  — omega >= 0.70 required for "ready" language
B2: IRF alignment                — irf_composite direction must not contradict omega
B3: Overclaiming language        — "proves/conclusive/definitive" flagged as WARN
B4: Precheck confidence scope    — PARTIAL/LIMITED mode must dampen claim strength
"""

from __future__ import annotations

import re
from typing import Any

try:
    from spar_framework.result_types import CheckResult  # type: ignore[import]
except ImportError:
    from ._compat import CheckResult  # type: ignore[no-redef]

_OVERCLAIM_PATTERNS = [
    r"\bproves?\b",
    r"\bconclusive(?:ly)?\b",
    r"\bdefinitive(?:ly)?\b",
    r"\bground.?breaking\b",
    r"\bnever.?before\b",
    r"\bunambiguous(?:ly)?\b",
    r"\birrefutable\b",
    r"\bwithout\s+doubt\b",
]
_OVERCLAIM_RE = re.compile("|".join(_OVERCLAIM_PATTERNS), re.IGNORECASE)


def build_layer_b(
    *,
    subject: dict[str, Any],
    source: str,
    gate: str,
    report_text: str,
    context: dict[str, Any] | None = None,
) -> list[CheckResult]:
    del source, gate, context
    return [
        _check_b1(subject.get("omega_score", 0.0), report_text),
        _check_b2(subject.get("omega_score", 0.0), subject.get("irf_composite")),
        _check_b3(report_text),
        _check_b4(subject.get("precheck_mode", "FULL"), subject.get("omega_score", 0.0)),
    ]


# ── checks ────────────────────────────────────────────────────────────────────


def _check_b1(omega: float, report_text: str) -> CheckResult:
    pub_ready_language = bool(
        re.search(
            r"\b(publication.?ready|ready\s+for\s+publish|submit\s+to\s+journal|"
            r"camera.?ready|final\s+version|accepted\s+for)\b",
            report_text,
            re.IGNORECASE,
        )
    )
    if pub_ready_language and omega < 0.70:
        return CheckResult(
            check_id="B1",
            label="Publication-Readiness Claim",
            status="FAIL",
            detail=f"Publication-ready language detected but omega={omega:.4f} < 0.70. "
            "Interpretation exceeds what the quality surface justifies.",
        )
    if omega >= 0.80:
        return CheckResult(
            check_id="B1",
            label="Publication-Readiness Claim",
            status="PASS",
            detail=f"omega={omega:.4f} >= 0.80. Quality surface supports high-confidence claims.",
        )
    return CheckResult(
        check_id="B1",
        label="Publication-Readiness Claim",
        status="APPROXIMATION",
        detail=f"omega={omega:.4f}. Interpretation should reflect revision-needed state.",
    )


def _check_b2(omega: float, irf_composite: float | None) -> CheckResult:
    if irf_composite is None:
        return CheckResult(
            check_id="B2",
            label="IRF Alignment",
            status="PASS",
            detail="IRF not available — no cross-signal drift check performed.",
        )
    delta = abs(omega - irf_composite)
    if delta > 0.30 and omega > irf_composite:
        return CheckResult(
            check_id="B2",
            label="IRF Alignment",
            status="FAIL",
            detail=f"omega={omega:.4f} vs irf_composite={irf_composite:.4f} (delta={delta:.4f}). "
            "VERITAS omega substantially higher than LOGOS IRF reasoning score — "
            "surface-level traceability may be overstating confidence.",
        )
    if delta > 0.20:
        return CheckResult(
            check_id="B2",
            label="IRF Alignment",
            status="WARN",
            detail=f"omega={omega:.4f} vs irf_composite={irf_composite:.4f} (delta={delta:.4f}). "
            "Mild divergence between traceability signal and reasoning score.",
        )
    return CheckResult(
        check_id="B2",
        label="IRF Alignment",
        status="CONSISTENT",
        detail=f"omega={omega:.4f} and irf_composite={irf_composite:.4f} aligned (delta={delta:.4f}).",
    )


def _check_b3(report_text: str) -> CheckResult:
    if not report_text:
        return CheckResult(
            check_id="B3",
            label="Overclaiming Language",
            status="PASS",
            detail="No report text supplied for language scan.",
        )
    hits = _OVERCLAIM_RE.findall(report_text)
    unique_hits = list(dict.fromkeys(h.lower() for h in hits))
    if unique_hits:
        return CheckResult(
            check_id="B3",
            label="Overclaiming Language",
            status="WARN",
            detail=f"Overclaiming term(s) detected: {unique_hits}. "
            "Soften language to match actual evidence strength.",
        )
    return CheckResult(
        check_id="B3",
        label="Overclaiming Language",
        status="PASS",
        detail="No overclaiming patterns detected in report text.",
    )


def _check_b4(precheck_mode: str, omega: float) -> CheckResult:
    if precheck_mode in {"PARTIAL", "LIMITED"} and omega >= 0.80:
        return CheckResult(
            check_id="B4",
            label="Precheck Confidence Scope",
            status="FAIL",
            detail=f"omega={omega:.4f} >= 0.80 but PRECHECK={precheck_mode}. "
            "High omega claim is not supported under reduced artifact sufficiency.",
        )
    if precheck_mode in {"PARTIAL", "LIMITED"}:
        return CheckResult(
            check_id="B4",
            label="Precheck Confidence Scope",
            status="WARN",
            detail=f"PRECHECK={precheck_mode}: claim scope should be explicitly bounded "
            "by artifact sufficiency (not a complete evidence surface).",
        )
    return CheckResult(
        check_id="B4",
        label="Precheck Confidence Scope",
        status="PASS",
        detail=f"PRECHECK={precheck_mode}: full artifact surface — no scope dampening needed.",
    )
