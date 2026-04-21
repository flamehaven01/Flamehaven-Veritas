"""KU Research Report Writing Template.

Maps CritiqueReport to the University of Kisumu (KU) Research Report
structure: Title → Abstract → Introduction → Methodology → Results →
Discussion → Conclusion → References.
"""

from __future__ import annotations

from .base import BaseTemplate, TemplateSection


class KUTemplate(BaseTemplate):
    """KU Research Report (8-chapter layout)."""

    TEMPLATE_ID = "ku"
    DISPLAY_NAME = "KU Research Report Template"

    SECTIONS = [
        "Title Page",
        "Abstract",
        "Introduction",
        "Methodology",
        "Results & Findings",
        "Discussion",
        "Conclusion",
        "References & Appendices",
    ]

    def build(self, report) -> list[TemplateSection]:
        sections: list[TemplateSection] = []

        # Title Page
        sections.append(
            TemplateSection(
                title="Title Page",
                level=1,
                body="\n".join(
                    [
                        "VERITAS — EXPERIMENTAL REPORT ANALYSIS v2.1",
                        "",
                        f"Critique Round    : {report.round_number}",
                        f"PRECHECK Mode     : {report.precheck.mode.value}",
                        f"Missing Artifacts : {', '.join(report.precheck.missing_artifacts) or 'none'}",
                        f"Omega Score       : {report.omega_score:.4f}",
                        "",
                        "Prepared using the KU Research Report Template",
                    ]
                ),
            )
        )

        # Abstract
        step1 = report.step("1")
        abstract = (
            f"PRECHECK MODE: {report.precheck.mode.value}. "
            f"MISSING ARTIFACTS: {', '.join(report.precheck.missing_artifacts) or 'none'}. "
            + (
                f"Experiment class: {report.experiment_class.value}. "
                if report.experiment_class
                else ""
            )
            + (
                step1.vulnerable_claim
                if step1 and step1.vulnerable_claim
                else "See Claim Integrity section for details."
            )
        )
        sections.append(TemplateSection(title="Abstract", level=1, body=abstract))

        # Introduction — STEP 0
        cls_label = report.experiment_class.value if report.experiment_class else "UNKNOWN"
        secondary = (
            f", SECONDARY={report.experiment_class_secondary.value}"
            if report.experiment_class_secondary
            else ""
        )
        intro = (
            f"This report is classified as **{cls_label}{secondary}**. "
            f"{report.experiment_class_reason} "
            f"The critique evaluates claim integrity (40%), traceability (30%), "
            f"series continuity (20%), and publication readiness (10%)."
        )
        sections.append(TemplateSection(title="Introduction", level=1, body=intro))

        # Methodology — STEP 2 (traceability as methodology audit)
        step2 = report.step("2")
        sections.append(
            TemplateSection(
                title="Methodology",
                level=1,
                body=_step_body(step2),
                findings=_format_findings(step2),
            )
        )

        # Results & Findings — STEP 1 + STEP 3
        step3 = report.step("3")
        results_body = "**Claim Integrity**\n\n" + _step_body(step1)
        if step3:
            results_body += "\n\n**Series Continuity**\n\n" + _step_body(step3)
        findings = _format_findings(step1) + _format_findings(step3)
        sections.append(
            TemplateSection(
                title="Results & Findings",
                level=1,
                body=results_body,
                findings=findings,
            )
        )

        # Discussion — STEP 4 + evidence conflicts
        step4 = report.step("4")
        disc_body = _step_body(step4)
        if report.evidence_conflicts:
            disc_body += f"\n\n**Evidence Conflicts ({len(report.evidence_conflicts)})**\n\n"
            for ec in report.evidence_conflicts:
                disc_body += f"- Rank {ec.rank.name}: {ec.artifact_a} vs {ec.artifact_b} — {ec.description}\n"
        sections.append(TemplateSection(title="Discussion", level=1, body=disc_body))

        # Conclusion — STEP 5
        conclusion = report.priority_fix
        if report.next_liability:
            conclusion += f"\n\n**Next Liability:** {report.next_liability}"
        sections.append(TemplateSection(title="Conclusion", level=1, body=conclusion))

        # References & Appendices
        refs = []
        if report.hold_events:
            refs.append("**HOLD Events:**")
            for h in report.hold_events:
                refs.append(
                    f"- {h.event_id}: cause_stated={h.cause_stated}, "
                    f"disposition={h.disposition.value}, "
                    f"traceable_to_data={h.traceable_to_data}"
                )
        refs.append(
            f"\n**Omega Score:** {report.omega_score:.4f} (1.0=fully traceable, 0.0=blocked)"
        )
        sections.append(
            TemplateSection(
                title="References & Appendices",
                level=1,
                body="\n".join(refs),
            )
        )

        # Bibliography Analysis (optional)
        if report.bibliography_stats:
            s = report.bibliography_stats
            fmt = ", ".join(s.formats_detected) or "Unknown"
            yr = f"{s.oldest_year}–{s.newest_year}" if s.oldest_year else "N/A"
            sections.append(
                TemplateSection(
                    title="Bibliography Analysis",
                    level=1,
                    body="\n".join(
                        [
                            f"Total references   : {s.total_refs}",
                            f"Recent ratio (≤5yr): {s.recent_ratio:.1%}",
                            f"Year range         : {yr}",
                            f"Citation format    : {fmt}",
                            f"Self-cite detected : {'Yes' if s.self_citation_detected else 'No'}",
                            f"Quality score      : {s.quality_score:.4f}",
                        ]
                    ),
                )
            )

        # Reproducibility Checklist (optional)
        if report.reproducibility_checklist:
            rc = report.reproducibility_checklist
            sections.append(
                TemplateSection(
                    title="Reproducibility Checklist",
                    level=1,
                    body=f"Score: {rc.score:.4f} | {rc.summary}",
                    findings=[
                        f"[{item.code}] [{'SATISFIED' if item.satisfied else 'NOT MET' if item.satisfied is False else 'UNKNOWN'}] "
                        f"{item.criterion}" + (f" — {item.note}" if item.note else "")
                        for item in rc.items
                    ],
                )
            )

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
