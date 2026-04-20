"""BMJ Scientific Editing Report Template.

Maps CritiqueReport fields to the BMJ Medical Scientific Editing Report
section structure (8-section layout).
"""
from __future__ import annotations

from .base import BaseTemplate, TemplateSection


class BMJTemplate(BaseTemplate):
    """BMJ Medical Scientific Editing Report (8-section)."""

    TEMPLATE_ID  = "bmj"
    DISPLAY_NAME = "BMJ Scientific Editing Report"

    SECTIONS = [
        "Cover Page",
        "Executive Summary",
        "Experiment Classification",
        "Claim Integrity Assessment",
        "Traceability & Artifact Audit",
        "Series Continuity",
        "Publication Readiness",
        "Priority Recommendations",
    ]

    def build(self, report) -> list[TemplateSection]:

        sections: list[TemplateSection] = []

        # 1 — Cover Page
        sections.append(TemplateSection(
            title="Cover Page",
            level=1,
            body="\n".join([
                "**VERITAS REPORT — BMJ Format**",
                "",
                f"Round          : {report.round_number}",
                f"PRECHECK MODE  : {report.precheck.mode.value}",
                f"Missing Artifacts: {', '.join(report.precheck.missing_artifacts) or 'none'}",
                f"Critique Omega : {report.omega_score:.4f}",
                f"Not-Traceable  : {report.not_traceable_count()} finding(s)",
                f"Partially      : {report.partially_traceable_count()} finding(s)",
            ]),
        ))

        # 2 — Executive Summary
        report.step("5")
        sections.append(TemplateSection(
            title="Executive Summary",
            level=1,
            body=report.priority_fix + (
                f"\n\n**Next Liability:** {report.next_liability}" if report.next_liability else ""
            ),
        ))

        # 3 — Experiment Classification
        cls_label = report.experiment_class.value if report.experiment_class else "UNKNOWN"
        secondary = f" / SECONDARY={report.experiment_class_secondary.value}" \
            if report.experiment_class_secondary else ""
        sections.append(TemplateSection(
            title="Experiment Classification",
            level=1,
            body=f"**CLASS:** {cls_label}{secondary}\n\n{report.experiment_class_reason}",
        ))

        # 4 — Claim Integrity (STEP 1)
        step1 = report.step("1")
        sections.append(TemplateSection(
            title="Claim Integrity Assessment",
            level=1,
            body=_step_body(step1),
            findings=_format_findings(step1),
        ))

        # 5 — Traceability Audit (STEP 2)
        step2 = report.step("2")
        sections.append(TemplateSection(
            title="Traceability & Artifact Audit",
            level=1,
            body=_step_body(step2),
            findings=_format_findings(step2),
        ))

        # 6 — Series Continuity (STEP 3)
        step3 = report.step("3")
        sections.append(TemplateSection(
            title="Series Continuity",
            level=1,
            body=_step_body(step3),
            findings=_format_findings(step3),
        ))

        # 7 — Publication Readiness (STEP 4)
        step4 = report.step("4")
        sections.append(TemplateSection(
            title="Publication Readiness",
            level=1,
            body=_step_body(step4),
            findings=_format_findings(step4),
        ))

        # 8 — Priority Recommendations
        recs = [f"1. {report.priority_fix}"]
        if report.next_liability:
            recs.append(f"2. (Next liability) {report.next_liability}")
        if report.evidence_conflicts:
            recs.append(f"3. Resolve {len(report.evidence_conflicts)} same-rank evidence conflict(s).")
        sections.append(TemplateSection(
            title="Priority Recommendations",
            level=1,
            body="\n\n".join(recs),
        ))

        # 9 — Bibliography Analysis (optional)
        if report.bibliography_stats:
            s = report.bibliography_stats
            fmt = ", ".join(s.formats_detected) or "Unknown"
            yr  = f"{s.oldest_year}–{s.newest_year}" if s.oldest_year else "N/A"
            sections.append(TemplateSection(
                title="Bibliography Analysis",
                level=1,
                body="\n".join([
                    f"Total references   : {s.total_refs}",
                    f"Recent ratio (≤5yr): {s.recent_ratio:.1%}",
                    f"Year range         : {yr}",
                    f"Citation format    : {fmt}",
                    f"Self-cite detected : {'Yes' if s.self_citation_detected else 'No'}",
                    f"Quality score      : {s.quality_score:.4f}",
                ]),
            ))

        # 10 — Reproducibility Checklist (optional)
        if report.reproducibility_checklist:
            rc = report.reproducibility_checklist
            sections.append(TemplateSection(
                title="Reproducibility Checklist",
                level=1,
                body=f"Score: {rc.score:.4f} | {rc.summary}",
                findings=[
                    f"[{item.code}] [{'SATISFIED' if item.satisfied else 'NOT MET' if item.satisfied is False else 'UNKNOWN'}] "
                    f"{item.criterion}" + (f" — {item.note}" if item.note else "")
                    for item in rc.items
                ],
            ))

        return sections


def _step_body(step) -> str:
    return step.prose if step else "_Step not executed._"


def _format_findings(step) -> list[str]:
    if not step:
        return []
    lines = []
    for f in step.findings:
        tc = f.traceability.value
        line = f"[{f.code}] [{tc.upper()}] {f.description}"
        if f.verbatim_quote:
            line += f' — "{f.verbatim_quote}"'
        lines.append(line)
    return lines
