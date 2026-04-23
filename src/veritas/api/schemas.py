"""API Schemas — Pydantic v2 request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CritiqueRequest(BaseModel):
    report_text: str = Field(..., description="Raw text of the experimental report")
    template: str = Field("bmj", description="Output template: 'bmj' or 'ku'")
    round_number: int = Field(1, ge=1, description="Critique round number")
    domain: str = Field(
        "biomedical",
        description="IRF scoring domain: biomedical (default) | cs | math",
    )


class FindingOut(BaseModel):
    code: str
    description: str
    traceability: str
    verbatim_quote: str | None = None


class StepOut(BaseModel):
    step_id: str
    weight: float
    prose: str
    findings: list[FindingOut]
    vulnerable_claim: str | None = None
    not_applicable: bool = False


class PrecheckOut(BaseModel):
    mode: str
    missing_artifacts: list[str]
    line1: str
    line2: str


class EvidenceConflictOut(BaseModel):
    rank: str
    artifact_a: str
    artifact_b: str
    description: str


class HoldEventOut(BaseModel):
    event_id: str
    cause_stated: bool
    disposition: str
    characterization: str
    traceable_to_data: bool


class IRF6DScoresOut(BaseModel):
    """LOGOS IRF-Calc 6D dimension scores."""

    M: float
    A: float
    D: float
    I: float  # noqa: E741
    F: float
    P: float
    composite: float
    passed: bool
    source: str


class HSTA4DScoresOut(BaseModel):
    """HSTA 4D extension scores (Novelty, Consistency, Temporality, Reproducibility)."""

    N: float
    C: float
    T: float
    R: float
    composite: float


class CritiqueResponse(BaseModel):
    precheck: PrecheckOut
    experiment_class: str | None
    experiment_class_secondary: str | None
    experiment_class_reason: str
    steps: list[StepOut]
    priority_fix: str
    next_liability: str | None
    round_number: int
    omega_score: float
    not_traceable_count: int
    partially_traceable_count: int
    evidence_conflicts: list[EvidenceConflictOut]
    hold_events: list[HoldEventOut]
    # ---- LOGOS enrichment (optional)
    irf_scores: IRF6DScoresOut | None = None
    hsta_scores: HSTA4DScoresOut | None = None
    methodology_class: str | None = None
    hypothesis_text: str | None = None
    logos_omega: float | None = None
    hybrid_omega: float | None = None
    # ---- SPAR claim-aware review (optional; requires spar-framework)
    spar_review: dict | None = None
    # ---- Drift tracking (multi-round)
    delta_omega: float | None = None
    drift_level: str | None = None


# ── Review simulation schemas ─────────────────────────────────────────────────


class ReviewSimRequest(BaseModel):
    report_text: str = Field(..., description="Full text of the experimental report")
    reviewers: int = Field(3, ge=2, le=3, description="Number of reviewer personas (2-3)")


class PersonaReviewOut(BaseModel):
    persona: str
    min_omega: float
    base_omega: float
    calibrated_omega: float
    recommendation: str
    irf_dims: dict[str, float]


class ConsensusOut(BaseModel):
    omegas: dict[str, float]
    consensus_omega: float
    variance: float
    spread: float
    reached: bool
    recommendation: str


class DR3Out(BaseModel):
    conflict_detected: bool
    tiebreaker_persona: str
    final_omega: float
    resolution_note: str


class ReviewSimResponse(BaseModel):
    per_reviewer: list[PersonaReviewOut]
    consensus: ConsensusOut
    dr3: DR3Out
    final_omega: float
    final_recommendation: str


# ── Rebuttal schemas (v3.3) ───────────────────────────────────────────────────


class RebuttalRequest(BaseModel):
    report_text: str = Field(..., description="Raw text of the experimental report to rebut")
    style: str = Field("ieee", description="Response letter style: ieee | acm | nature")
    domain: str = Field("biomedical", description="IRF scoring domain: biomedical | cs | math")


class RebuttalItemOut(BaseModel):
    issue_id: str
    category: str
    severity: str
    reviewer_text: str
    author_response_template: str
    addressed: bool


class RebuttalResponse(BaseModel):
    style: str
    generated_at: str
    total_issues: int
    critical_count: int
    high_count: int
    rebuttal_coverage: float
    items: list[RebuttalItemOut]


# ── Journal schemas (v3.3) ────────────────────────────────────────────────────


class JournalProfileOut(BaseModel):
    key: str
    name: str
    accept_omega: float
    revise_omega: float
    step_weights: dict
    description: str
    domain_hint: str = ""


class JournalScoreRequest(BaseModel):
    report_text: str = Field(..., description="Raw text of the experimental report")
    journal: str = Field(
        "default", description="Journal key: nature, ieee, lancet, q1, q2, q3, default"
    )
    domain: str = Field("biomedical", description="IRF scoring domain: biomedical | cs | math")


# ── Domain schemas (v3.4) ──────────────────────────────────────────────────────


class DomainOut(BaseModel):
    """Single registered domain metadata."""

    key: str
    name: str
    composite_threshold: float
    component_min: float
    marker_counts: dict[str, int] = Field(
        description="Number of markers per IRF dimension (M/A/D/I/F/P)"
    )


class StepContributionOut(BaseModel):
    raw: float
    weighted: float
    multiplier: float


class JournalScoreResponse(BaseModel):
    journal_key: str
    journal_name: str
    raw_omega: float
    calibrated_omega: float
    omega_delta: float
    verdict: str
    accept_threshold: float
    revise_threshold: float
    step_contributions: dict[str, StepContributionOut]


class DiffRequest(BaseModel):
    report_v1_text: str = Field(..., description="Original submission text")
    report_v2_text: str = Field(..., description="Revised submission text")


class DiffResponse(BaseModel):
    delta_omega: float
    addressed_count: int
    total_v1_issues: int
    rcs: float
    revision_grade: str
    addressed_codes: list[str]
    remaining_codes: list[str]
    priority_overlap_ratio: float
    improved: bool


# ── Response letter schemas (v3.3) ────────────────────────────────────────────


class ResponseLetterRequest(BaseModel):
    domain: str = Field("biomedical", description="IRF scoring domain: biomedical | cs | math")
    report_text: str = Field(..., description="Raw text of the experimental report")
    style: str = Field("ieee", description="Response letter style: ieee | acm | nature")
    author_name: str = Field("The Authors", description="Author name / signature for closing")


class ResponseLetterResponse(BaseModel):
    style: str
    markdown: str
    total_issues: int
    critical_count: int
    high_count: int
