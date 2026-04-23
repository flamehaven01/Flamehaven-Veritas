"""tests/test_response_letter.py — Unit tests for ResponseLetterRenderer (v3.3).

Coverage targets:
  - All 3 styles (ieee, acm, nature)
  - Invalid style raises ValueError
  - Structural sections present in output
  - render_to_file() writes correct content
  - Severity grouping reflected in output
  - Edge: zero items in rebuttal report
"""

from __future__ import annotations

import os
import re

import pytest

from veritas.rebuttal.rebuttal_engine import (
    RebuttalEngine,
    RebuttalItem,
    RebuttalReport,
)
from veritas.render.response_letter import ResponseLetterRenderer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(
    issue_id: str = "R-1.1",
    severity: str = "HIGH",
    category: str = "METHODOLOGY",
    reviewer_text: str = "Sample reviewer concern.",
    template: str = "We have addressed this by ...",
) -> RebuttalItem:
    return RebuttalItem(
        issue_id=issue_id,
        reviewer_text=reviewer_text,
        author_response_template=template,
        severity=severity,
        category=category,
        addressed=False,
    )


def _make_report(items: list[RebuttalItem] | None = None, style: str = "ieee") -> RebuttalReport:
    if items is None:
        items = [
            _make_item("R-1.1", severity="CRITICAL", category="REPRODUCIBILITY"),
            _make_item("R-2.1", severity="HIGH", category="METHODOLOGY"),
            _make_item("R-3.1", severity="MEDIUM", category="STATISTICS"),
            _make_item("R-4.1", severity="LOW", category="CLARITY"),
        ]
    return RebuttalReport(items=items, style=style)


# ---------------------------------------------------------------------------
# Style rendering tests
# ---------------------------------------------------------------------------


class TestRenderStyles:
    def test_ieee_header_present(self):
        renderer = ResponseLetterRenderer()
        md = renderer.render(_make_report(), style="ieee")
        assert "IEEE" in md

    def test_ieee_title_present(self):
        renderer = ResponseLetterRenderer()
        md = renderer.render(_make_report(), style="ieee")
        assert "Author Response to Reviewer Comments" in md

    def test_acm_title_present(self):
        renderer = ResponseLetterRenderer()
        md = renderer.render(_make_report(), style="acm")
        assert "Response to Reviewer Comments" in md

    def test_acm_header_present(self):
        renderer = ResponseLetterRenderer()
        md = renderer.render(_make_report(), style="acm")
        assert "ACM" in md

    def test_nature_title_present(self):
        renderer = ResponseLetterRenderer()
        md = renderer.render(_make_report(), style="nature")
        assert "Point-by-Point" in md

    def test_nature_header_present(self):
        renderer = ResponseLetterRenderer()
        md = renderer.render(_make_report(), style="nature")
        assert "NATURE" in md

    def test_all_styles_start_with_heading(self):
        renderer = ResponseLetterRenderer()
        for style in ("ieee", "acm", "nature"):
            md = renderer.render(_make_report(), style=style)
            assert md.startswith("# "), f"Style {style} must start with H1"

    def test_all_styles_produce_markdown(self):
        renderer = ResponseLetterRenderer()
        for style in ("ieee", "acm", "nature"):
            md = renderer.render(_make_report(), style=style)
            assert len(md) > 200

    def test_invalid_style_raises_value_error(self):
        renderer = ResponseLetterRenderer()
        with pytest.raises(ValueError, match="Unknown style"):
            renderer.render(_make_report(), style="acs")

    def test_invalid_style_message_helpful(self):
        renderer = ResponseLetterRenderer()
        try:
            renderer.render(_make_report(), style="bad")
        except ValueError as exc:
            assert "bad" in str(exc).lower() or "unknown" in str(exc).lower()

    def test_outputs_are_unique_per_style(self):
        renderer = ResponseLetterRenderer()
        report = _make_report()
        outputs = {s: renderer.render(report, style=s) for s in ("ieee", "acm", "nature")}
        assert len(set(outputs.values())) == 3, "Each style must produce distinct output"


# ---------------------------------------------------------------------------
# Content structure tests
# ---------------------------------------------------------------------------


