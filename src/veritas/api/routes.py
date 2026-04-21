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
    )
