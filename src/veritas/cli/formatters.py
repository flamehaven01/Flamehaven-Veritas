"""CLI formatter — converts CritiqueReport to terminal / stream output.

Provides:
  fmt_md(report)   -> str   markdown (default, token-efficient)
  fmt_term(report) -> str   ANSI-stripped plain text for terminal display
"""
from __future__ import annotations
import re

from ..types import CritiqueReport

_HR = "---"
_TRACEABILITY_BADGE = {
    "traceable":           "[+]",
    "partially traceable": "[~]",
    "not traceable":       "[-]",
}
_STEP_TITLES = {
    "1": "STEP 1 — Claim Integrity (w=0.40)",
    "2": "STEP 2 — Traceability (w=0.30)",
    "3": "STEP 3 — Series Continuity (w=0.20)",
    "4": "STEP 4 — Publication Readiness (w=0.10)",
    "5": "STEP 5 — Priority Fix",
}


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _hdr(report: CritiqueReport) -> list[str]:
    omega_str = (
        f"**Omega:** {report.omega_score:.4f}"
        + (f" → hybrid {report.hybrid_omega:.4f}" if report.hybrid_omega is not None else "")
    )
    return [
        "# VERITAS — AI Critique Experimental Report Analysis Framework — Report", "",
        f"**Round:** {report.round_number}  ", omega_str, "",
    ]


def _precheck_block(report: CritiqueReport) -> list[str]:
    return ["## PRECHECK", "", "```", report.precheck.render(), "```", ""]


def _blocked_body(report: CritiqueReport) -> list[str]:
    lines: list[str] = []
    if report.steps:
        lines += ["## STEP 0", "", report.steps[0].prose, ""]
    lines += [
        "> **BLOCKED** — critique halted. Provide required artifacts.", "",
        f"**Priority fix:** {report.priority_fix}",
    ]
    return lines


def _step0_block(report: CritiqueReport) -> list[str]:
    lines = ["## STEP 0 — Experiment Classification", ""]
    if report.experiment_class:
        cls_str = report.experiment_class.value
        if report.experiment_class_secondary:
            cls_str += f" + {report.experiment_class_secondary.value}"
        lines.append(f"**Class:** {cls_str}")
    if report.experiment_class_reason:
        lines += [f"**Reason:** {report.experiment_class_reason}", ""]
    return lines


def _paper_intel_block(report: CritiqueReport) -> list[str]:
    if not (report.methodology_class or report.hypothesis_text):
        return []
    lines = ["### Paper Intelligence", ""]
    if report.methodology_class:
        lines.append(f"- **Methodology:** {report.methodology_class.value}")
    if report.hypothesis_text:
        lines.append(f"- **Hypothesis:** {report.hypothesis_text}")
    lines.append("")
    return lines


def _irf_block(report: CritiqueReport) -> list[str]:
    if not report.irf_scores:
        return []
    sc = report.irf_scores
    pass_icon = ":white_check_mark:" if sc.passed else ":warning:"
    pass_label = "PASS" if sc.passed else "WARN"
    lines = [
        "### IRF-Calc 6D (LOGOS)", "",
        "| Dim | Score | Meaning |",
        "|-----|-------|---------|",
        f"| M   | {sc.M:.3f} | Methodic Doubt |",
        f"| A   | {sc.A:.3f} | Axiom / Hypothesis |",
        f"| D   | {sc.D:.3f} | Deduction |",
        f"| I   | {sc.I:.3f} | Induction |",
        f"| F   | {sc.F:.3f} | Falsification |",
        f"| P   | {sc.P:.3f} | Paradigm |",
        f"| **composite** | **{sc.composite:.3f}** | {pass_icon} {pass_label} |",
        f"| source | `{sc.source}` | |",
        "",
    ]
    if report.logos_omega is not None:
        lines.append(
            f"**LOGOS ω:** {report.logos_omega:.4f}  "
            f"**SCI-EXP ω:** {report.omega_score:.4f}  "
            f"**Hybrid ω:** {report.hybrid_omega:.4f}"
        )
        lines.append("")
    return lines


def _hsta_block(report: CritiqueReport) -> list[str]:
    if not report.hsta_scores:
        return []
    h = report.hsta_scores
    return [
        "### HSTA 4D",
        (f"N(Novelty)={h.N:.3f}  C(Consistency)={h.C:.3f}  "
         f"T(Temporality)={h.T:.3f}  R(Reproducibility)={h.R:.3f}  composite={h.composite:.3f}"),
        "",
    ]


def _steps_block(report: CritiqueReport) -> list[str]:
    lines: list[str] = []
    for sr in report.steps:
        if sr.step_id == "0":
            continue
        title = _STEP_TITLES.get(sr.step_id, f"STEP {sr.step_id}")
        lines += [f"## {title}", "", sr.prose, ""]
        for finding in sr.findings:
            badge = _TRACEABILITY_BADGE.get(finding.traceability.value, "[?]")
            lines.append(f"- **{finding.code}** {badge} {finding.description}")
            if finding.verbatim_quote:
                lines.append(f'  > "{finding.verbatim_quote}"')
        if sr.findings:
            lines.append("")
        if sr.vulnerable_claim:
            lines += [f"> *Vulnerable claim:* {sr.vulnerable_claim}", ""]
    return lines


def _events_block(report: CritiqueReport) -> list[str]:
    lines: list[str] = []
    if report.hold_events:
        lines += ["## HOLD Events", ""]
        for h in report.hold_events:
            flag = "" if h.cause_stated else " ⚠ CAUSE UNSTATED"
            lines.append(f"- `{h.event_id}` [{h.disposition.value}]{flag}: {h.characterization}")
        lines.append("")
    if report.evidence_conflicts:
        lines += ["## Evidence Conflicts", ""]
        for ec in report.evidence_conflicts:
            lines.append(
                f"- **{ec.rank.name}** conflict: "
                f"`{ec.artifact_a}` vs `{ec.artifact_b}` — {ec.description}"
            )
        lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Public formatters
# ---------------------------------------------------------------------------

def fmt_md(report: CritiqueReport) -> str:
    """Full markdown representation of CritiqueReport."""
    lines = _hdr(report) + _precheck_block(report)

    if report.is_blocked():
        return "\n".join(lines + _blocked_body(report))

    lines += (
        _step0_block(report)
        + _paper_intel_block(report)
        + _irf_block(report)
        + _hsta_block(report)
        + _steps_block(report)
        + _events_block(report)
    )
    lines += [
        _HR,
        f"**not traceable:** {report.not_traceable_count()}  "
        f"**partially traceable:** {report.partially_traceable_count()}",
    ]
    return "\n".join(lines)


def fmt_term(report: CritiqueReport) -> str:
    """Compact plain-text terminal output (no markdown syntax)."""
    md = fmt_md(report)
    text = re.sub(r"^#{1,3} ", "", md, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`{1,3}[^`]*`{1,3}", lambda m: m.group(0).strip("`"), text)
    text = re.sub(r"^\|.+\|$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