class TestRenderContent:
    def test_generated_date_present(self):
        renderer = ResponseLetterRenderer()
        md = renderer.render(_make_report(), style="ieee")
        assert re.search(r"\d{4}-\d{2}-\d{2}", md)

    def test_issue_ids_appear_in_output(self):
        renderer = ResponseLetterRenderer()
        items = [
            _make_item("R-1.1"),
            _make_item("R-2.1"),
        ]
        md = renderer.render(_make_report(items=items), style="ieee")
        assert "R-1.1" in md
        assert "R-2.1" in md

    def test_reviewer_text_appears(self):
        renderer = ResponseLetterRenderer()
        items = [_make_item(reviewer_text="The sample size is insufficient.")]
        md = renderer.render(_make_report(items=items), style="ieee")
        assert "sample size" in md.lower() or "insufficient" in md.lower()

    def test_response_template_appears(self):
        renderer = ResponseLetterRenderer()
        items = [_make_item(template="We expanded the dataset to N=40.")]
        md = renderer.render(_make_report(items=items), style="ieee")
        assert "expanded" in md.lower() or "N=40" in md

    def test_critical_items_in_output(self):
        renderer = ResponseLetterRenderer()
        items = [_make_item("R-1.1", severity="CRITICAL")]
        md = renderer.render(_make_report(items=items), style="ieee")
        assert "critical" in md.lower() or "R-1.1" in md

    def test_high_items_in_output(self):
        renderer = ResponseLetterRenderer()
        items = [_make_item("R-2.1", severity="HIGH")]
        md = renderer.render(_make_report(items=items), style="ieee")
        assert "R-2.1" in md

    def test_medium_items_in_output(self):
        renderer = ResponseLetterRenderer()
        items = [_make_item("R-3.1", severity="MEDIUM")]
        md = renderer.render(_make_report(items=items), style="ieee")
        assert "R-3.1" in md

    def test_low_items_in_output(self):
        renderer = ResponseLetterRenderer()
        items = [_make_item("R-4.1", severity="LOW")]
        md = renderer.render(_make_report(items=items), style="ieee")
        assert "R-4.1" in md

    def test_total_issue_count_in_output(self):
        renderer = ResponseLetterRenderer()
        report = _make_report()
        md = renderer.render(report, style="ieee")
        assert str(len(report.items)) in md

    def test_closing_section_present(self):
        renderer = ResponseLetterRenderer()
        md = renderer.render(_make_report(), style="ieee")
        # Should have a closing or "Sincerely" / "Regards" style line
        lower = md.lower()
        assert any(kw in lower for kw in ("sincerely", "regards", "respectfully", "authors"))

    def test_empty_items_list_renders(self):
        renderer = ResponseLetterRenderer()
        report = _make_report(items=[])
        md = renderer.render(report, style="ieee")
        assert md.startswith("# ")
        assert "0" in md  # 0 total issues

    def test_single_critical_item(self):
        renderer = ResponseLetterRenderer()
        items = [_make_item("R-1.1", severity="CRITICAL")]
        md = renderer.render(_make_report(items=items), style="nature")
        assert "Point-by-Point" in md
        assert "R-1.1" in md


# ---------------------------------------------------------------------------
# render_to_file tests
# ---------------------------------------------------------------------------


class TestRenderToFile:
    def test_creates_file(self, tmp_path):
        renderer = ResponseLetterRenderer()
        path = str(tmp_path / "letter.md")
        result = renderer.render_to_file(_make_report(), path, style="ieee")
        assert os.path.isfile(path)
        assert result == path

    def test_file_content_matches_render(self, tmp_path):
        renderer = ResponseLetterRenderer()
        report = _make_report()
        path = str(tmp_path / "letter.md")
        renderer.render_to_file(report, path, style="acm")
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        expected = renderer.render(report, style="acm")
        assert content == expected

    def test_creates_acm_file(self, tmp_path):
        renderer = ResponseLetterRenderer()
        path = str(tmp_path / "acm_letter.md")
        renderer.render_to_file(_make_report(), path, style="acm")
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        assert "ACM" in content

    def test_creates_nature_file(self, tmp_path):
        renderer = ResponseLetterRenderer()
        path = str(tmp_path / "nature_letter.md")
        renderer.render_to_file(_make_report(), path, style="nature")
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        assert "NATURE" in content

    def test_overwrites_existing_file(self, tmp_path):
        renderer = ResponseLetterRenderer()
        path = str(tmp_path / "letter.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("old content")
        renderer.render_to_file(_make_report(), path, style="ieee")
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        assert "old content" not in content
        assert "IEEE" in content

    def test_returns_path_string(self, tmp_path):
        renderer = ResponseLetterRenderer()
        path = str(tmp_path / "out.md")
        result = renderer.render_to_file(_make_report(), path, style="ieee")
        assert isinstance(result, str)
        assert result == path


# ---------------------------------------------------------------------------
# Integration with RebuttalEngine
# ---------------------------------------------------------------------------


class TestRenderFromEngine:
    def test_engine_report_renderable(self):
        from veritas.engine import SciExpCritiqueEngine
        engine = SciExpCritiqueEngine()
        report = engine.critique(
            "Abstract: Drug X effect studied. N=20. p=0.03. t-test applied. "
            "Methods: Standard cell protocol."
        )
        rb_engine = RebuttalEngine()
        rb_report = rb_engine.generate(report, style="ieee")
        renderer = ResponseLetterRenderer()
        md = renderer.render(rb_report, style="ieee")
        assert md.startswith("# ")

    def test_engine_report_nature_style(self):
        from veritas.engine import SciExpCritiqueEngine
        engine = SciExpCritiqueEngine()
        report = engine.critique(
            "Abstract: Drug X inhibition. N=20. Results: 45% inhibition. p=0.05."
        )
        rb_engine = RebuttalEngine()
        rb_report = rb_engine.generate(report, style="nature")
        renderer = ResponseLetterRenderer()
        md = renderer.render(rb_report, style="nature")
        assert "Point-by-Point" in md
