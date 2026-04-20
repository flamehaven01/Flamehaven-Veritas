"""VERITAS — AI Critique Experimental Report Analysis Framework — Type Universe.

Compiled from the VERITAS — AI Critique Experimental Report Analysis Framework protocol specification.
No external imports. All critique types are self-contained.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SciExpMode(Enum):
    """PRECHECK artifact sufficiency mode."""
    FULL    = "FULL"
    PARTIAL = "PARTIAL"
    LIMITED = "LIMITED"
    BLOCKED = "BLOCKED"


class ExperimentClass(Enum):
    """STEP 0 experiment classification."""
    PARITY    = "PARITY"
    EXTENSION = "EXTENSION"
    RCA       = "RCA"
    ABLATION  = "ABLATION"
    MULTIAXIS = "MULTIAXIS"


class TraceabilityClass(Enum):
    """Evidence traceability verdict — 3 values, no substitutes."""
    TRACEABLE           = "traceable"
    PARTIALLY_TRACEABLE = "partially traceable"
    NOT_TRACEABLE       = "not traceable"


class EvidenceRank(Enum):
    """Evidence precedence hierarchy (lower = higher authority)."""
    MEASURED_ARTIFACT = 1
    HASH_MANIFEST     = 2
    INLINE_FIGURE     = 3
    NARRATIVE         = 4
    CROSS_CYCLE_PROSE = 5


class HoldDisposition(Enum):
    """HOLD event disposition state."""
    ISOLATED        = "isolated"
    PATCHED         = "patched"
    CARRIED_FORWARD = "carried_forward"
    UNDOCUMENTED    = "undocumented"


class MethodologyClass(Enum):
    """Research/experiment methodology type (from paper analysis)."""
    RCT           = "RCT"
    META_ANALYSIS = "META_ANALYSIS"
    COHORT        = "COHORT"
    CASE_STUDY    = "CASE_STUDY"
    SURVEY        = "SURVEY"
    EXPERIMENTAL  = "EXPERIMENTAL"
    COMPUTATIONAL = "COMPUTATIONAL"
    OBSERVATIONAL = "OBSERVATIONAL"
    UNKNOWN       = "UNKNOWN"


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
        return {"M": self.M, "A": self.A, "D": self.D,
                "I": self.I, "F": self.F, "P": self.P,
                "composite": self.composite, "passed": self.passed,
                "source": self.source}


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
    mode:              SciExpMode
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
    rank:        EvidenceRank
    artifact_a:  str
    artifact_b:  str
    description: str


@dataclass
class HoldEvent:
    """HOLD event record for STEP 1.4 audit."""
    event_id:          str
    cause_stated:      bool
    disposition:       HoldDisposition
    characterization:  str
    traceable_to_data: bool


@dataclass
class StepFinding:
    """Single finding within a critique step."""
    code:           str
    description:    str
    traceability:   TraceabilityClass
    verbatim_quote: str | None = None
    evidence_rank:  EvidenceRank | None = None
    hold_event:     HoldEvent | None = None


@dataclass
class StepResult:
    """One critique step — enforces OUTPUT CONTRACT prose shape."""
    step_id:          str
    weight:           float
    prose:            str
    findings:         list[StepFinding] = field(default_factory=list)
    vulnerable_claim: str | None = None
    not_applicable:   bool = False


@dataclass
class CritiqueReport:
    """Full VERITAS — AI Critique Experimental Report Analysis Framework output."""
    precheck: PrecheckResult

    experiment_class:           ExperimentClass | None = None
    experiment_class_secondary: ExperimentClass | None = None
    experiment_class_reason:    str = ""

    steps:          list[StepResult] = field(default_factory=list)
    priority_fix:   str = ""
    next_liability: str | None = None

    round_number:       int   = 1
    omega_score:        float = 0.0
    evidence_conflicts: list[EvidenceConflict] = field(default_factory=list)
    hold_events:        list[HoldEvent] = field(default_factory=list)

    # ---- LOGOS / Paper Intelligence (optional, None when not available)
    irf_scores:       IRF6DScores | None    = None
    hsta_scores:      HSTA4DScores | None   = None
    methodology_class: MethodologyClass | None = None
    hypothesis_text:   str | None           = None
    logos_omega:       float | None         = None  # LOGOS-computed omega
    hybrid_omega:      float | None         = None  # 0.6*sciexp + 0.4*logos

    # ---- Repository-derived extensions (BibliographyAnalyzer + ReproducibilityChecklist)
    bibliography_stats:        BibliographyStats | None        = None
    reproducibility_checklist: ReproducibilityChecklist | None = None

    def step(self, step_id: str) -> StepResult | None:
        return next((s for s in self.steps if s.step_id == step_id), None)

    def is_blocked(self) -> bool:
        return self.precheck.mode == SciExpMode.BLOCKED

    def partially_traceable_count(self) -> int:
        return sum(
            1 for s in self.steps for f in s.findings
            if f.traceability == TraceabilityClass.PARTIALLY_TRACEABLE
        )

    def not_traceable_count(self) -> int:
        return sum(
            1 for s in self.steps for f in s.findings
            if f.traceability == TraceabilityClass.NOT_TRACEABLE
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
    total_refs:             int        = 0
    recent_ratio:           float      = 0.0   # refs <= 5 years old / total
    oldest_year:            int | None = None
    newest_year:            int | None = None
    formats_detected:       list[str]  = field(default_factory=list)
    self_citation_detected: bool       = False

    @property
    def quality_score(self) -> float:
        """0–1 composite: recency (50%) + breadth (50%), penalty for self-cites."""
        if self.total_refs == 0:
            return 0.0
        recency = self.recent_ratio * 0.5
        breadth = min(self.total_refs / 30.0, 1.0) * 0.5
        score   = recency + breadth
        if self.self_citation_detected:
            score *= 0.9
        return round(score, 4)


@dataclass
class ReproducibilityItem:
    """Single ARRIVE / CONSORT-style reproducibility criterion."""
    code:      str
    criterion: str
    satisfied: bool | None = None   # None = cannot determine from text
    note:      str            = ""


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
        return cls(items=[
            ReproducibilityItem("DATA",   "Raw data publicly available"),
            ReproducibilityItem("CODE",   "Analysis code publicly available"),
            ReproducibilityItem("PREREG", "Study preregistered (OSF/ClinicalTrials)"),
            ReproducibilityItem("POWER",  "Sample size / power calculation reported"),
            ReproducibilityItem("STATS",  "Statistical methods fully described"),
            ReproducibilityItem("BLIND",  "Blinding / masking procedure described"),
            ReproducibilityItem("EXCL",   "Inclusion / exclusion criteria stated"),
            ReproducibilityItem("CONF",   "Conflicts of interest declared"),
        ])

    @property
    def score(self) -> float:
        """Ratio of satisfied criteria over determinable criteria."""
        satisfied    = sum(1 for i in self.items if i.satisfied is True)
        determinable = sum(1 for i in self.items if i.satisfied is not None)
        if determinable == 0:
            return 0.0
        return round(satisfied / determinable, 4)

    @property
    def summary(self) -> str:
        satisfied = sum(1 for i in self.items if i.satisfied is True)
        not_sat   = sum(1 for i in self.items if i.satisfied is False)
        unknown   = sum(1 for i in self.items if i.satisfied is None)
        return f"{satisfied} satisfied / {not_sat} not satisfied / {unknown} unknown"
