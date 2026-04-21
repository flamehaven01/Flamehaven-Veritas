"""SciExp Layer A — Anchor Consistency checks.

A1: Claim presence gate    — PRECHECK not BLOCKED
A2: Traceability floor     — ratio >= 0.30 (below = ANOMALY)
A3: Omega-gate agreement   — ACCEPT gate requires omega >= 0.60
A4: Round-1 integrity      — round 1 fully NOT_TRACEABLE = ANOMALY
"""

from __future__ import annotations

from typing import Any

try:
    from spar_framework.result_types import CheckResult  # type: ignore[import]
except ImportError:
    from ._compat import CheckResult  # type: ignore[no-redef]


def build_layer_a(
    *,
    subject: dict[str, Any],
    source: str,
    gate: str,
    params: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> list[CheckResult]:
    del source, params, context
    return [
        _check_a1(subject.get("precheck_mode", "FULL")),
        _check_a2(subject.get("traceability_ratio", 1.0)),
        _check_a3(subject.get("omega_score", 0.0), gate),
        _check_a4(
            subject.get("traceability_ratio", 1.0),
            subject.get("round_number", 1),
            subject.get("not_traceable_count", 0),
        ),
    ]


# ── checks ────────────────────────────────────────────────────────────────────


def _check_a1(precheck_mode: str) -> CheckResult:
    if precheck_mode == "BLOCKED":
        return CheckResult(
            check_id="A1",
            label="Claim Presence Gate",
            status="ANOMALY",
            detail="PRECHECK=BLOCKED: no evaluable claim found. "
            "Cannot anchor a review without an extractable claim.",
        )
    label_map = {"FULL": "CONSISTENT", "PARTIAL": "WARN", "LIMITED": "WARN"}
    status = label_map.get(precheck_mode, "PASS")
    return CheckResult(
        check_id="A1",
        label="Claim Presence Gate",
        status=status,
        detail=f"PRECHECK={precheck_mode}. "
        + (
            "All required artifacts present."
            if precheck_mode == "FULL"
            else f"Artifact sufficiency reduced ({precheck_mode}) — interpretation scope limited."
        ),
    )


def _check_a2(traceability_ratio: float) -> CheckResult:
    if traceability_ratio < 0.30:
        return CheckResult(
            check_id="A2",
            label="Traceability Floor",
            status="ANOMALY",
            detail=f"Traceability ratio {traceability_ratio:.2%} < 30% floor. "
            "Findings cannot be anchored to verifiable evidence.",
        )
    if traceability_ratio < 0.60:
        return CheckResult(
            check_id="A2",
            label="Traceability Floor",
            status="WARN",
            detail=f"Traceability ratio {traceability_ratio:.2%} — low coverage. "
            "Partial evidence anchoring only.",
        )
    return CheckResult(
        check_id="A2",
        label="Traceability Floor",
        status="CONSISTENT",
        detail=f"Traceability ratio {traceability_ratio:.2%} meets anchor threshold.",
    )


def _check_a3(omega: float, gate: str) -> CheckResult:
    gate_upper = gate.upper() if gate else ""
    if gate_upper in {"ACCEPT", "PASS"} and omega < 0.60:
        return CheckResult(
            check_id="A3",
            label="Omega-Gate Agreement",
            status="ANOMALY",
            detail=f"Gate={gate_upper} but omega={omega:.4f} < 0.60. "
            "Acceptance claim contradicts scored quality surface.",
        )
    if gate_upper in {"REJECT"} and omega > 0.85:
        return CheckResult(
            check_id="A3",
            label="Omega-Gate Agreement",
            status="WARN",
            detail=f"Gate={gate_upper} but omega={omega:.4f} > 0.85. "
            "Rejection stronger than quality surface warrants.",
        )
    return CheckResult(
        check_id="A3",
        label="Omega-Gate Agreement",
        status="CONSISTENT",
        detail=f"Gate={gate_upper or 'unset'} consistent with omega={omega:.4f}.",
    )


def _check_a4(traceability_ratio: float, round_num: int, not_traceable_count: int) -> CheckResult:
    if round_num == 1 and not_traceable_count >= 3 and traceability_ratio < 0.20:
        return CheckResult(
            check_id="A4",
            label="Round-1 Integrity",
            status="ANOMALY",
            detail=f"Round {round_num} with {not_traceable_count} NOT_TRACEABLE findings "
            f"({traceability_ratio:.2%} traceable). "
            "First-round submission lacks minimum evidence anchor.",
        )
    if not_traceable_count > 0:
        return CheckResult(
            check_id="A4",
            label="Round-1 Integrity",
            status="GAP",
            detail=f"{not_traceable_count} not-traceable finding(s) in round {round_num}. "
            "Each represents an open gap in the evidence anchor.",
        )
    return CheckResult(
        check_id="A4",
        label="Round-1 Integrity",
        status="PASS",
        detail=f"Round {round_num}: no NOT_TRACEABLE findings.",
    )
