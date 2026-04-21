"""Tests for veritas.spar_bridge — Layer A/B/C + subject mapper."""

from __future__ import annotations

import importlib.util

import pytest

from veritas.spar_bridge.layer_a import _check_a1, _check_a2, _check_a3, _check_a4, build_layer_a
from veritas.spar_bridge.layer_b import _check_b1, _check_b2, _check_b3, _check_b4, build_layer_b
from veritas.spar_bridge.layer_c import _check_c1, _check_c2, _check_c3, _check_c4, build_layer_c
from veritas.spar_bridge.runtime import get_review_runtime
from veritas.spar_bridge.subject_mapper import report_to_subject
from veritas.types import (
    CritiqueReport,
    ExperimentClass,
    PrecheckResult,
    SciExpMode,
    StepFinding,
    StepResult,
    TraceabilityClass,
)

_SPAR_AVAILABLE = importlib.util.find_spec("spar_framework") is not None


class TestLayerA:
    def test_a1_full(self):
        r = _check_a1("FULL")
        assert r.status == "CONSISTENT"

    def test_a1_blocked(self):
        r = _check_a1("BLOCKED")
        assert r.status == "ANOMALY"

    def test_a1_partial(self):
        r = _check_a1("PARTIAL")
        assert r.status == "WARN"

    def test_a2_anomaly_below_floor(self):
        r = _check_a2(0.10)
        assert r.status == "ANOMALY"

    def test_a2_warn_low(self):
        r = _check_a2(0.45)
        assert r.status == "WARN"

    def test_a2_consistent(self):
        r = _check_a2(0.75)
        assert r.status == "CONSISTENT"

    def test_a3_accept_low_omega(self):
        r = _check_a3(0.40, "ACCEPT")
        assert r.status == "ANOMALY"

    def test_a3_reject_high_omega(self):
        r = _check_a3(0.90, "REJECT")
        assert r.status == "WARN"

    def test_a3_consistent(self):
        r = _check_a3(0.75, "ACCEPT")
        assert r.status == "CONSISTENT"

    def test_a3_no_gate(self):
        r = _check_a3(0.75, "")
        assert r.status == "CONSISTENT"

    def test_a4_anomaly_round1_all_not_traceable(self):
        r = _check_a4(0.10, 1, 5)
        assert r.status == "ANOMALY"

    def test_a4_gap_some_not_traceable(self):
        r = _check_a4(0.50, 2, 2)
        assert r.status == "GAP"

    def test_a4_pass(self):
        r = _check_a4(1.0, 1, 0)
        assert r.status == "PASS"

    def test_build_layer_a_returns_four_checks(self):
        subject = {
            "precheck_mode": "FULL",
            "traceability_ratio": 0.80,
            "omega_score": 0.75,
            "round_number": 1,
            "not_traceable_count": 0,
        }
        checks = build_layer_a(subject=subject, source="sciexp", gate="ACCEPT", params={})
        assert len(checks) == 4
        assert all(c.check_id.startswith("A") for c in checks)


# ── Layer B ───────────────────────────────────────────────────────────────────


class TestLayerB:
    def test_b1_fail_pubready_low_omega(self):
        r = _check_b1(0.55, "This report is publication-ready and camera-ready for submission.")
        assert r.status == "FAIL"

    def test_b1_pass_high_omega(self):
        r = _check_b1(0.85, "Standard experimental report.")
        assert r.status == "PASS"

    def test_b1_approximation_mid_omega(self):
        r = _check_b1(0.65, "Results indicate moderate effect. Needs further validation.")
        assert r.status == "APPROXIMATION"

    def test_b2_fail_omega_much_higher_than_irf(self):
        r = _check_b2(0.90, 0.50)
        assert r.status == "FAIL"

    def test_b2_warn_mild_divergence(self):
        r = _check_b2(0.80, 0.55)
        assert r.status == "WARN"

    def test_b2_consistent(self):
        r = _check_b2(0.75, 0.72)
        assert r.status == "CONSISTENT"

    def test_b2_no_irf(self):
        r = _check_b2(0.75, None)
        assert r.status == "PASS"

    def test_b3_overclaiming_detected(self):
        r = _check_b3("This study conclusively proves the hypothesis without doubt.")
        assert r.status == "WARN"
        assert "conclusively" in str(r.detail).lower() or "proves" in str(r.detail).lower()

    def test_b3_clean_text(self):
        r = _check_b3("Results suggest a moderate effect size in the treatment group.")
        assert r.status == "PASS"

    def test_b3_empty_text(self):
        r = _check_b3("")
        assert r.status == "PASS"

    def test_b4_fail_partial_high_omega(self):
        r = _check_b4("PARTIAL", 0.85)
        assert r.status == "FAIL"

    def test_b4_warn_limited_mode(self):
        r = _check_b4("LIMITED", 0.60)
        assert r.status == "WARN"

    def test_b4_pass_full_mode(self):
        r = _check_b4("FULL", 0.75)
        assert r.status == "PASS"

    def test_build_layer_b_returns_four_checks(self):
        subject = {"omega_score": 0.75, "irf_composite": 0.78, "precheck_mode": "FULL"}
        checks = build_layer_b(
            subject=subject,
            source="sciexp",
            gate="ACCEPT",
            report_text="Standard report.",
            context=None,
        )
        assert len(checks) == 4
        assert all(c.check_id.startswith("B") for c in checks)


# ── Layer C ───────────────────────────────────────────────────────────────────


