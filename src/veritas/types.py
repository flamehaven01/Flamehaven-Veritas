"""VERITAS — AI Critique Experimental Report Analysis Framework — Type Universe.

Compiled from the VERITAS — AI Critique Experimental Report Analysis Framework protocol specification.
No external imports. All critique types are self-contained.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SciExpMode(Enum):
    """PRECHECK artifact sufficiency mode."""

    FULL = "FULL"
    PARTIAL = "PARTIAL"
    LIMITED = "LIMITED"
    BLOCKED = "BLOCKED"


class ExperimentClass(Enum):
    """STEP 0 experiment classification."""

    PARITY = "PARITY"
    EXTENSION = "EXTENSION"
    RCA = "RCA"
    ABLATION = "ABLATION"
    MULTIAXIS = "MULTIAXIS"


class TraceabilityClass(Enum):
    """Evidence traceability verdict — 3 values, no substitutes."""

    TRACEABLE = "traceable"
    PARTIALLY_TRACEABLE = "partially traceable"
    NOT_TRACEABLE = "not traceable"


class EvidenceRank(Enum):
    """Evidence precedence hierarchy (lower = higher authority)."""

    MEASURED_ARTIFACT = 1
    HASH_MANIFEST = 2
    INLINE_FIGURE = 3
    NARRATIVE = 4
    CROSS_CYCLE_PROSE = 5


class HoldDisposition(Enum):
    """HOLD event disposition state."""

    ISOLATED = "isolated"
    PATCHED = "patched"
    CARRIED_FORWARD = "carried_forward"
    UNDOCUMENTED = "undocumented"


class MethodologyClass(Enum):
    """Research/experiment methodology type (from paper analysis)."""

    RCT = "RCT"
    META_ANALYSIS = "META_ANALYSIS"
    COHORT = "COHORT"
    CASE_STUDY = "CASE_STUDY"
    SURVEY = "SURVEY"
    EXPERIMENTAL = "EXPERIMENTAL"
    COMPUTATIONAL = "COMPUTATIONAL"
    OBSERVATIONAL = "OBSERVATIONAL"
    UNKNOWN = "UNKNOWN"


class ClaimType(Enum):
    """Academic claim typology — determines required traceability evidence.

    EMPIRICAL      — measured data anchor + sha256 required
    THEORETICAL    — logical derivation chain required
    COMPARATIVE    — controlled comparison baseline required
    METHODOLOGICAL — protocol documentation required
    UNKNOWN        — cannot be classified from text
    """

    EMPIRICAL = "empirical"
    THEORETICAL = "theoretical"
    COMPARATIVE = "comparative"
    METHODOLOGICAL = "methodological"
    UNKNOWN = "unknown"


@dataclass
class IRF6DScores:
    """LOGOS IRF-Calc 6D dimension scores for a report.

    M: Methodic Doubt  — uncertainty acknowledgment & premise clarity
    A: Axiom           — foundational grounding & hypothesis quality
    D: Deduction       — logical rigor & consistency
    I: Induction       — empirical support & numeric density
    F: Falsification   — testability, reproducibility, control
    P: Paradigm        — peer-review alignment & reference density

    composite = geometric mean of all 6 (epsilon-smoothed)
    passed    = composite >= threshold AND all dims >= component_min
    """

    M: float
    A: float
    D: float
    I: float  # noqa: E741
    F: float
    P: float
    composite: float
    passed: bool
    source: str = "local"  # "local" | "logos_server" | "logos_irf_pipeline"

    def as_dict(self) -> dict:
        return {
            "M": self.M,
            "A": self.A,
            "D": self.D,
            "I": self.I,
            "F": self.F,
            "P": self.P,
            "composite": self.composite,
            "passed": self.passed,
            "source": self.source,
        }


@dataclass
class HSTA4DScores:
    """HSTA extension 4 dimensions (from BioMedical-Paper-Harvester quality tensor).

    N: Novelty        — semantic uniqueness of findings
    C: Consistency    — internal cross-reference agreement
    T: Temporality    — citation/date recency signal
    R: Reproducibility— method detail completeness
    """

    N: float
    C: float
    T: float
    R: float

    @property
    def composite(self) -> float:
        return (self.N + self.C + self.T + self.R) / 4.0


@dataclass
class PrecheckResult:
    """PRECHECK gate output — exactly 2 lines per OUTPUT CONTRACT."""

    mode: SciExpMode
    missing_artifacts: list[str]

    @property
    def line1(self) -> str:
        return f"PRECHECK MODE: {self.mode.value}"

    @property
    def line2(self) -> str:
        arts = ", ".join(self.missing_artifacts) if self.missing_artifacts else "none"
        return f"MISSING ARTIFACTS: {arts}"

    def render(self) -> str:
        return f"{self.line1}\n{self.line2}"


@dataclass
class EvidenceConflict:
    """Named conflict between same-rank artifacts."""

    rank: EvidenceRank
    artifact_a: str
    artifact_b: str
    description: str


@dataclass
class HoldEvent:
    """HOLD event record for STEP 1.4 audit."""

    event_id: str
    cause_stated: bool
    disposition: HoldDisposition
    characterization: str
    traceable_to_data: bool


@dataclass
class StepFinding:
    """Single finding within a critique step."""

    code: str
    description: str
    traceability: TraceabilityClass
    verbatim_quote: str | None = None
    evidence_rank: EvidenceRank | None = None
    hold_event: HoldEvent | None = None


@dataclass
class StepResult:
    """One critique step — enforces OUTPUT CONTRACT prose shape."""

    step_id: str
    weight: float
    prose: str
    findings: list[StepFinding] = field(default_factory=list)
    vulnerable_claim: str | None = None
    not_applicable: bool = False


# ---------------------------------------------------------------------------
# v3.3 — Section-Aware Analysis types
# ---------------------------------------------------------------------------


@dataclass
class DocumentSection:
    """One parsed section of an academic document."""

    name: str  # ABSTRACT | INTRODUCTION | METHODS | RESULTS | DISCUSSION | CONCLUSION | OTHER
    text: str
    start_pos: int
    end_pos: int

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass
class SectionMap:
    """Parsed section structure of an academic document.

    ``coverage`` is the fraction of canonical sections detected (0.0–1.0).
    A coverage of 0.0 means no headers were found; analysis falls back to
    full-text mode.
    """

    sections: dict[str, DocumentSection] = field(default_factory=dict)
    coverage: float = 0.0

    def get(self, name: str) -> str | None:
        """Return text for a section by canonical name (case-insensitive)."""
        sec = self.sections.get(name.upper())
        return sec.text if sec is not None else None

    def has(self, name: str) -> bool:
        return name.upper() in self.sections

    def combined(self, *names: str) -> str:
        """Concatenate text of multiple sections."""
        parts = [self.get(n) or "" for n in names]
        return " ".join(p for p in parts if p)


@dataclass
class StatValidity:
    """Statistical reporting completeness score for an academic report.

    Each field reflects whether the criterion was detected in the text.
    ``score`` is a weighted sum (p*0.30 + effect*0.25 + ci*0.20 + power*0.15 + sample*0.10).
    ``issues`` lists human-readable descriptions of unmet criteria.
    """

    p_value_reported: bool = False
    p_value_numeric: bool = False  # True when "p = 0.032" vs just "significant"
    effect_size_reported: bool = False
    ci_reported: bool = False
    power_reported: bool = False
    sample_size_stated: bool = False
    score: float = 0.0
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "p_value_reported": self.p_value_reported,
            "p_value_numeric": self.p_value_numeric,
            "effect_size_reported": self.effect_size_reported,
            "ci_reported": self.ci_reported,
            "power_reported": self.power_reported,
            "sample_size_stated": self.sample_size_stated,
            "score": self.score,
            "issues": list(self.issues),
        }


@dataclass
class AnalysisConfidence:
    """Meta-uncertainty signal for the VERITAS engine's own analysis.

    Editors use this to understand how reliable the omega score is given
    the document structure and artifact density.

    level: HIGH (>=0.70 coverage, >=5 artifacts) |
           MEDIUM (>=0.40 coverage or >=2 artifacts) |
           LOW (sparse document)
    """

    level: str = "LOW"  # HIGH | MEDIUM | LOW
    artifact_count: int = 0
    text_length: int = 0
    section_coverage: float = 0.0
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "level": self.level,
            "artifact_count": self.artifact_count,
            "text_length": self.text_length,
            "section_coverage": self.section_coverage,
            "reason": self.reason,
        }


@dataclass
class CritiqueReport:
    """Full VERITAS — AI Critique Experimental Report Analysis Framework output."""

    schema_version: str = "3.3"

    precheck: PrecheckResult = field(
        default_factory=lambda: PrecheckResult(SciExpMode.BLOCKED, [])
    )

    experiment_class: ExperimentClass | None = None
    experiment_class_secondary: ExperimentClass | None = None
    experiment_class_reason: str = ""

    steps: list[StepResult] = field(default_factory=list)
    priority_fix: str = ""
    next_liability: str | None = None

    round_number: int = 1
    omega_score: float = 0.0
    evidence_conflicts: list[EvidenceConflict] = field(default_factory=list)
    hold_events: list[HoldEvent] = field(default_factory=list)

    # ---- LOGOS / Paper Intelligence (optional, None when not available)
    irf_scores: IRF6DScores | None = None
    hsta_scores: HSTA4DScores | None = None
    methodology_class: MethodologyClass | None = None
    hypothesis_text: str | None = None
    logos_omega: float | None = None  # LOGOS-computed omega
    hybrid_omega: float | None = None  # 0.6*sciexp + 0.4*logos

    # ---- Repository-derived extensions (BibliographyAnalyzer + ReproducibilityChecklist)
    bibliography_stats: BibliographyStats | None = None
    reproducibility_checklist: ReproducibilityChecklist | None = None

    # ---- SPAR claim-aware review (optional; None when spar-framework not installed)
    spar_review: dict | None = None

    # ---- Multi-round drift tracking (v2.3.0)
    delta_omega: float | None = None  # signed: current - previous round omega
    drift_metrics: dict | None = None  # DriftMetrics.as_dict() — JSON-serializable
    jsd_penalized_omega: float | None = None  # JSD-gated omega (multi-round only)

    # ---- v3.3 Section-Aware + Academic Discourse Intelligence
    section_map: SectionMap | None = None
    claim_type: ClaimType | None = None
    stat_validity: StatValidity | None = None
    analysis_confidence: AnalysisConfidence | None = None

    def step(self, step_id: str) -> StepResult | None:
        return next((s for s in self.steps if s.step_id == step_id), None)

    def is_blocked(self) -> bool:
        return self.precheck.mode == SciExpMode.BLOCKED

    def partially_traceable_count(self) -> int:
        return sum(
            1
            for s in self.steps
            for f in s.findings
            if f.traceability == TraceabilityClass.PARTIALLY_TRACEABLE
        )

    def not_traceable_count(self) -> int:
        return sum(
            1
            for s in self.steps
            for f in s.findings
            if f.traceability == TraceabilityClass.NOT_TRACEABLE
        )

    def to_round_summary(self) -> dict:
        """Minimal JSON-serializable summary for cross-round drift tracking.

        Saves only the fields needed for next-round DriftEngine computation.
        Write to ``{stem}_r{N}.json`` for ``--prev`` reload.
        """
        return {
            "schema_version": self.schema_version,
            "round_number": self.round_number,
            "omega_score": self.omega_score,
            "hybrid_omega": self.hybrid_omega,
            "irf_scores": self.irf_scores.as_dict() if self.irf_scores else None,
            "delta_omega": self.delta_omega,
            "drift_metrics": self.drift_metrics,
            "jsd_penalized_omega": self.jsd_penalized_omega,
        }

    @classmethod
    def from_round_summary(cls, data: dict) -> CritiqueReport:
        """Reconstruct minimal CritiqueReport from to_round_summary() dict.

        Only restores the fields required for multi-round drift computation;
        all other fields are set to safe defaults.
        """
        irf_data = data.get("irf_scores")
        irf_scores: IRF6DScores | None = None
        if irf_data and isinstance(irf_data, dict):
            irf_scores = IRF6DScores(
                M=float(irf_data.get("M", 0.0)),
                A=float(irf_data.get("A", 0.0)),
                D=float(irf_data.get("D", 0.0)),
                I=float(irf_data.get("I", 0.0)),
                F=float(irf_data.get("F", 0.0)),
                P=float(irf_data.get("P", 0.0)),
                composite=float(irf_data.get("composite", 0.0)),
                passed=bool(irf_data.get("passed", False)),
                source=str(irf_data.get("source", "loaded")),
            )
        hybrid = data.get("hybrid_omega")
        return cls(
            schema_version=str(data.get("schema_version", "3.2")),
            precheck=PrecheckResult(mode=SciExpMode.FULL, missing_artifacts=[]),
            round_number=int(data.get("round_number", 1)),
            omega_score=float(data.get("omega_score", 0.0)),
            hybrid_omega=float(hybrid) if hybrid is not None else None,
            irf_scores=irf_scores,
            delta_omega=data.get("delta_omega"),
            drift_metrics=data.get("drift_metrics"),
            jsd_penalized_omega=data.get("jsd_penalized_omega"),
        )


# ---------------------------------------------------------------------------
# Repository-derived extensions
# ---------------------------------------------------------------------------


@dataclass
class BibliographyStats:
    """Reference section quality metrics (from BibliographyAnalyzer).

    Derived from patterns in:
      - latex-scientific-paper-templates (labreport.bst author-year, <=5 authors)
      - Markdown-Templates (Harvard Anglia Ruskin University CSL, author-date)
    """

    total_refs: int = 0
    recent_ratio: float = 0.0  # refs <= 5 years old / total
    oldest_year: int | None = None
    newest_year: int | None = None
    formats_detected: list[str] = field(default_factory=list)
    self_citation_detected: bool = False

    @property
    def quality_score(self) -> float:
        """0-1 composite: recency (50%) + breadth (50%), penalty for self-cites."""
        if self.total_refs == 0:
            return 0.0
        recency = self.recent_ratio * 0.5
        breadth = min(self.total_refs / 30.0, 1.0) * 0.5
        score = recency + breadth
        if self.self_citation_detected:
            score *= 0.9
        return round(score, 4)


@dataclass
class ReproducibilityItem:
    """Single ARRIVE / CONSORT-style reproducibility criterion."""

    code: str
    criterion: str
    satisfied: bool | None = None  # None = cannot determine from text
    note: str = ""


@dataclass
class ReproducibilityChecklist:
    """Structured reproducibility assessment (ARRIVE 2.0 / CONSORT 2010 / TOP).

    Criteria adapted from:
      - ARRIVE 2.0  (animal research)
      - CONSORT 2010 (clinical trials)
      - STROBE       (observational studies)
      - TOP Guidelines (transparency & openness promotion)
    """

    items: list[ReproducibilityItem] = field(default_factory=list)

    @classmethod
    def default(cls) -> ReproducibilityChecklist:
        return cls(
            items=[
                ReproducibilityItem("DATA", "Raw data publicly available"),
                ReproducibilityItem("CODE", "Analysis code publicly available"),
                ReproducibilityItem("PREREG", "Study preregistered (OSF/ClinicalTrials)"),
                ReproducibilityItem("POWER", "Sample size / power calculation reported"),
                ReproducibilityItem("STATS", "Statistical methods fully described"),
                ReproducibilityItem("BLIND", "Blinding / masking procedure described"),
                ReproducibilityItem("EXCL", "Inclusion / exclusion criteria stated"),
                ReproducibilityItem("CONF", "Conflicts of interest declared"),
            ]
        )

    @property
    def score(self) -> float:
        """Ratio of satisfied criteria over determinable criteria."""
        satisfied = sum(1 for i in self.items if i.satisfied is True)
        determinable = sum(1 for i in self.items if i.satisfied is not None)
        if determinable == 0:
            return 0.0
        return round(satisfied / determinable, 4)

    @property
    def summary(self) -> str:
        satisfied = sum(1 for i in self.items if i.satisfied is True)
        not_sat = sum(1 for i in self.items if i.satisfied is False)
        unknown = sum(1 for i in self.items if i.satisfied is None)
        return f"{satisfied} satisfied / {not_sat} not satisfied / {unknown} unknown"


