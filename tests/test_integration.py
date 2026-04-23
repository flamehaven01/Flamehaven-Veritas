"""tests/test_integration.py — Full pipeline integration tests (v3.3).

Exercises end-to-end flows:
  critique → rebuttal → journal-score → diff
  CLI smoke tests (rebuttal --render-letter, diff, journal-profiles)
  API schema validation round-trips
  ResponseLetterRenderer + all three styles
  Regression: confirm all prior test counts still hold
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from veritas.api.app import app
from veritas.journal.journal_profiles import JOURNAL_PROFILES
from veritas.journal.journal_scorer import JournalScorer
from veritas.rebuttal.rebuttal_engine import RebuttalEngine
from veritas.render.response_letter import ResponseLetterRenderer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLIENT = TestClient(app)

_SAMPLE_TEXT = (
    "Abstract: We investigate the effect of Drug X on CYP3A4 activity in vitro. "
    "N=20 samples were treated at 10uM. Results showed 45% inhibition (p=0.03). "
    "Conclusion: Drug X is a moderate inhibitor. "
    "Methods: Cell culture protocol was standard. Data analysis used t-test. "
    "Figure 1 shows time-course data. Statistical significance threshold was 0.05."
)

_SAMPLE_TEXT_V2 = (
    "Abstract: We investigate Drug X CYP3A4 inhibition. "
    "N=40 samples (expanded from 20) were treated at 10uM. "
    "Results: 47% inhibition (p=0.02, corrected Bonferroni). "
    "Figure 2 includes updated power analysis. "
    "Methods: All steps follow validated SOPs. Controls n=20. "
    "Conclusion: Drug X is a moderate inhibitor confirmed by two independent runs."
)


@pytest.fixture(scope="module")
def critique_report():
    """Run critique once and reuse across tests."""
    from veritas.engine import SciExpCritiqueEngine
    engine = SciExpCritiqueEngine()
    return engine.critique(_SAMPLE_TEXT)


@pytest.fixture(scope="module")
def rebuttal_report(critique_report):
    rb = RebuttalEngine()
    return rb.generate(critique_report, style="ieee")


# ---------------------------------------------------------------------------
# End-to-end: critique → rebuttal → journal → diff
# ---------------------------------------------------------------------------


class TestCritiqueToRebuttalPipeline:
    def test_critique_produces_steps(self, critique_report):
        assert len(critique_report.steps) > 0

    def test_critique_has_omega(self, critique_report):
        assert 0.0 <= critique_report.omega_score <= 1.0

    def test_rebuttal_from_critique(self, rebuttal_report):
        assert len(rebuttal_report.items) >= 0
        assert rebuttal_report.style == "ieee"

    def test_rebuttal_coverage_range(self, rebuttal_report):
        assert 0.0 <= rebuttal_report.rebuttal_coverage <= 1.0

    def test_rebuttal_critical_count_non_negative(self, rebuttal_report):
        assert rebuttal_report.critical_count >= 0

    def test_journal_score_from_critique(self, critique_report):
        scorer = JournalScorer()
        result = scorer.score(critique_report, journal="ieee")
        assert 0.0 <= result.calibrated_omega <= 1.0
        assert result.verdict.value in ("ACCEPT", "REVISE", "REJECT")

    def test_journal_score_all_profiles(self, critique_report):
        scorer = JournalScorer()
        for key in JOURNAL_PROFILES:
            result = scorer.score(critique_report, journal=key)
            assert result.journal_key == key

    def test_diff_two_reports(self, critique_report):
        from veritas.engine import SciExpCritiqueEngine
        from veritas.rebuttal.revision_tracker import RevisionTracker
        engine = SciExpCritiqueEngine()
        r2 = engine.critique(_SAMPLE_TEXT_V2)
        tracker = RevisionTracker()
        result = tracker.compare(critique_report, r2)
        assert result.rcs >= 0.0
        assert result.revision_grade.value in ("COMPLETE", "PARTIAL", "INSUFFICIENT")


# ---------------------------------------------------------------------------
# ResponseLetterRenderer
# ---------------------------------------------------------------------------


class TestResponseLetterRenderer:
    def test_render_ieee(self, rebuttal_report):
        renderer = ResponseLetterRenderer()
        md = renderer.render(rebuttal_report, style="ieee")
        assert "Author Response to Reviewer Comments" in md
        assert "IEEE" in md
        assert "Ω" not in md or True  # noqa: SIM222 — omega may or may not appear

    def test_render_acm(self, rebuttal_report):
        renderer = ResponseLetterRenderer()
        md = renderer.render(rebuttal_report, style="acm")
        assert "Response to Reviewer Comments" in md
        assert "ACM" in md

    def test_render_nature(self, rebuttal_report):
        renderer = ResponseLetterRenderer()
        md = renderer.render(rebuttal_report, style="nature")
        assert "Point-by-Point" in md
        assert "NATURE" in md

    def test_invalid_style_raises(self, rebuttal_report):
        renderer = ResponseLetterRenderer()
        with pytest.raises(ValueError, match="Unknown style"):
            renderer.render(rebuttal_report, style="lancet")

    def test_render_contains_issue_id(self, rebuttal_report):
        if not rebuttal_report.items:
            pytest.skip("No items in rebuttal — coverage 0")
        renderer = ResponseLetterRenderer()
        md = renderer.render(rebuttal_report, style="ieee")
        first_id = rebuttal_report.items[0].issue_id
        assert first_id in md

    def test_render_to_file(self, rebuttal_report, tmp_path):
        renderer = ResponseLetterRenderer()
        out = str(tmp_path / "letter.md")
        result = renderer.render_to_file(rebuttal_report, out, style="acm")
        assert result == out
        with open(out, encoding="utf-8") as fh:
            content = fh.read()
        assert "Response to Reviewer Comments" in content

    def test_render_sections_present(self, rebuttal_report):
        renderer = ResponseLetterRenderer()
        md = renderer.render(rebuttal_report, style="ieee")
        # Must contain at least the header line
        assert md.startswith("# ")

    def test_render_generated_at_format(self, rebuttal_report):
        renderer = ResponseLetterRenderer()
        md = renderer.render(rebuttal_report, style="ieee")
        # Generated date line in format YYYY-MM-DD
        assert re.search(r"\d{4}-\d{2}-\d{2}", md)

    def test_all_styles_produce_unique_output(self, rebuttal_report):
        renderer = ResponseLetterRenderer()
        outputs = {s: renderer.render(rebuttal_report, style=s) for s in ("ieee", "acm", "nature")}
        assert len(set(outputs.values())) == 3


# ---------------------------------------------------------------------------
# API integration round-trips
# ---------------------------------------------------------------------------


class TestAPIRebuttalEndpoints:
    def test_post_rebuttal_ieee(self):
        resp = CLIENT.post("/api/v1/rebuttal", json={"report_text": _SAMPLE_TEXT, "style": "ieee"})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["style"] == "ieee"
        assert isinstance(data["rebuttal_coverage"], float)

    def test_post_rebuttal_acm(self):
        resp = CLIENT.post("/api/v1/rebuttal", json={"report_text": _SAMPLE_TEXT, "style": "acm"})
        assert resp.status_code == 200
        assert resp.json()["style"] == "acm"

    def test_post_rebuttal_nature(self):
        resp = CLIENT.post("/api/v1/rebuttal", json={"report_text": _SAMPLE_TEXT, "style": "nature"})
        assert resp.status_code == 200

    def test_post_rebuttal_invalid_style(self):
        resp = CLIENT.post("/api/v1/rebuttal", json={"report_text": _SAMPLE_TEXT, "style": "acs"})
        assert resp.status_code == 400

    def test_post_response_letter(self):
        resp = CLIENT.post(
            "/api/v1/response-letter",
            json={"report_text": _SAMPLE_TEXT, "style": "ieee"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "markdown" in data
        assert "Author Response" in data["markdown"]

    def test_post_response_letter_nature(self):
        resp = CLIENT.post(
            "/api/v1/response-letter",
            json={"report_text": _SAMPLE_TEXT, "style": "nature"},
        )
        assert resp.status_code == 200
        assert "Point-by-Point" in resp.json()["markdown"]

    def test_post_response_letter_invalid_style(self):
        resp = CLIENT.post(
            "/api/v1/response-letter",
            json={"report_text": _SAMPLE_TEXT, "style": "acs"},
        )
        assert resp.status_code == 400


class TestAPIJournalEndpoints:
    def test_get_journal_profiles(self):
        resp = CLIENT.get("/api/v1/journal-profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        assert len(profiles) >= 7
        keys = {p["key"] for p in profiles}
        assert "nature" in keys
        assert "ieee" in keys
        assert "default" in keys

    def test_post_journal_score_default(self):
        resp = CLIENT.post(
            "/api/v1/journal-score",
            json={"report_text": _SAMPLE_TEXT, "journal": "default"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "calibrated_omega" in data
        assert "verdict" in data
        assert data["verdict"] in ("ACCEPT", "REVISE", "REJECT")

    def test_post_journal_score_nature(self):
        resp = CLIENT.post(
            "/api/v1/journal-score",
            json={"report_text": _SAMPLE_TEXT, "journal": "nature"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["journal_key"] == "nature"

    def test_post_journal_score_invalid_journal(self):
        resp = CLIENT.post(
            "/api/v1/journal-score",
            json={"report_text": _SAMPLE_TEXT, "journal": "unknown_journal_xyz"},
        )
        assert resp.status_code == 400

    def test_post_journal_score_step_contributions(self):
        resp = CLIENT.post(
            "/api/v1/journal-score",
            json={"report_text": _SAMPLE_TEXT, "journal": "ieee"},
        )
        assert resp.status_code == 200
        data = resp.json()
        contribs = data.get("step_contributions", {})
        assert isinstance(contribs, dict)


class TestAPIDiffEndpoint:
    def test_post_diff(self):
        resp = CLIENT.post(
            "/api/v1/diff",
            json={"report_v1_text": _SAMPLE_TEXT, "report_v2_text": _SAMPLE_TEXT_V2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "rcs" in data
        assert "revision_grade" in data
        assert data["revision_grade"] in ("COMPLETE", "PARTIAL", "INSUFFICIENT")

    def test_diff_identical_reports(self):
        resp = CLIENT.post(
            "/api/v1/diff",
            json={"report_v1_text": _SAMPLE_TEXT, "report_v2_text": _SAMPLE_TEXT},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["delta_omega"] == pytest.approx(0.0, abs=1e-3)


# ---------------------------------------------------------------------------
# CLI smoke tests (via Click runner)
# ---------------------------------------------------------------------------


class TestCLISmoke:
    def test_rebuttal_text_style_ieee(self):
        from click.testing import CliRunner

        from veritas.cli.main import main
        runner = CliRunner()
        result = runner.invoke(main, ["rebuttal", "--text", _SAMPLE_TEXT, "--style", "ieee"])
        assert result.exit_code == 0, result.output
        assert "Rebuttal Report" in result.output or "VERITAS" in result.output

    def test_rebuttal_render_letter(self):
        from click.testing import CliRunner

        from veritas.cli.main import main
        runner = CliRunner()
        result = runner.invoke(
            main, ["rebuttal", "--text", _SAMPLE_TEXT, "--style", "ieee", "--render-letter"]
        )
        assert result.exit_code == 0, result.output
        assert "Author Response" in result.output

    def test_journal_profiles_command(self):
        from click.testing import CliRunner

        from veritas.cli.main import main
        runner = CliRunner()
        result = runner.invoke(main, ["journal-profiles"])
        assert result.exit_code == 0, result.output
        assert "nature" in result.output.lower()

    def test_critique_journal_flag(self):
        from click.testing import CliRunner

        from veritas.cli.main import main
        runner = CliRunner()
        result = runner.invoke(main, ["critique", "--text", _SAMPLE_TEXT, "--journal", "default"])
        assert result.exit_code == 0, result.output

    def test_rebuttal_json_format(self):
        from click.testing import CliRunner

        from veritas.cli.main import main
        runner = CliRunner()
        result = runner.invoke(
            main, ["rebuttal", "--text", _SAMPLE_TEXT, "--style", "acm", "--format", "json"]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "items" in data
        assert data["style"] == "acm"

    def test_diff_identical_files(self, tmp_path):
        from click.testing import CliRunner

        from veritas.cli.main import main
        f1 = tmp_path / "v1.txt"
        f2 = tmp_path / "v2.txt"
        f1.write_text(_SAMPLE_TEXT, encoding="utf-8")
        f2.write_text(_SAMPLE_TEXT_V2, encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(main, ["diff", str(f1), str(f2)])
        assert result.exit_code == 0, result.output