class TestLayerC:
    def test_c1_genuine(self):
        r = _check_c1(0.82, True)
        assert r.status == "GENUINE"

    def test_c1_approximation_mid(self):
        r = _check_c1(0.65, False)
        assert r.status == "APPROXIMATION"

    def test_c1_partial_low(self):
        r = _check_c1(0.40, False)
        assert r.status == "PARTIAL"

    def test_c1_no_irf(self):
        r = _check_c1(None, None)
        assert r.status == "APPROXIMATION"

    def test_c2_genuine_high_coverage(self):
        r = _check_c2(0.90)
        assert r.status == "GENUINE"

    def test_c2_approximation_mid(self):
        r = _check_c2(0.65)
        assert r.status == "APPROXIMATION"

    def test_c2_partial_low(self):
        r = _check_c2(0.30)
        assert r.status == "PARTIAL"

    def test_c2_no_data(self):
        r = _check_c2(None)
        assert r.status == "APPROXIMATION"

    def test_c3_genuine(self):
        r = _check_c3(0.75)
        assert r.status == "GENUINE"

    def test_c3_approximation(self):
        r = _check_c3(0.55)
        assert r.status == "APPROXIMATION"

    def test_c3_partial(self):
        r = _check_c3(0.20)
        assert r.status == "PARTIAL"

    def test_c3_no_data(self):
        r = _check_c3(None)
        assert r.status == "APPROXIMATION"

    def test_c4_genuine_rct(self):
        r = _check_c4("RCT")
        assert r.status == "GENUINE"

    def test_c4_approximation_observational(self):
        r = _check_c4("OBSERVATIONAL")
        assert r.status == "APPROXIMATION"

    def test_c4_research_only_unknown(self):
        r = _check_c4("UNKNOWN")
        assert r.status == "RESEARCH_ONLY"

    def test_c4_none(self):
        r = _check_c4(None)
        assert r.status == "RESEARCH_ONLY"

    def test_build_layer_c_returns_four_checks(self):
        subject = {
            "irf_composite": 0.80,
            "irf_passed": True,
            "repro_completeness": 0.75,
            "bibliography_quality": 0.70,
            "methodology_class": "RCT",
        }
        checks = build_layer_c(subject=subject, source="sciexp", gate="ACCEPT", params={})
        assert len(checks) == 4
        assert all(c.check_id.startswith("C") for c in checks)


# ── Subject mapper ────────────────────────────────────────────────────────────


def _make_report(omega: float = 0.75, mode: SciExpMode = SciExpMode.FULL) -> CritiqueReport:
    pc = PrecheckResult(mode=mode, missing_artifacts=[])
    step = StepResult(
        step_id="1",
        weight=0.4,
        prose="Test.",
        findings=[
            StepFinding(
                code="C1.1",
                description="d",
                traceability=TraceabilityClass.TRACEABLE,
            ),
            StepFinding(
                code="C1.2",
                description="d2",
                traceability=TraceabilityClass.NOT_TRACEABLE,
            ),
        ],
    )
    return CritiqueReport(
        precheck=pc,
        experiment_class=ExperimentClass.PARITY,
        steps=[step],
        priority_fix="Fix A.",
        omega_score=omega,
        round_number=1,
    )


class TestSubjectMapper:
    def test_basic_mapping(self):
        report = _make_report(omega=0.75)
        s = report_to_subject(report)
        assert s["omega_score"] == 0.75
        assert s["precheck_mode"] == "FULL"
        assert s["round_number"] == 1
        assert s["traceability_ratio"] == 0.5
        assert s["not_traceable_count"] == 1
        assert s["partially_traceable_count"] == 0

    def test_no_findings_defaults_to_full_traceability(self):
        pc = PrecheckResult(mode=SciExpMode.FULL, missing_artifacts=[])
        report = CritiqueReport(precheck=pc, omega_score=0.80, steps=[])
        s = report_to_subject(report)
        assert s["traceability_ratio"] == 1.0

    def test_repro_completeness_none_when_no_checklist(self):
        report = _make_report()
        s = report_to_subject(report)
        assert s["repro_completeness"] is None


# ── Runtime integration ────────────────────────────────────────────────────────


@pytest.mark.skipif(not _SPAR_AVAILABLE, reason="spar-framework not installed")
class TestRuntime:
    def test_runtime_builds(self):
        rt = get_review_runtime()
        assert rt.build_layer_a is not None
        assert rt.build_layer_b is not None
        assert rt.build_layer_c is not None

    def test_full_review_run(self):
        from spar_framework.engine import run_review  # type: ignore[import]

        rt = get_review_runtime()
        subject = {
            "omega_score": 0.75,
            "traceability_ratio": 0.80,
            "not_traceable_count": 1,
            "partially_traceable_count": 0,
            "precheck_mode": "FULL",
            "round_number": 1,
            "experiment_class": "PARITY",
            "irf_composite": 0.78,
            "irf_passed": True,
            "methodology_class": "RCT",
            "bibliography_quality": 0.72,
            "repro_completeness": 0.85,
        }
        result = run_review(
            runtime=rt,
            subject=subject,
            source="sciexp",
            gate="ACCEPT",
            report_text="Standard experimental report with method details.",
        )
        assert result.verdict in {"ACCEPT", "MINOR_REVISION", "MAJOR_REVISION", "REJECT"}
        assert 0 <= result.score <= 100
        d = result.to_dict()
        assert "layer_a" in d
        assert "layer_b" in d
        assert "layer_c" in d
