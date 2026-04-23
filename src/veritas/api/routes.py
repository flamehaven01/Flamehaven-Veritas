"""API Routes — /critique, /precheck, /classify, /download."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..engine import SciExpCritiqueEngine, _extract_file_text
from ..ingest.document import SUPPORTED, extract_chunks
from ..rag.retriever import SciExpRetriever
from ..render.docx_renderer import render_docx
from ..render.md_renderer import save_md
from ..render.pdf_renderer import render_pdf
from . import schemas as S

router = APIRouter()
_engine = SciExpCritiqueEngine()

# Temporary output dir
_TMP = Path(tempfile.gettempdir()) / "sciexp_outputs"
_TMP.mkdir(exist_ok=True)


# ── /critique/text ─────────────────────────────────────────────────────────────


@router.post("/critique/text", response_model=S.CritiqueResponse, tags=["critique"])
async def critique_text(req: S.CritiqueRequest):
    """Submit raw text and receive structured VERITAS."""
    report = _engine.critique(req.report_text, round_number=req.round_number)
    return _to_response(report)


# ── /critique/upload ───────────────────────────────────────────────────────────


@router.post("/critique/upload", response_model=S.CritiqueResponse, tags=["critique"])
async def critique_upload(
    file: UploadFile = File(...),  # noqa: B008
    template: str = Form("bmj"),
    round_number: int = Form(1),
):
    """Upload a document (PDF, DOCX, DOC, TXT, MD) and receive critique."""
    suffix = Path(file.filename or "upload.txt").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Supported: {SUPPORTED}")

    # Save upload to temp file
    tmp_path = _TMP / f"{uuid.uuid4().hex}{suffix}"
    tmp_path.write_bytes(await file.read())

    try:
        text = _extract_file_text(tmp_path)
        if not text.strip():
            raise HTTPException(422, "Could not extract text from the uploaded file.")

        # RAG indexing on document itself for context enrichment
        retriever = SciExpRetriever()
        chunks = extract_chunks(tmp_path)
        retriever.index_chunks(chunks)
        ctx = retriever.build_context(text[:500])

        eng = SciExpCritiqueEngine(rag_retriever=retriever)
        report = eng.critique(text, doc_context=ctx, round_number=round_number)
    finally:
        tmp_path.unlink(missing_ok=True)

    return _to_response(report)


# ── /critique/download ─────────────────────────────────────────────────────────


@router.post("/critique/download", tags=["critique"])
async def critique_download(
    file: UploadFile = File(...),  # noqa: B008
    format: str = Form("pdf"),  # pdf | docx | md
    template: str = Form("bmj"),
    round_number: int = Form(1),
):
    """Upload document → receive downloadable critique report in chosen format."""
    suffix = Path(file.filename or "upload.txt").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(400, f"Unsupported file type '{suffix}'.")
    if format not in ("pdf", "docx", "md"):
        raise HTTPException(400, "format must be one of: pdf, docx, md")

    tmp_in = _TMP / f"{uuid.uuid4().hex}{suffix}"
    tmp_in.write_bytes(await file.read())

    out_id = uuid.uuid4().hex
    out_ext = f".{format}"
    out_path = _TMP / f"critique_{out_id}{out_ext}"

    try:
        text = _extract_file_text(tmp_in)
        if not text.strip():
            raise HTTPException(422, "Could not extract text from the uploaded file.")

        retriever = SciExpRetriever()
        chunks = extract_chunks(tmp_in)
        retriever.index_chunks(chunks)
        ctx = retriever.build_context(text[:500])

        eng = SciExpCritiqueEngine(rag_retriever=retriever)
        report = eng.critique(text, doc_context=ctx, round_number=round_number)

        if format == "md":
            save_md(report, out_path, template_id=template)
            media_type = "text/markdown"
        elif format == "docx":
            render_docx(report, out_path, template_id=template)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            render_pdf(report, out_path, template_id=template)
            media_type = "application/pdf"
    finally:
        tmp_in.unlink(missing_ok=True)

    return FileResponse(
        str(out_path),
        media_type=media_type,
        filename=f"veritas{out_ext}",
        background=None,
    )


# ── /precheck ──────────────────────────────────────────────────────────────────


@router.post("/precheck", response_model=S.PrecheckOut, tags=["critique"])
async def precheck_only(req: S.CritiqueRequest):
    from .. import precheck as _pc

    result = _pc.run(req.report_text)
    return S.PrecheckOut(
        mode=result.mode.value,
        missing_artifacts=result.missing_artifacts,
        line1=result.line1,
        line2=result.line2,
    )


# ── /rebuttal (v3.3) ───────────────────────────────────────────────────────────


@router.post("/rebuttal", response_model=S.RebuttalResponse, tags=["rebuttal"])
async def generate_rebuttal(req: S.RebuttalRequest):
    """Submit report text → receive structured rebuttal with author-response templates.

    Runs full critique pipeline then maps findings to point-by-point RebuttalItems.
    """
    from ..rebuttal.rebuttal_engine import RebuttalEngine

    if req.style not in ("ieee", "acm", "nature"):
        raise HTTPException(400, "style must be one of: ieee, acm, nature")

    report = _engine.critique(req.report_text)

    rb_engine = RebuttalEngine()
    rb_report = rb_engine.generate(report, style=req.style)

    return S.RebuttalResponse(
        style=rb_report.style,
        generated_at=rb_report.generated_at,
        total_issues=len(rb_report.items),
        critical_count=rb_report.critical_count,
        high_count=rb_report.high_count,
        rebuttal_coverage=round(rb_report.rebuttal_coverage, 4),
        items=[
            S.RebuttalItemOut(
                issue_id=item.issue_id,
                category=item.category,
                severity=item.severity,
                reviewer_text=item.reviewer_text,
                author_response_template=item.author_response_template,
                addressed=item.addressed,
            )
            for item in rb_report.items
        ],
    )


@router.post("/rebuttal-upload", response_model=S.RebuttalResponse, tags=["rebuttal"])
async def generate_rebuttal_upload(
    file: UploadFile = File(...),  # noqa: B008
    style: str = Form("ieee"),
):
    """Upload a document → receive structured rebuttal. Convenience alias of /rebuttal."""
    from ..rebuttal.rebuttal_engine import RebuttalEngine

    if style not in ("ieee", "acm", "nature"):
        raise HTTPException(400, "style must be one of: ieee, acm, nature")

    suffix = Path(file.filename or "upload.txt").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(400, f"Unsupported file type '{suffix}'.")

    tmp_path = _TMP / f"{uuid.uuid4().hex}{suffix}"
    tmp_path.write_bytes(await file.read())

    try:
        text = _extract_file_text(tmp_path)
        if not text.strip():
            raise HTTPException(422, "Could not extract text from the uploaded file.")
        report = _engine.critique(text)
    finally:
        tmp_path.unlink(missing_ok=True)

    rb_engine = RebuttalEngine()
    rb_report = rb_engine.generate(report, style=style)

    return S.RebuttalResponse(
        style=rb_report.style,
        generated_at=rb_report.generated_at,
        total_issues=len(rb_report.items),
        critical_count=rb_report.critical_count,
        high_count=rb_report.high_count,
        rebuttal_coverage=round(rb_report.rebuttal_coverage, 4),
        items=[
            S.RebuttalItemOut(
                issue_id=item.issue_id,
                category=item.category,
                severity=item.severity,
                reviewer_text=item.reviewer_text,
                author_response_template=item.author_response_template,
                addressed=item.addressed,
            )
            for item in rb_report.items
        ],
    )


# ── /journal-profiles (v3.3) ──────────────────────────────────────────────────


@router.get("/journal-profiles", response_model=list[S.JournalProfileOut], tags=["journal"])
async def list_journal_profiles():
    """Return all built-in journal profiles with acceptance thresholds."""
    from ..journal.journal_profiles import JOURNAL_PROFILES

    return [S.JournalProfileOut(**profile.as_dict()) for profile in JOURNAL_PROFILES.values()]


# ── /journal-score (v3.3) ─────────────────────────────────────────────────────


@router.post("/journal-score", response_model=S.JournalScoreResponse, tags=["journal"])
async def journal_score(req: S.JournalScoreRequest):
    """Critique a report and return journal-calibrated omega + verdict."""
    from ..journal.journal_scorer import JournalScorer

    try:
        report = _engine.critique(req.report_text)
        scorer = JournalScorer()
        result = scorer.score(report, journal=req.journal)
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc

    return S.JournalScoreResponse(
        journal_key=result.journal_key,
        journal_name=result.journal_name,
        raw_omega=round(result.raw_omega, 4),
        calibrated_omega=round(result.calibrated_omega, 4),
        omega_delta=round(result.omega_delta, 4),
        verdict=result.verdict.value,
        accept_threshold=result.accept_threshold,
        revise_threshold=result.revise_threshold,
        step_contributions={
            k: S.StepContributionOut(**v)
            for k, v in result.step_contributions.items()
        },
    )


@router.post("/journal-score-upload", response_model=S.JournalScoreResponse, tags=["journal"])
async def journal_score_upload(
    file: UploadFile = File(...),  # noqa: B008
    journal: str = Form("default"),
):
    """Upload a document → journal-calibrated omega + verdict. Convenience alias."""
    from ..journal.journal_scorer import JournalScorer

    suffix = Path(file.filename or "upload.txt").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(400, f"Unsupported file type '{suffix}'.")

    tmp_path = _TMP / f"{uuid.uuid4().hex}{suffix}"
    tmp_path.write_bytes(await file.read())

    try:
        text = _extract_file_text(tmp_path)
        if not text.strip():
            raise HTTPException(422, "Could not extract text from the uploaded file.")
        report = _engine.critique(text)
        scorer = JournalScorer()
        result = scorer.score(report, journal=journal)
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return S.JournalScoreResponse(
        journal_key=result.journal_key,
        journal_name=result.journal_name,
        raw_omega=round(result.raw_omega, 4),
        calibrated_omega=round(result.calibrated_omega, 4),
        omega_delta=round(result.omega_delta, 4),
        verdict=result.verdict.value,
        accept_threshold=result.accept_threshold,
        revise_threshold=result.revise_threshold,
        step_contributions={
            k: S.StepContributionOut(**v)
            for k, v in result.step_contributions.items()
        },
    )


# ── /diff (v3.3) ──────────────────────────────────────────────────────────────


@router.post("/diff", response_model=S.DiffResponse, tags=["rebuttal"])
async def revision_diff(req: S.DiffRequest):
    """Compare two report versions and return Revision Completeness Score."""
    from ..rebuttal.revision_tracker import RevisionTracker

    r1 = _engine.critique(req.report_v1_text)
    r2 = _engine.critique(req.report_v2_text)
    tracker = RevisionTracker()
    result = tracker.compare(r1, r2)

    return S.DiffResponse(
        delta_omega=round(result.delta_omega, 4),
        addressed_count=result.addressed_count,
        total_v1_issues=result.total_v1_issues,
        rcs=round(result.rcs, 4),
        revision_grade=result.revision_grade.value,
        addressed_codes=result.addressed_codes,
        remaining_codes=result.remaining_codes,
        priority_overlap_ratio=round(result.priority_overlap_ratio, 4),
        improved=result.improved,
    )


# ── /response-letter (v3.3) ───────────────────────────────────────────────────


@router.post("/response-letter", response_model=S.ResponseLetterResponse, tags=["rebuttal"])
async def generate_response_letter(req: S.ResponseLetterRequest):
    """Generate a formal IEEE/ACM/Nature response letter from report text."""
    from ..rebuttal.rebuttal_engine import RebuttalEngine
    from ..render.response_letter import ResponseLetterRenderer

    if req.style not in ("ieee", "acm", "nature"):
        raise HTTPException(400, "style must be one of: ieee, acm, nature")

    report = _engine.critique(req.report_text)
    rb_engine = RebuttalEngine()
    rb_report = rb_engine.generate(report, style=req.style)

    renderer = ResponseLetterRenderer()
    md = renderer.render(rb_report, style=req.style)

    return S.ResponseLetterResponse(
        style=rb_report.style,
        markdown=md,
        total_issues=len(rb_report.items),
        critical_count=rb_report.critical_count,
        high_count=rb_report.high_count,
    )


# ── helpers ────────────────────────────────────────────────────────────────────


def _to_response(report) -> S.CritiqueResponse:
    # Serialize HSTA 4D
    hsta_out = None
    if report.hsta_scores is not None:
        h = report.hsta_scores
        hsta_out = S.HSTA4DScoresOut(
            N=h.N,
            C=h.C,
            T=h.T,
            R=h.R,
            composite=round(h.composite, 4),
        )

    return S.CritiqueResponse(
        precheck=S.PrecheckOut(
            mode=report.precheck.mode.value,
            missing_artifacts=report.precheck.missing_artifacts,
            line1=report.precheck.line1,
            line2=report.precheck.line2,
        ),
        experiment_class=report.experiment_class.value if report.experiment_class else None,
        experiment_class_secondary=(
            report.experiment_class_secondary.value if report.experiment_class_secondary else None
        ),
        experiment_class_reason=report.experiment_class_reason,
        steps=[
            S.StepOut(
                step_id=s.step_id,
                weight=s.weight,
                prose=s.prose,
                findings=[
                    S.FindingOut(
                        code=f.code,
                        description=f.description,
                        traceability=f.traceability.value,
                        verbatim_quote=f.verbatim_quote,
                    )
                    for f in s.findings
                ],
                vulnerable_claim=s.vulnerable_claim,
                not_applicable=s.not_applicable,
            )
            for s in report.steps
        ],
        priority_fix=report.priority_fix,
        next_liability=report.next_liability,
        round_number=report.round_number,
        omega_score=report.omega_score,
        not_traceable_count=report.not_traceable_count(),
        partially_traceable_count=report.partially_traceable_count(),
        evidence_conflicts=[
            S.EvidenceConflictOut(
                rank=ec.rank.name,
                artifact_a=ec.artifact_a,
                artifact_b=ec.artifact_b,
                description=ec.description,
            )
            for ec in report.evidence_conflicts
        ],
        hold_events=[
            S.HoldEventOut(
                event_id=h.event_id,
                cause_stated=h.cause_stated,
                disposition=h.disposition.value,
                characterization=h.characterization,
                traceable_to_data=h.traceable_to_data,
            )
            for h in report.hold_events
        ],
        irf_scores=(
            S.IRF6DScoresOut(**report.irf_scores.as_dict())
            if report.irf_scores is not None
            else None
        ),
        hsta_scores=hsta_out,
        methodology_class=(
            report.methodology_class.value if report.methodology_class is not None else None
        ),
        hypothesis_text=report.hypothesis_text,
        logos_omega=report.logos_omega,
        hybrid_omega=report.hybrid_omega,
        spar_review=report.spar_review,
        delta_omega=getattr(report, "delta_omega", None),
        drift_level=getattr(report, "drift_level", None),
    )


# ── /review-sim ────────────────────────────────────────────────────────────────


@router.post("/review-sim", response_model=S.ReviewSimResponse, tags=["review-sim"])
async def review_sim(req: S.ReviewSimRequest) -> S.ReviewSimResponse:
    """Run multi-persona peer-review simulation on report text.

    Args:
        req.report_text: Full text of the experimental report.
        req.reviewers: 2 or 3 reviewer personas (STRICT/BALANCED/[LENIENT]).

    Returns:
        Per-reviewer calibrated scores, consensus result, DR3 resolution.
    """
    from ..reviewer.engine import ReviewSimEngine

    engine = ReviewSimEngine()
    result = engine.run(req.report_text, reviewers=req.reviewers)

    consensus_out = S.ConsensusOut(
        omegas=result.consensus.omegas,
        consensus_omega=result.consensus.consensus_omega,
        variance=result.consensus.variance,
        spread=result.consensus.spread,
        reached=result.consensus.reached,
        recommendation=result.consensus.recommendation,
    )
    dr3_out = S.DR3Out(
        conflict_detected=result.dr3.conflict_detected,
        tiebreaker_persona=result.dr3.tiebreaker_persona,
        final_omega=result.dr3.final_omega,
        resolution_note=result.dr3.resolution_note,
    )
    return S.ReviewSimResponse(
        per_reviewer=[
            S.PersonaReviewOut(
                persona=r.persona,
                min_omega=r.min_omega,
                base_omega=r.base_omega,
                calibrated_omega=r.calibrated_omega,
                recommendation=r.recommendation,
                irf_dims=r.irf_dims,
            )
            for r in result.per_reviewer
        ],
        consensus=consensus_out,
        dr3=dr3_out,
        final_omega=result.final_omega,
        final_recommendation=result.final_recommendation,
    )
