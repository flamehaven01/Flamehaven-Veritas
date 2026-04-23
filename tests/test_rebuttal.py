"""Tests for veritas.rebuttal — RebuttalEngine + RevisionTracker (Phase 1, v3.3)."""

from __future__ import annotations

import pytest

from veritas.engine import SciExpCritiqueEngine
from veritas.rebuttal.rebuttal_engine import RebuttalEngine, RebuttalItem, RebuttalReport
from veritas.rebuttal.revision_tracker import RevisionGrade, RevisionResult, RevisionTracker
from veritas.types import (
    CritiqueReport,
    PrecheckResult,
    SciExpMode,
    StepFinding,
    StepResult,
    TraceabilityClass,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(code: str, description: str, traceability=TraceabilityClass.NOT_TRACEABLE):
    return StepFinding(
        code=code,
        description=description,
        traceability=traceability,
    )


def _make_step(step_id: str, findings=None, prose="Step prose.", not_applicable=False):
    return StepResult(
        step_id=step_id,
        weight=1.0,
        prose=prose,
        findings=findings or [],
        not_applicable=not_applicable,
    )


def _make_report(steps=None, omega=0.5, priority_fix="Fix claim.", round_number=1):
    return CritiqueReport(
        precheck=PrecheckResult(SciExpMode.FULL, []),
        steps=steps or [],
        omega_score=omega,
        priority_fix=priority_fix,
        round_number=round_number,
    )


CLINICAL_TEXT = """
Abstract
We investigate high-dose vitamin D supplementation for fracture reduction.
Methods
RCT n=340, power 80%, alpha=0.05. Participants received 4000 IU/day.
Results
Fracture incidence 12% vs 21% (p=0.003), 95% CI 0.24-0.61, Cohen d=0.54.
Discussion
Significant reduction confirms hypothesis.
Conclusion
High-dose vitamin D reduces fractures by 43%.
""".strip()

MINIMAL_TEXT = "We ran some tests and the results were interesting."


# ---------------------------------------------------------------------------
# RebuttalItem unit tests
# ---------------------------------------------------------------------------


class TestRebuttalItem:
    def test_mark_addressed_returns_new_item(self):
        item = RebuttalItem(
            issue_id="R-1.1",
            category="CLAIM_INTEGRITY",
            severity="HIGH",
            reviewer_text="Missing central claim.",
            author_response_template="We revised...",
        )
        addressed = item.mark_addressed()
        assert addressed.addressed is True
        assert item.addressed is False  # original unchanged

    def test_as_dict_keys(self):
        item = RebuttalItem(
            issue_id="R-2.1",
            category="TRACEABILITY",
            severity="MEDIUM",
            reviewer_text="No artifact found.",
            author_response_template="We added artifact...",
        )
        d = item.as_dict()
        assert set(d.keys()) == {
            "issue_id",
            "category",
            "severity",
            "reviewer_text",
            "author_response_template",
            "addressed",
        }

    def test_as_dict_addressed_default_false(self):
        item = RebuttalItem(
            issue_id="R-1.1",
            category="CLAIM_INTEGRITY",
            severity="CRITICAL",
            reviewer_text="Claim absent.",
            author_response_template="We added...",
        )
        assert item.as_dict()["addressed"] is False


# ---------------------------------------------------------------------------
# RebuttalReport unit tests
# ---------------------------------------------------------------------------


class TestRebuttalReport:
    def test_empty_report_coverage_is_1(self):
        rr = RebuttalReport()
        assert rr.rebuttal_coverage == 1.0

    def test_coverage_all_unaddressed(self):
        items = [
            RebuttalItem("R-1.1", "C", "HIGH", "t", "t"),
            RebuttalItem("R-2.1", "C", "HIGH", "t", "t"),
        ]
        rr = RebuttalReport(items=items)
        assert rr.rebuttal_coverage == 0.0

    def test_coverage_half_addressed(self):
        items = [
            RebuttalItem("R-1.1", "C", "HIGH", "t", "t", addressed=True),
            RebuttalItem("R-2.1", "C", "HIGH", "t", "t", addressed=False),
        ]
        rr = RebuttalReport(items=items)
        assert rr.rebuttal_coverage == 0.5

    def test_critical_count(self):
        items = [
            RebuttalItem("R-1.1", "C", "CRITICAL", "t", "t"),
            RebuttalItem("R-1.2", "C", "HIGH", "t", "t"),
        ]
        rr = RebuttalReport(items=items)
        assert rr.critical_count == 1
        assert rr.high_count == 1

    def test_items_by_severity_filter(self):
        items = [
            RebuttalItem("R-1.1", "C", "CRITICAL", "t", "t"),
            RebuttalItem("R-1.2", "C", "MEDIUM", "t", "t"),
        ]
        rr = RebuttalReport(items=items)
        assert len(rr.items_by_severity("CRITICAL")) == 1
        assert len(rr.items_by_severity("MEDIUM")) == 1
        assert len(rr.items_by_severity("LOW")) == 0

    def test_as_dict_structure(self):
        rr = RebuttalReport(items=[], style="acm", generated_at="2026-01-01T00:00:00+00:00")
        d = rr.as_dict()
        assert d["style"] == "acm"
        assert d["total_issues"] == 0
        assert "rebuttal_coverage" in d
        assert "items" in d


# ---------------------------------------------------------------------------
# RebuttalEngine — from CritiqueReport findings
# ---------------------------------------------------------------------------


class TestRebuttalEngineFromFindings:
    @pytest.fixture()
    def engine(self):
        return RebuttalEngine()

    def test_generate_returns_rebuttal_report(self, engine):
        report = _make_report()
        result = engine.generate(report)
        assert isinstance(result, RebuttalReport)

    def test_finding_becomes_item(self, engine):
        finding = _make_finding("1.1", "Central claim is absent.")
        step = _make_step("1", findings=[finding])
        report = _make_report(steps=[step])
        result = engine.generate(report)
        assert len(result.items) >= 1

    def test_issue_id_format(self, engine):
        finding = _make_finding("1.1", "Claim integrity issue.")
        step = _make_step("1", findings=[finding])
        report = _make_report(steps=[step])
        result = engine.generate(report)
        assert result.items[0].issue_id.startswith("R-1.")

    def test_not_traceable_maps_high(self, engine):
        finding = _make_finding("1.1", "No artifact.", TraceabilityClass.NOT_TRACEABLE)
        step = _make_step("1", findings=[finding])
        report = _make_report(steps=[step])
        result = engine.generate(report)
        assert result.items[0].severity in ("CRITICAL", "HIGH")

    def test_partially_traceable_maps_medium(self, engine):
        finding = _make_finding("2.1", "Partial artifact.", TraceabilityClass.PARTIALLY_TRACEABLE)
        step = _make_step("2", findings=[finding])
        report = _make_report(steps=[step])
        result = engine.generate(report)
        assert result.items[0].severity == "MEDIUM"

    def test_traceable_maps_low(self, engine):
        finding = _make_finding("3.1", "Minor gap.", TraceabilityClass.TRACEABLE)
        step = _make_step("3", findings=[finding])
        report = _make_report(steps=[step])
        result = engine.generate(report)
        assert result.items[0].severity == "LOW"

    def test_step1_not_traceable_is_critical(self, engine):
        finding = _make_finding(
            "1.1", "Claim absent — not traceable.", TraceabilityClass.NOT_TRACEABLE
        )
        step = _make_step("1", findings=[finding])
        report = _make_report(steps=[step])
        result = engine.generate(report)
        assert result.items[0].severity == "CRITICAL"

    def test_stat_description_maps_statistical_category(self, engine):
        finding = _make_finding(
            "1.2", "Missing p-value and effect size.", TraceabilityClass.PARTIALLY_TRACEABLE
        )
        step = _make_step("1", findings=[finding])
        report = _make_report(steps=[step])
        result = engine.generate(report)
        assert result.items[0].category == "STATISTICAL"

    def test_scope_description_maps_scope_violation_category(self, engine):
        finding = _make_finding(
            "2.1", "Overclaiming: 'proves superiority'", TraceabilityClass.TRACEABLE
        )
        step = _make_step("2", findings=[finding])
        report = _make_report(steps=[step])
        result = engine.generate(report)
        assert result.items[0].category == "SCOPE_VIOLATION"

    def test_not_applicable_step_skipped(self, engine):
        step = _make_step("3", findings=[], not_applicable=True)
        report = _make_report(steps=[step])
        result = engine.generate(report)
        # No items from a not_applicable step (priority_fix fallback may add one)
        item_ids = [i.issue_id for i in result.items]
        assert "R-3.1" not in item_ids or all("R-3" not in i for i in item_ids)

    def test_author_response_template_non_empty(self, engine):
        finding = _make_finding("1.1", "Missing claim.", TraceabilityClass.NOT_TRACEABLE)
        step = _make_step("1", findings=[finding])
        report = _make_report(steps=[step])
        result = engine.generate(report)
        assert len(result.items[0].author_response_template) > 20

    def test_style_stored_in_report(self, engine):
        report = _make_report()
        result = engine.generate(report, style="nature")
        assert result.style == "nature"

    def test_generated_at_is_set(self, engine):
        report = _make_report()
        result = engine.generate(report)
        assert len(result.generated_at) > 10

    def test_fallback_to_prose_when_no_findings(self, engine):
        step = _make_step("4", findings=[], prose="Publication readiness issue with missing DOI.")
        report = _make_report(steps=[step], priority_fix="")
        result = engine.generate(report)
        assert any(item.issue_id.startswith("R-4") for item in result.items)

    def test_priority_fix_fallback_when_no_steps(self, engine):
        report = _make_report(steps=[], priority_fix="Critical: missing central claim artifact.")
        result = engine.generate(report)
        assert len(result.items) >= 1
        assert result.items[0].issue_id == "R-5.1"


# ---------------------------------------------------------------------------
# RebuttalEngine — from full engine integration
# ---------------------------------------------------------------------------


class TestRebuttalEngineIntegration:
    @pytest.fixture()
    def rb_engine(self):
        return RebuttalEngine()

    @pytest.fixture()
    def critique_engine(self):
        return SciExpCritiqueEngine()

    def test_clinical_paper_produces_items(self, rb_engine, critique_engine):
        report = critique_engine.critique(CLINICAL_TEXT)
        result = rb_engine.generate(report)
        assert isinstance(result, RebuttalReport)
        assert len(result.items) >= 1

    def test_all_items_have_valid_severity(self, rb_engine, critique_engine):
        report = critique_engine.critique(CLINICAL_TEXT)
        result = rb_engine.generate(report)
        valid = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        for item in result.items:
            assert item.severity in valid

    def test_all_items_have_non_empty_template(self, rb_engine, critique_engine):
        report = critique_engine.critique(CLINICAL_TEXT)
        result = rb_engine.generate(report)
        for item in result.items:
            assert len(item.author_response_template) > 15

    def test_coverage_initially_zero(self, rb_engine, critique_engine):
        report = critique_engine.critique(CLINICAL_TEXT)
        result = rb_engine.generate(report)
        assert result.rebuttal_coverage == 0.0

    def test_as_dict_items_list(self, rb_engine, critique_engine):
        report = critique_engine.critique(CLINICAL_TEXT)
        result = rb_engine.generate(report)
        d = result.as_dict()
        assert isinstance(d["items"], list)

    def test_ieee_style_default(self, rb_engine, critique_engine):
        report = critique_engine.critique(MINIMAL_TEXT)
        result = rb_engine.generate(report)
        assert result.style == "ieee"


# ---------------------------------------------------------------------------
# RevisionTracker unit tests
# ---------------------------------------------------------------------------


class TestRevisionTracker:
    @pytest.fixture()
    def tracker(self):
        return RevisionTracker()

    def test_returns_revision_result(self, tracker):
        v1 = _make_report()
        v2 = _make_report()
        result = tracker.compare(v1, v2)
        assert isinstance(result, RevisionResult)

    def test_delta_omega_positive(self, tracker):
        v1 = _make_report(omega=0.5)
        v2 = _make_report(omega=0.7)
        result = tracker.compare(v1, v2)
        assert abs(result.delta_omega - 0.2) < 1e-9

    def test_delta_omega_negative(self, tracker):
        v1 = _make_report(omega=0.8)
        v2 = _make_report(omega=0.6)
        result = tracker.compare(v1, v2)
        assert result.delta_omega < 0

    def test_delta_omega_zero(self, tracker):
        v1 = _make_report(omega=0.7)
        v2 = _make_report(omega=0.7)
        result = tracker.compare(v1, v2)
        assert result.delta_omega == pytest.approx(0.0)

    def test_addressed_codes_empty_when_same_findings(self, tracker):
        finding = _make_finding("1.1", "Missing claim.")
        step = _make_step("1", findings=[finding])
        v1 = _make_report(steps=[step])
        v2 = _make_report(steps=[step])  # same findings
        result = tracker.compare(v1, v2)
        assert len(result.addressed_codes) == 0
        assert "1.1" in result.remaining_codes

    def test_addressed_code_when_finding_removed(self, tracker):
        finding = _make_finding("1.1", "Missing claim.")
        step_with = _make_step("1", findings=[finding])
        step_without = _make_step("1", findings=[])
        v1 = _make_report(steps=[step_with])
        v2 = _make_report(steps=[step_without])
        result = tracker.compare(v1, v2)
        assert "1.1" in result.addressed_codes

    def test_rcs_all_addressed(self, tracker):
        finding = _make_finding("1.1", "Issue.")
        step = _make_step("1", findings=[finding])
        v1 = _make_report(steps=[step])
        v2 = _make_report(steps=[])  # all findings gone
        result = tracker.compare(v1, v2)
        assert result.rcs == pytest.approx(1.0)

    def test_rcs_none_addressed(self, tracker):
        finding = _make_finding("1.1", "Issue.")
        step = _make_step("1", findings=[finding])
        v1 = _make_report(steps=[step])
        v2 = _make_report(steps=[step])  # same
        result = tracker.compare(v1, v2)
        assert result.rcs == pytest.approx(0.0)

    def test_grade_complete(self, tracker):
        findings = [_make_finding(f"1.{i}", "Issue.") for i in range(5)]
        step_v1 = _make_step("1", findings=findings)
        v1 = _make_report(steps=[step_v1])
        v2 = _make_report(steps=[])  # all addressed
        result = tracker.compare(v1, v2)
        assert result.revision_grade == RevisionGrade.COMPLETE

    def test_grade_partial(self, tracker):
        findings = [_make_finding(f"1.{i}", "Issue.") for i in range(4)]
        step_v1 = _make_step("1", findings=findings)
        step_v2 = _make_step("1", findings=findings[:2])  # 2 of 4 remain
        v1 = _make_report(steps=[step_v1])
        v2 = _make_report(steps=[step_v2])
        result = tracker.compare(v1, v2)
        assert result.revision_grade == RevisionGrade.PARTIAL

    def test_grade_insufficient(self, tracker):
        findings = [_make_finding(f"1.{i}", "Issue.") for i in range(4)]
        step_v1 = _make_step("1", findings=findings)
        # only 1 addressed out of 4 → rcs=0.25
        step_v2 = _make_step("1", findings=findings[1:])
        v1 = _make_report(steps=[step_v1])
        v2 = _make_report(steps=[step_v2])
        result = tracker.compare(v1, v2)
        assert result.revision_grade == RevisionGrade.INSUFFICIENT

    def test_no_findings_omega_improved_is_partial(self, tracker):
        v1 = _make_report(steps=[], omega=0.5)
        v2 = _make_report(steps=[], omega=0.7)
        result = tracker.compare(v1, v2)
        assert result.revision_grade == RevisionGrade.PARTIAL

    def test_improved_flag_true_when_omega_and_rcs_improve(self, tracker):
        finding = _make_finding("1.1", "Issue.")
        step_v1 = _make_step("1", findings=[finding])
        v1 = _make_report(steps=[step_v1], omega=0.5)
        v2 = _make_report(steps=[], omega=0.7)
        result = tracker.compare(v1, v2)
        assert result.improved is True

    def test_improved_flag_false_when_omega_regresses(self, tracker):
        v1 = _make_report(omega=0.8)
        v2 = _make_report(omega=0.6)
        result = tracker.compare(v1, v2)
        assert result.improved is False

    def test_priority_overlap_same_text(self, tracker):
        v1 = _make_report(priority_fix="Fix the central claim methodology.")
        v2 = _make_report(priority_fix="Fix the central claim methodology.")
        result = tracker.compare(v1, v2)
        assert result.priority_overlap_ratio == pytest.approx(1.0)

    def test_priority_overlap_different_text(self, tracker):
        v1 = _make_report(priority_fix="Fix the central claim methodology.")
        v2 = _make_report(priority_fix="Add statistical power analysis.")
        result = tracker.compare(v1, v2)
        assert result.priority_overlap_ratio < 1.0

    def test_as_dict_keys(self, tracker):
        v1 = _make_report()
        v2 = _make_report()
        d = tracker.compare(v1, v2).as_dict()
        assert "delta_omega" in d
        assert "rcs" in d
        assert "revision_grade" in d
        assert "addressed_codes" in d
        assert "remaining_codes" in d
