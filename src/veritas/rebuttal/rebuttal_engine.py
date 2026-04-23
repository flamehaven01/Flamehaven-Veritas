"""RebuttalEngine — maps CritiqueReport findings to structured rebuttal items.

Algorithm (v3.3):
  For each StepFinding in report.steps:
    - Derive issue_id = "R-{step_id}.{finding_index}"
    - Derive category from step_id + IRF dimension map
    - Assign severity from traceability class + step weight
    - Generate author_response_template keyed to category
    - Yield RebuttalItem(addressed=False by default)
  Compute rebuttal_coverage = addressed_count / total_issues
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..types import CritiqueReport, StepFinding, TraceabilityClass

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class RebuttalItem:
    """One reviewer concern mapped to a structured rebuttal entry."""

    issue_id: str
    category: str
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW
    reviewer_text: str
    author_response_template: str
    addressed: bool = False

    def mark_addressed(self) -> RebuttalItem:
        return RebuttalItem(
            issue_id=self.issue_id,
            category=self.category,
            severity=self.severity,
            reviewer_text=self.reviewer_text,
            author_response_template=self.author_response_template,
            addressed=True,
        )

    def as_dict(self) -> dict:
        return {
            "issue_id": self.issue_id,
            "category": self.category,
            "severity": self.severity,
            "reviewer_text": self.reviewer_text,
            "author_response_template": self.author_response_template,
            "addressed": self.addressed,
        }


@dataclass
class RebuttalReport:
    """Structured rebuttal report derived from a CritiqueReport."""

    items: list[RebuttalItem] = field(default_factory=list)
    style: str = "ieee"
    generated_at: str = ""

    @property
    def rebuttal_coverage(self) -> float:
        if not self.items:
            return 1.0
        addressed = sum(1 for i in self.items if i.addressed)
        return addressed / len(self.items)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.items if i.severity == "CRITICAL")

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.items if i.severity == "HIGH")

    def items_by_severity(self, severity: str) -> list[RebuttalItem]:
        return [i for i in self.items if i.severity == severity]

    def as_dict(self) -> dict:
        return {
            "style": self.style,
            "generated_at": self.generated_at,
            "rebuttal_coverage": round(self.rebuttal_coverage, 4),
            "total_issues": len(self.items),
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "items": [i.as_dict() for i in self.items],
        }


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STEP_CATEGORY = {
    "1": "CLAIM_INTEGRITY",
    "2": "TRACEABILITY",
    "3": "SERIES_CONTINUITY",
    "4": "PUBLICATION_READINESS",
    "5": "PRIORITY_FIX",
}

_SEVERITY_BY_TRACEABILITY = {
    TraceabilityClass.NOT_TRACEABLE: "HIGH",
    TraceabilityClass.PARTIALLY_TRACEABLE: "MEDIUM",
    TraceabilityClass.TRACEABLE: "LOW",
}

_RESPONSE_TEMPLATES = {
    "CLAIM_INTEGRITY": (
        "We have revised the central claim in the Abstract/Introduction to improve "
        "precision. The scope of the claim is now bounded by [SPECIFY BOUNDS]. "
        "See revised Section [X], paragraph [N]."
    ),
    "TRACEABILITY": (
        "We have added the missing artifact '{artifact}' as Supplementary Material S[N]. "
        "The artifact directly traces to Result [RESULT_ID] via the chain: "
        "[DATA_FILE] → [ANALYSIS_SCRIPT] → [FIGURE/TABLE]."
    ),
    "SERIES_CONTINUITY": (
        "We have resolved the continuity gap by [DESCRIBE ACTION]. "
        "The revised methodology section now explicitly links [STEP_A] to [STEP_B] "
        "with intermediate checkpoints documented in Appendix [N]."
    ),
    "PUBLICATION_READINESS": (
        "We have addressed this by [DESCRIBE REVISION]. "
        "The manuscript now meets [JOURNAL] formatting/completeness standards. "
        "Specifically, [SECTION] was revised to include [ELEMENT]."
    ),
    "STATISTICAL": (
        "We have added the required statistical reporting: effect size (Cohen's d = [X]), "
        "confidence interval ([X]% CI: [LB]–[UB]), and power analysis (n=[N], "
        "power=[P], α=[A]). See Table [N] in the revised manuscript."
    ),
    "SCOPE_VIOLATION": (
        "We agree the language in the Discussion was too strong. We have revised "
        "'[ORIGINAL_PHRASE]' to '[REVISED_PHRASE]' to accurately reflect "
        "the limits of the current evidence."
    ),
    "DEFAULT": (
        "We have addressed this concern by [DESCRIBE ACTION]. "
        "The revised manuscript reflects this change in Section [X]. "
        "Please see our response in the accompanying revision notes."
    ),
}

_CRITICAL_KEYWORDS = re.compile(
    r"\b(no\s+central\s+claim|blocked|missing\s+artifact|critical|not\s+traceable)\b",
    re.IGNORECASE,
)

_STAT_KEYWORDS = re.compile(
    r"\b(p.value|effect\s+size|confidence\s+interval|power\s+analysis|sample\s+size|"
    r"statistical|cohen|ci\b)\b",
    re.IGNORECASE,
)

_SCOPE_KEYWORDS = re.compile(
    r"\b(overclai|definitive|proves?|confirms?|demonstrates?\s+that)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class RebuttalEngine:
    """Maps a CritiqueReport to a structured rebuttal report.

    Usage::
        engine = RebuttalEngine()
        report = engine.generate(critique_report, style="ieee")
    """

    def generate(self, report: CritiqueReport, style: str = "ieee") -> RebuttalReport:
        """Generate RebuttalReport from a CritiqueReport.

        Args:
            report: Completed CritiqueReport from SciExpCritiqueEngine.critique().
            style:  Citation/format style. One of 'ieee', 'acm', 'nature'. Default 'ieee'.

        Returns:
            RebuttalReport with structured RebuttalItems and coverage metric.
        """
        items: list[RebuttalItem] = []

        for step in report.steps:
            if step.not_applicable:
                continue
            step_items = self._extract_from_step(step)
            items.extend(step_items)

        # If no findings from steps, parse priority_fix
        if not items and report.priority_fix:
            items.append(self._parse_priority_fix(report.priority_fix))

        return RebuttalReport(
            items=items,
            style=style,
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    # ── private ──────────────────────────────────────────────────────────────

    def _extract_from_step(self, step) -> list[RebuttalItem]:
        items = []
        if step.findings:
            for idx, finding in enumerate(step.findings, start=1):
                item = self._finding_to_item(step.step_id, idx, finding)
                items.append(item)
        elif step.prose and not step.not_applicable:
            # Synthesise a single item from the prose
            prose_item: RebuttalItem | None = self._prose_to_item(step.step_id, step.prose)
            if prose_item:
                items.append(prose_item)
        return items

    def _finding_to_item(self, step_id: str, idx: int, finding: StepFinding) -> RebuttalItem:
        category = self._infer_category(step_id, finding.description)
        severity = self._infer_severity(step_id, finding)
        template = self._select_template(category, finding.description)
        return RebuttalItem(
            issue_id=f"R-{step_id}.{idx}",
            category=category,
            severity=severity,
            reviewer_text=finding.description,
            author_response_template=template,
        )

    def _prose_to_item(self, step_id: str, prose: str) -> RebuttalItem | None:
        prose_stripped = prose.strip()
        if not prose_stripped or len(prose_stripped) < 10:
            return None
        category = _STEP_CATEGORY.get(step_id, "DEFAULT")
        severity = "HIGH" if _CRITICAL_KEYWORDS.search(prose_stripped) else "MEDIUM"
        template = self._select_template(category, prose_stripped)
        return RebuttalItem(
            issue_id=f"R-{step_id}.1",
            category=category,
            severity=severity,
            reviewer_text=prose_stripped[:300],
            author_response_template=template,
        )

    def _infer_category(self, step_id: str, text: str) -> str:
        if _STAT_KEYWORDS.search(text):
            return "STATISTICAL"
        if _SCOPE_KEYWORDS.search(text):
            return "SCOPE_VIOLATION"
        return _STEP_CATEGORY.get(step_id, "DEFAULT")

    @staticmethod
    def _infer_severity(step_id: str, finding: StepFinding) -> str:
        base = _SEVERITY_BY_TRACEABILITY.get(finding.traceability, "MEDIUM")
        if step_id == "1" and finding.traceability == TraceabilityClass.NOT_TRACEABLE:
            return "CRITICAL"
        return base

    @staticmethod
    def _select_template(category: str, context: str) -> str:
        template = _RESPONSE_TEMPLATES.get(category, _RESPONSE_TEMPLATES["DEFAULT"])
        # Substitute artifact placeholder if detectable
        if "{artifact}" in template:
            art_match = re.search(
                r"\b(sha256|hash|artifact|data\s+file|figure|table)\b", context, re.IGNORECASE
            )
            placeholder = art_match.group(0) if art_match else "required artifact"
            template = template.replace("{artifact}", placeholder)
        return template

    def _parse_priority_fix(self, priority_fix: str) -> RebuttalItem:
        category = "DEFAULT"
        if _STAT_KEYWORDS.search(priority_fix):
            category = "STATISTICAL"
        elif _SCOPE_KEYWORDS.search(priority_fix):
            category = "SCOPE_VIOLATION"
        severity = "HIGH" if _CRITICAL_KEYWORDS.search(priority_fix) else "MEDIUM"
        return RebuttalItem(
            issue_id="R-5.1",
            category=category,
            severity=severity,
            reviewer_text=priority_fix[:300],
            author_response_template=_RESPONSE_TEMPLATES.get(
                category, _RESPONSE_TEMPLATES["DEFAULT"]
            ),
        )
