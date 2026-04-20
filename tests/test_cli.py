"""Tests for the veritas CLI (Mode 2)."""
from __future__ import annotations

import json
import pathlib
import tempfile

import pytest
from click.testing import CliRunner

from veritas.cli.main import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
SAMPLE_TEXT = """
Experiment: Effect of temperature on enzyme activity.
Hypothesis: Higher temperature increases reaction rate up to 37C.
Materials: 10 mL enzyme solution (0.5 mg/mL), buffer pH 7.0, spectrophotometer.
Method: Samples heated to 25, 30, 37, 42, 50C. Absorbance measured at t=0, 5, 10 min.
Results: Activity peaked at 37C (OD=1.24). At 50C activity dropped to OD=0.31.
Data file: raw_absorbance_table_v1.csv.
Conclusion: Enzyme is thermolabile above 42C.
""".strip()


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "paper.txt"
    f.write_text(SAMPLE_TEXT, encoding="utf-8")
    return str(f)


# ---------------------------------------------------------------------------
# critique --text
# ---------------------------------------------------------------------------
class TestCritique:
    def test_critique_text_md_exit_zero(self, runner):
        result = runner.invoke(main, ["critique", "--text", SAMPLE_TEXT, "--quiet"])
        assert result.exit_code == 0, result.output

    def test_critique_text_md_contains_sections(self, runner):
        result = runner.invoke(main, ["critique", "--text", SAMPLE_TEXT, "--quiet"])
        output = result.output
        assert "PRECHECK" in output
        assert "Omega" in output

    def test_critique_file_md(self, runner, sample_file):
        result = runner.invoke(main, ["critique", sample_file, "--quiet"])
        assert result.exit_code == 0, result.output
        assert "PRECHECK" in result.output

    def test_critique_no_input_fails(self, runner):
        result = runner.invoke(main, ["critique"])
        assert result.exit_code != 0

    def test_critique_pdf_format_requires_out(self, runner):
        result = runner.invoke(main, ["critique", "--text", SAMPLE_TEXT, "--format", "pdf"])
        assert result.exit_code != 0
        assert "required" in result.output.lower() or "error" in result.output.lower()

    def test_critique_md_to_file(self, runner):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(pathlib.Path(tmp) / "report.md")
            result = runner.invoke(
                main, ["critique", "--text", SAMPLE_TEXT, "--quiet", "--out", out]
            )
            assert result.exit_code == 0, result.output
            content = pathlib.Path(out).read_text(encoding="utf-8")
            assert "PRECHECK" in content

    def test_critique_template_ku(self, runner):
        result = runner.invoke(
            main, ["critique", "--text", SAMPLE_TEXT, "--template", "ku", "--quiet"]
        )
        assert result.exit_code == 0, result.output

    def test_critique_round_flag(self, runner):
        result = runner.invoke(
            main, ["critique", "--text", SAMPLE_TEXT, "--round", "2", "--quiet"]
        )
        assert result.exit_code == 0, result.output
        assert "**Round:** 2" in result.output

    def test_critique_verbose_shows_header(self, runner):
        result = runner.invoke(main, ["critique", "--text", SAMPLE_TEXT])
        assert result.exit_code == 0
        assert "SCI-EXP" in result.output

    def test_md_output_contains_omega(self, runner):
        result = runner.invoke(main, ["critique", "--text", SAMPLE_TEXT, "--quiet"])
        assert "Omega" in result.output or "omega" in result.output

    def test_md_output_traceability_badge(self, runner):
        result = runner.invoke(main, ["critique", "--text", SAMPLE_TEXT, "--quiet"])
        # Should contain at least one traceability badge
        assert any(badge in result.output for badge in ["[+]", "[-]", "[~]"])

    def test_minimal_text_does_not_crash(self, runner):
        result = runner.invoke(
            main, ["critique", "--text", "Some experiment.", "--quiet"]
        )
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# precheck
# ---------------------------------------------------------------------------
class TestPrecheck:
    def test_precheck_text(self, runner):
        result = runner.invoke(main, ["precheck", "--text", SAMPLE_TEXT])
        assert result.exit_code == 0, result.output
        assert len(result.output.strip()) > 0

    def test_precheck_file(self, runner, sample_file):
        result = runner.invoke(main, ["precheck", sample_file])
        assert result.exit_code == 0, result.output

    def test_precheck_no_input(self, runner):
        result = runner.invoke(main, ["precheck"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------
class TestInfo:
    def test_info_exits_zero(self, runner):
        result = runner.invoke(main, ["info"])
        assert result.exit_code == 0, result.output

    def test_info_shows_version(self, runner):
        result = runner.invoke(main, ["info"])
        assert "VERITAS" in result.output

    def test_info_shows_mica_state(self, runner):
        result = runner.invoke(main, ["info"])
        assert "MICA" in result.output or "mica" in result.output.lower()


# ---------------------------------------------------------------------------
# playbook
# ---------------------------------------------------------------------------
class TestPlaybook:
    def test_playbook_exits_zero(self, runner):
        result = runner.invoke(main, ["playbook"])
        assert result.exit_code == 0, result.output

    def test_playbook_contains_mica_header(self, runner):
        result = runner.invoke(main, ["playbook"])
        assert "MICA" in result.output

    def test_playbook_contains_di_section(self, runner):
        result = runner.invoke(main, ["playbook"])
        assert "DI-001" in result.output or "Design Invariants" in result.output

    def test_playbook_contains_cli_examples(self, runner):
        result = runner.invoke(main, ["playbook"])
        assert "veritas critique" in result.output


# ---------------------------------------------------------------------------
# version flag
# ---------------------------------------------------------------------------
class TestVersion:
    def test_version_flag(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "2.2" in result.output
