"""response_letter.py — Formal academic response letter renderer (v3.3).

Generates a point-by-point author response letter from a RebuttalReport,
following IEEE, ACM, or Nature formatting conventions.

Output: Markdown string, suitable for .md / .docx / .pdf conversion.
Zero external dependencies — pure Python string composition.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..rebuttal.rebuttal_engine import RebuttalItem, RebuttalReport

# ---------------------------------------------------------------------------
# Style configurations (pure data — no logic)
# ---------------------------------------------------------------------------

_STYLE_CONFIG = {
    "ieee": {
        "title": "Author Response to Reviewer Comments",
        "preamble": (
            "Dear Editor and Reviewers,\n\n"
            "We thank the reviewers for their thorough evaluation of our manuscript. "
            "We have carefully considered all comments and provide a detailed "
            "point-by-point response below. All changes are marked in the revised "
            "manuscript using track changes / highlighted text.\n"
        ),
        "reviewer_prefix": "**Reviewer Comment {n}:**",
        "response_prefix": "**Author Response:**",
        "closing": (
            "We believe the revised manuscript fully addresses the reviewer concerns "
            "and meets IEEE publication standards. "
            "We appreciate the editors' consideration.\n\n"
            "Sincerely,\nThe Authors"
        ),
        "severity_note": {"CRITICAL": "(CRITICAL — addressed first)", "HIGH": "(HIGH priority)"},
    },
    "acm": {
        "title": "Response to Reviewer Comments",
        "preamble": (
            "Dear Associate Editor and Reviewers,\n\n"
            "We are grateful for the reviewers' careful reading and constructive feedback. "
            "The following provides a complete point-by-point response. "
            "Corresponding changes in the manuscript are referenced by section and page number.\n"
        ),
        "reviewer_prefix": "**Reviewer Concern {n} [{category}]:**",
        "response_prefix": "**Response:**",
        "closing": (
            "We hope the above responses and revisions have satisfactorily addressed "
            "all reviewer concerns. We look forward to the editorial decision.\n\n"
            "With appreciation,\nThe Authors"
        ),
        "severity_note": {"CRITICAL": "⚠️ Critical", "HIGH": "!  High priority"},
    },
    "nature": {
        "title": "Point-by-Point Response to Referees",
        "preamble": (
            "We thank the referees for their detailed and constructive evaluations. "
            "Below we address each point raised. "
            "We have substantially revised the manuscript in light of these comments, "
            "and we believe the revisions strengthen the work considerably.\n"
        ),
        "reviewer_prefix": "*Referee Comment {n}:*",
        "response_prefix": "*Our Response:*",
        "closing": (
            "We trust these responses and revisions will be satisfactory "
            "and look forward to the referees' further evaluation.\n\n"
            "Yours sincerely,\nThe Authors"
        ),
        "severity_note": {"CRITICAL": "[Major]", "HIGH": "[Significant]"},
    },
}

_SECTION_HEADERS = {
    "CRITICAL": "### Critical Issues",
    "HIGH": "### High-Priority Issues",
    "MEDIUM": "### Medium-Priority Issues",
    "LOW": "### Minor Issues",
}

_SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


class ResponseLetterRenderer:
    """Renders a RebuttalReport as a formal academic response letter.

    Usage::
        renderer = ResponseLetterRenderer()
        md = renderer.render(rebuttal_report, style="ieee")
        path = renderer.render_to_file(rebuttal_report, "response.md", style="nature")
    """

    def render(self, report: RebuttalReport, style: str = "ieee") -> str:
        """Return a full Markdown response letter string.

        Args:
            report: RebuttalReport from RebuttalEngine.generate().
            style:  Citation/format style — 'ieee', 'acm', or 'nature'.

        Returns:
            Markdown string of the complete response letter.

        Raises:
            ValueError: If style is not one of ieee, acm, nature.
        """
        cfg = _STYLE_CONFIG.get(style.lower())
        if cfg is None:
            valid = ", ".join(sorted(_STYLE_CONFIG))
            raise ValueError(f"Unknown style '{style}'. Valid: {valid}")

        sections = self._build_sections(report, cfg)
        return self._assemble(cfg, sections, report, style.upper())

    def render_to_file(self, report: RebuttalReport, path: str, style: str = "ieee") -> str:
        """Render and write to file. Returns path."""
        content = self.render(report, style=style)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    # ── private ──────────────────────────────────────────────────────────────

    def _build_sections(self, report: RebuttalReport, cfg: dict) -> list[str]:
        """Group items by severity and emit point-by-point blocks."""
        sections: list[str] = []
        by_severity: dict[str, list[RebuttalItem]] = {s: [] for s in _SEVERITY_ORDER}

        for item in report.items:
            bucket = by_severity.get(item.severity, by_severity["LOW"])
            bucket.append(item)

        counter = 1
        for severity in _SEVERITY_ORDER:
            items = by_severity[severity]
            if not items:
                continue
            sections.append(_SECTION_HEADERS[severity])
            sections.append("")
            for item in items:
                block = self._format_item(item, counter, cfg)
                sections.extend(block)
                sections.append("")
                counter += 1

        return sections

    @staticmethod
    def _format_item(item: RebuttalItem, n: int, cfg: dict) -> list[str]:
        """Format one RebuttalItem as a reviewer–response exchange."""
        severity_tag = cfg["severity_note"].get(item.severity, "")
        reviewer_line = cfg["reviewer_prefix"].format(n=n, category=item.category) + (
            f" {severity_tag}" if severity_tag else ""
        )
        response_line = cfg["response_prefix"].format(n=n, category=item.category)

        return [
            "---",
            f"**Issue ID:** `{item.issue_id}` | **Category:** {item.category}",
            "",
            reviewer_line,
            f"> {item.reviewer_text}",
            "",
            response_line,
            item.author_response_template,
            "",
            f"**Status:** {'✅ Addressed' if item.addressed else '🔲 Pending'}",
        ]

    @staticmethod
    def _assemble(
        cfg: dict, sections: list[str], report: RebuttalReport, style_label: str = ""
    ) -> str:
        """Combine header, preamble, sections, and closing into final string."""
        ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        label = style_label or report.style.upper()
        header = [
            f"# {cfg['title']}",
            "",
            f"**Style:** {label}  ",
            f"**Generated:** {ts}  ",
            f"**Total Issues:** {len(report.items)} "
            f"(Critical: {report.critical_count}, High: {report.high_count})  ",
            f"**Rebuttal Coverage:** {report.rebuttal_coverage:.0%}",
            "",
            "---",
            "",
            cfg["preamble"],
            "",
        ]
        footer = [
            "",
            "---",
            "",
            cfg["closing"],
            "",
            f"*Generated by VERITAS v3.3 Rebuttal Engine · {ts}*",
        ]
        return "\n".join(header + sections + footer)
