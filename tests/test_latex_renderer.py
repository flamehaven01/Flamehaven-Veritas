"""Tests for LaTeXRenderer and render_latex()."""

from __future__ import annotations

import pytest

from veritas.render.latex_renderer import LatexRenderer, _e, render_latex
from veritas.types import (
    BibliographyStats,
    CritiqueReport,
    HSTA4DScores,
    IRF6DScores,
    PrecheckResult,
    ReproducibilityChecklist,
    ReproducibilityItem,
    SciExpMode,
    StepFinding,
    StepResult,
    TraceabilityClass,
)


def _base_report(**kwargs) -> CritiqueReport:
    return CritiqueReport(
        precheck=PrecheckResult(mode=SciExpMode.FULL, missing_artifacts=[]),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# _e() escape helper
# ---------------------------------------------------------------------------
def test_escape_ampersand():
    assert _e("A & B") == r"A \& B"


def test_escape_percent():
    assert _e("50%") == r"50\%"


def test_escape_underscore():
    assert _e("a_b") == r"a\_b"


def test_escape_hash():
    assert _e("#tag") == r"\#tag"


# ---------------------------------------------------------------------------
# Basic render_latex()
# ---------------------------------------------------------------------------
def test_render_latex_returns_string():
    report = _base_report()
    out = render_latex(report, "bmj")
    assert isinstance(out, str)
    assert r"\documentclass" in out
    assert r"\begin{document}" in out
    assert r"\end{document}" in out


def test_render_latex_ku_template():
    report = _base_report()
    out = render_latex(report, "ku")
    assert r"\end{document}" in out


def test_render_latex_unknown_template_raises():
    with pytest.raises(ValueError, match="Unknown template"):
        render_latex(_base_report(), "nonexistent")


def test_render_latex_contains_cover():
    report = _base_report(omega_score=0.75)
    out = render_latex(report)
    assert r"VERITAS" in out
    assert "0.7500" in out


def test_render_latex_skips_cover_page_section():
    """'Cover Page' section should NOT appear as a \\section{} heading."""
    report = _base_report()
    out = render_latex(report, "bmj")
    assert r"\section{Cover Page}" not in out
    assert r"\section{Title Page}" not in out


# ---------------------------------------------------------------------------
# Findings block
# ---------------------------------------------------------------------------
def test_render_latex_with_findings():
    finding = StepFinding(
        code="F1",
        description="Missing baseline.",
        traceability=TraceabilityClass.NOT_TRACEABLE,
    )
    step = StepResult(step_id="1", weight=0.4, prose="Claim analysis.", findings=[finding])
    report = _base_report(steps=[step])
    out = render_latex(report)
    assert r"\item" in out
    assert r"\notTC{NOT TRACEABLE}" in out


def test_render_latex_partially_traceable_finding():
    finding = StepFinding(
        code="F2",
        description="Partial claim.",
        traceability=TraceabilityClass.PARTIALLY_TRACEABLE,
    )
    step = StepResult(step_id="1", weight=0.4, prose=".", findings=[finding])
    report = _base_report(steps=[step])
    out = render_latex(report)
    assert r"\partialTC{PARTIALLY TRACEABLE}" in out


# ---------------------------------------------------------------------------
# BibliographyStats block
# ---------------------------------------------------------------------------
def test_render_latex_with_bibliography_stats():
    stats = BibliographyStats(
        total_refs=20,
        recent_ratio=0.6,
        oldest_year=2010,
        newest_year=2024,
        formats_detected=["Harvard"],
        self_citation_detected=False,
    )
    report = _base_report(bibliography_stats=stats)
    out = render_latex(report)
    assert "Bibliography Analysis" in out
    assert "20" in out
    assert "Harvard" in out


def test_bibliography_stats_quality_score_with_self_cite():
    stats = BibliographyStats(
        total_refs=30,
        recent_ratio=0.8,
        self_citation_detected=True,
    )
    score = stats.quality_score
    assert 0.0 < score < 1.0  # penalised


def test_bibliography_stats_quality_score_zero():
    stats = BibliographyStats(total_refs=0)
    assert stats.quality_score == 0.0


# ---------------------------------------------------------------------------
# ReproducibilityChecklist block
# ---------------------------------------------------------------------------
def test_render_latex_with_reproducibility_checklist():
    checklist = ReproducibilityChecklist(
        items=[
            ReproducibilityItem("DATA", "Data available", satisfied=True, note="zenodo"),
            ReproducibilityItem("CODE", "Code available", satisfied=False),
            ReproducibilityItem("PREREG", "Preregistered", satisfied=None),
        ]
    )
    report = _base_report(reproducibility_checklist=checklist)
    out = render_latex(report)
    assert "Reproducibility Checklist" in out
    assert r"\traceable{Yes}" in out
    assert r"\notTC{No}" in out
    assert r"\textcolor{gray}{?}" in out


def test_reproducibility_checklist_score():
    cl = ReproducibilityChecklist(
        items=[
            ReproducibilityItem("A", "Crit1", satisfied=True),
            ReproducibilityItem("B", "Crit2", satisfied=False),
            ReproducibilityItem("C", "Crit3", satisfied=None),
        ]
    )
    assert cl.score == pytest.approx(0.5)


def test_reproducibility_checklist_summary():
    cl = ReproducibilityChecklist(
        items=[
            ReproducibilityItem("A", "Crit1", satisfied=True),
            ReproducibilityItem("B", "Crit2", satisfied=False),
            ReproducibilityItem("C", "Crit3", satisfied=None),
        ]
    )
    assert "1 satisfied" in cl.summary
    assert "1 not satisfied" in cl.summary
    assert "1 unknown" in cl.summary


# ---------------------------------------------------------------------------
# IRF + HSTA blocks
# ---------------------------------------------------------------------------
def test_render_latex_with_irf_scores():
    irf = IRF6DScores(
        M=0.8,
        A=0.7,
        D=0.85,
        I=0.75,
        F=0.9,
        P=0.8,
        composite=0.80,
        passed=True,
    )
    report = _base_report(irf_scores=irf)
    out = render_latex(report)
    assert "IRF-Calc 6D" in out
    assert r"\traceable{PASS}" in out


def test_render_latex_with_irf_warn():
    irf = IRF6DScores(
        M=0.5,
        A=0.5,
        D=0.5,
        I=0.5,
        F=0.5,
        P=0.5,
        composite=0.50,
        passed=False,
    )
    report = _base_report(irf_scores=irf)
    out = render_latex(report)
    assert r"\partialTC{WARN}" in out


def test_render_latex_with_hsta_scores():
    hsta = HSTA4DScores(N=0.8, C=0.7, T=0.9, R=0.85)
    report = _base_report(hsta_scores=hsta)
    out = render_latex(report)
    assert "HSTA 4D" in out
    assert "0.800" in out


# ---------------------------------------------------------------------------
# LatexRenderer class
# ---------------------------------------------------------------------------
def test_latex_renderer_write_file(tmp_path):
    report = _base_report()
    out = tmp_path / "report.tex"
    result = LatexRenderer().render(report, str(out), template="bmj")
    assert result == out
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert r"\documentclass" in content
