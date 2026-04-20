"""Markdown renderer — outputs CritiqueReport as structured .md file."""
from __future__ import annotations

from pathlib import Path

from ..templates.base import BaseTemplate

_TRACEABILITY_BADGE = {
    "traceable":           "[+]",
    "partially traceable": "[~]",
    "not traceable":       "[-]",
}
_PAT_TC = __import__("re").compile(r'^\[([^\]]+)\]\s+\[([^\]]+)\]\s+(.+)$')


def render_md(report, template_id: str = "bmj") -> str:
    """Return full Markdown string for the critique report."""
    tmpl = BaseTemplate.all_templates().get(template_id)
    if tmpl is None:
        raise ValueError(f"Unknown template: {template_id}")

    sections = tmpl.build(report)
    omega_str = (
        f"{report.omega_score:.4f}"
        + (f" → hybrid {report.hybrid_omega:.4f}" if report.hybrid_omega is not None else "")
    )

    lines: list[str] = [
        "# VERITAS — EXPERIMENTAL REPORT ANALYSIS v2.1",
        "",
        f"> **Template:** {tmpl.DISPLAY_NAME}  ",
        f"> **Round:** {report.round_number}  ",
        f"> **Omega:** {omega_str}",
        "",
        "---",
        "",
    ]

    for sec in sections:
        prefix = "#" * (sec.level + 1)
        lines += [f"{prefix} {sec.title}", "", sec.body.strip(), ""]
        if sec.findings:
            lines.append("**Findings:**")
            lines.append("")
            for f in sec.findings:
                lines.append(_format_finding_md(f))
            lines.append("")
        lines += ["---", ""]

    # IRF / HSTA score tables
    if report.irf_scores:
        lines += _irf_md(report.irf_scores)
    if report.hsta_scores:
        lines += _hsta_md(report.hsta_scores)

    # Bibliography / Reproducibility appendix tables
    if report.bibliography_stats:
        lines += _biblio_md(report.bibliography_stats)
    if report.reproducibility_checklist:
        lines += _repro_md(report.reproducibility_checklist)

    return "\n".join(lines)


def save_md(report, output_path: str | Path, template_id: str = "bmj") -> Path:
    """Render and write Markdown file. Returns the output path."""
    path = Path(output_path)
    path.write_text(render_md(report, template_id), encoding="utf-8")
    return path


def _format_finding_md(raw: str) -> str:
    """Format a finding string with traceability badge."""
    m = _PAT_TC.match(raw.strip())
    if not m:
        return f"- {raw}"
    code, tc, desc = m.group(1), m.group(2), m.group(3)
    badge = _TRACEABILITY_BADGE.get(tc.lower(), "[?]")
    return f"- **{code}** {badge} `{tc}` — {desc}"


def _irf_md(irf) -> list[str]:
    pass_icon = ":white_check_mark:" if irf.passed else ":warning:"
    return [
        "## IRF-Calc 6D Score (LOGOS)", "",
        "| DIM | SCORE | MEANING |",
        "|-----|------:|---------|",
        f"| M   | {irf.M:.3f} | Methodic Doubt |",
        f"| A   | {irf.A:.3f} | Axiom / Hypothesis |",
        f"| D   | {irf.D:.3f} | Deduction |",
        f"| I   | {irf.I:.3f} | Induction |",
        f"| F   | {irf.F:.3f} | Falsification |",
        f"| P   | {irf.P:.3f} | Paradigm |",
        f"| **COMPOSITE** | **{irf.composite:.3f}** | {pass_icon} {'PASS' if irf.passed else 'WARN'} |",
        "",
        "---", "",
    ]


def _hsta_md(hsta) -> list[str]:
    return [
        "## HSTA 4D Score (BioMedical-Paper-Harvester)", "",
        "| DIM | SCORE | MEANING |",
        "|-----|------:|---------|",
        f"| N   | {hsta.N:.3f} | Novelty |",
        f"| C   | {hsta.C:.3f} | Consistency |",
        f"| T   | {hsta.T:.3f} | Temporality |",
        f"| R   | {hsta.R:.3f} | Reproducibility |",
        f"| **COMPOSITE** | **{hsta.composite:.3f}** | Arithmetic mean |",
        "",
        "---", "",
    ]


def _biblio_md(b) -> list[str]:
    fmt = ", ".join(b.formats_detected) if b.formats_detected else "Unknown"
    yr  = f"{b.oldest_year}–{b.newest_year}" if b.oldest_year else "N/A"
    self_cite = "Yes" if b.self_citation_detected else "No"
    return [
        "## Bibliography Analysis", "",
        "| METRIC | VALUE |",
        "|--------|-------|",
        f"| Total references | {b.total_refs} |",
        f"| Formats detected | {fmt} |",
        f"| Year range | {yr} |",
        f"| Self-citation detected | {self_cite} |",
        f"| Quality score | {b.quality_score:.3f} |",
        "",
        "---", "",
    ]


def _repro_md(rc) -> list[str]:
    sat  = sum(1 for i in rc.items if i.satisfied is True)
    tot  = len(rc.items)
    lines: list[str] = [
        "## Reproducibility Checklist", "",
        f"**Score:** {rc.score:.3f}  ({sat}/{tot} criteria met)", "",
        "| CRITERION | STATUS | NOTE |",
        "|-----------|--------|------|",
    ]
    for item in rc.items:
        icon = "[+]" if item.satisfied else ("[-]" if item.satisfied is False else "[?]")
        note = (item.note or "").replace("|", "/")
        lines.append(f"| {item.criterion} | {icon} | {note} |")
    lines += ["", "---", ""]
    return lines
