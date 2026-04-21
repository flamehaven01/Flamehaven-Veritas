"""API Schemas — Pydantic v2 request/response models."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CritiqueRequest(BaseModel):
    report_text:  str = Field(..., description="Raw text of the experimental report")
    template:     str = Field("bmj", description="Output template: 'bmj' or 'ku'")
    round_number: int = Field(1, ge=1, description="Critique round number")


class FindingOut(BaseModel):
    code:           str
    description:    str
    traceability:   str
    verbatim_quote: str | None = None


class StepOut(BaseModel):
    step_id:          str
    weight:           float
    prose:            str
    findings:         list[FindingOut]
    vulnerable_claim: str | None = None
    not_applicable:   bool = False


class PrecheckOut(BaseModel):
    mode:              str
    missing_artifacts: list[str]
    line1:             str
    line2:             str


class EvidenceConflictOut(BaseModel):
    rank:        str
    artifact_a:  str
    artifact_b:  str
    description: str


class HoldEventOut(BaseModel):
    event_id:          str
    cause_stated:      bool
    disposition:       str
    characterization:  str
    traceable_to_data: bool


class IRF6DScoresOut(BaseModel):
    """LOGOS IRF-Calc 6D dimension scores."""
    M:         float
    A:         float
    D:         float
    I:         float  # noqa: E741
    F:         float
    P:         float
    composite: float
    passed:    bool
    source:    str


class HSTA4DScoresOut(BaseModel):
    """HSTA 4D extension scores (Novelty, Consistency, Temporality, Reproducibility)."""
    N: float
    C: float
    T: float
    R: float
    composite: float


class CritiqueResponse(BaseModel):
    precheck:                    PrecheckOut
    experiment_class:            str | None
    experiment_class_secondary:  str | None
    experiment_class_reason:     str
    steps:                       list[StepOut]
    priority_fix:                str
    next_liability:              str | None
    round_number:                int
    omega_score:                 float
    not_traceable_count:         int
    partially_traceable_count:   int
    evidence_conflicts:          list[EvidenceConflictOut]
    hold_events:                 list[HoldEventOut]
    # ---- LOGOS enrichment (optional)
    irf_scores:        IRF6DScoresOut | None  = None
    hsta_scores:       HSTA4DScoresOut | None = None
    methodology_class: str | None             = None
    hypothesis_text:   str | None             = None
    logos_omega:       float | None           = None
    hybrid_omega:      float | None           = None
    # ---- SPAR claim-aware review (optional; requires spar-framework)
    spar_review:       dict | None            = None
