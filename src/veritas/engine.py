"""VERITAS — AI Critique Experimental Report Analysis Framework — Main Engine Orchestrator.

Wires PRECHECK → RAG ingestion → STEP 0-5 pipeline → LOGOS IRF reasoning
→ methodology / hypothesis intelligence → report rendering.
"""

from __future__ import annotations

from pathlib import Path

from . import pipeline as _pipeline
from . import precheck as _precheck
from .evidence import extract_evidence, resolve
from .ingest.section_parser import SectionParser
from .stats.claim_classifier import ClaimClassifier
from .stats.stat_validator import StatValidator
from .types import (
    AnalysisConfidence,
    CritiqueReport,
    PrecheckResult,
    SciExpMode,
    StepResult,
)


class SciExpCritiqueEngine:
    """Orchestrates the full VERITAS — AI Critique Experimental Report Analysis Framework pipeline.

    Usage (standalone — no RAG)::

        engine = SciExpCritiqueEngine()
        report = engine.critique(report_text)

    Usage (with RAG context from uploaded document)::

        engine = SciExpCritiqueEngine(rag_retriever=retriever)
        report = engine.critique(report_text, doc_context=context_chunks)
    """

    def __init__(self, rag_retriever=None, domain: str = "biomedical") -> None:
        self._rag = rag_retriever
        self._domain = domain
        self._logos = _try_init_component(".logos.logos_bridge", "LogosBridge")
        self._fusion = _try_init_component(".logos.omega_fusion", "OmegaFusion")
        self._method_det = _try_init_component(".paper.methodology_detector", "MethodologyDetector")
        self._hypo_ext = _try_init_component(".paper.hypothesis_extractor", "HypothesisExtractor")
        self._biblio = _try_init_component(".paper.bibliography_analyzer", "BibliographyAnalyzer")
        self._repro = _try_init_component(
            ".paper.reproducibility_checklist", "ReproducibilityChecklistExtractor"
        )
        # v3.3 — always-available, zero-dependency components
        self._section_parser = SectionParser()
        self._claim_classifier = ClaimClassifier()
        self._stat_validator = StatValidator()

    def critique(
        self,
        report_text: str,
        doc_context: str | None = None,
        round_number: int = 1,
        prev_report: CritiqueReport | None = None,
    ) -> CritiqueReport:
        """Execute full critique pipeline. Returns CritiqueReport."""
        text = (doc_context + "\n\n" + report_text) if doc_context else report_text

        # ── v3.3 early — parse structure, classify, compute confidence
        #    Run BEFORE BLOCKED check so all fields are always populated.
        section_map = self._section_parser.parse(text)
        # Use full text (not just abstract) — abstract rarely contains empirical markers
        claim_type = self._claim_classifier.classify(text)
        stat_validity = self._stat_validator.validate(text, section_map)
        analysis_confidence = self._compute_analysis_confidence(text, section_map)

        # ── PRECHECK
        pc = _precheck.run(text)
        if pc.mode == SciExpMode.BLOCKED:
            exp_class, exp_secondary, exp_reason = _pipeline.step0_classify(text)
            step0 = StepResult(
                step_id="0",
                weight=0.0,
                prose=f"BLOCKED — {pc.line2}. Class best-guess: {exp_class.value}.",
            )
            return CritiqueReport(
                precheck=pc,
                experiment_class=exp_class,
                experiment_class_secondary=exp_secondary,
                experiment_class_reason=exp_reason,
                steps=[step0],
                priority_fix=(
                    "Report is BLOCKED: no evaluable claim found. "
                    "Supply required artifacts before re-submitting."
                ),
                round_number=round_number,
                section_map=section_map,
                claim_type=claim_type,
                stat_validity=stat_validity,
                analysis_confidence=analysis_confidence,
            )

        # ── STEP 0
        exp_class, exp_secondary, exp_reason = _pipeline.step0_classify(text)
        step0 = StepResult(
            step_id="0",
            weight=0.0,
            prose=(
                f"Experiment class: {exp_class.value}. {exp_reason}"
                + (f" Secondary class: {exp_secondary.value}." if exp_secondary else "")
            ),
        )

        # ── Evidence resolution
        ev_items = extract_evidence(text)
        ev_result = resolve(ev_items)

        # ── STEP 1-4 (section-aware)
        res_claim, holds = _pipeline.step1_claim_integrity(text, section_map)
        res_trace = _pipeline.step2_traceability(text, holds)
        res_series = _pipeline.step3_series_continuity(text)
        res_pub = _pipeline.step4_publication_readiness(text)

        # ── STEP 5
        fix, next_l = _pipeline.step5_priority_fix(res_claim, res_trace, res_series, res_pub)
        step5 = StepResult(
            step_id="5",
            weight=0.0,
            prose=fix + (f" OPTIONAL — NEXT LIABILITY: {next_l}" if next_l else ""),
        )

        sciexp_omega = self._compute_omega(pc, [res_claim, res_trace, res_series, res_pub])

        # ── LOGOS IRF enrichment (optional; fails silently)
        irf_scores, methodology_class, hypothesis_text, logos_omega, hybrid_omega = (
            self._enrich_logos(text, res_claim, stat_validity=stat_validity)
        )

        # ── HSTA 4D (optional)
        hsta_scores = self._compute_hsta(text)

        # ── Bibliography analysis (optional)
        bibliography_stats = self._compute_bibliography(text)

        # ── Reproducibility checklist (optional)
        reproducibility_checklist = self._compute_repro(text)

        # Prefer hybrid_omega if computed; otherwise use sciexp_omega
        final_omega = hybrid_omega if hybrid_omega is not None else sciexp_omega

        # ── Multi-round drift computation (v2.3.0)
        delta_omega = None
        drift_metrics_dict = None
        jsd_penalized_omega = None
        if (
            prev_report is not None
            and irf_scores is not None
            and prev_report.irf_scores is not None
        ):
            from .logos.drift_engine import DriftEngine

            _de = DriftEngine()
            _dm = _de.compute_round_drift(
                irf_scores,
                prev_report.irf_scores,
                round_from=prev_report.round_number,
                round_to=round_number,
            )
            delta_omega = _dm.delta_omega
            drift_metrics_dict = _dm.as_dict()
            jsd_penalized_omega = _de.apply_penalty(final_omega, _dm.jsd)

        report = CritiqueReport(
            precheck=pc,
            experiment_class=exp_class,
            experiment_class_secondary=exp_secondary,
            experiment_class_reason=exp_reason,
            steps=[step0, res_claim, res_trace, res_series, res_pub, step5],
            priority_fix=fix,
            next_liability=next_l,
            round_number=round_number,
            omega_score=final_omega,
            evidence_conflicts=ev_result.conflicts,
            hold_events=holds,
            irf_scores=irf_scores,
            hsta_scores=hsta_scores,
            methodology_class=methodology_class,
            hypothesis_text=hypothesis_text,
            logos_omega=logos_omega,
            hybrid_omega=hybrid_omega,
            bibliography_stats=bibliography_stats,
            reproducibility_checklist=reproducibility_checklist,
            delta_omega=delta_omega,
            drift_metrics=drift_metrics_dict,
            jsd_penalized_omega=jsd_penalized_omega,
            # v3.3
            section_map=section_map,
            claim_type=claim_type,
            stat_validity=stat_validity,
            analysis_confidence=analysis_confidence,
        )

        # ── SPAR claim-aware review (post-build; needs complete report as subject)
        report.spar_review = self._compute_spar(report, text)
        return report

    def critique_from_file(
        self,
        file_path: str | Path,
        round_number: int = 1,
        prev_report: CritiqueReport | None = None,
    ) -> CritiqueReport:
        """Parse a file and critique its content.

        Supported: .pdf, .docx, .doc, .txt, .md
        """
        text = _extract_file_text(Path(file_path))
        ctx = self._rag_context(text) if self._rag else None
        return self.critique(
            text, doc_context=ctx, round_number=round_number, prev_report=prev_report
        )

    # ── private helpers ────────────────────────────────────────────────────────

    def _rag_context(self, text: str) -> str | None:
        if self._rag is None:
            return None
        try:
            return self._rag.build_context(text)
        except Exception:
            return None

    def _enrich_logos(self, text: str, claim_step, stat_validity=None) -> tuple:
        """Run LOGOS IRF, methodology detection, hypothesis extraction.

        Returns (irf_scores, methodology_class, hypothesis_text, logos_omega, hybrid_omega).
        All values may be None if enrichment is unavailable.
        """
        try:
            # Hypothesis extraction — use primary as central claim
            hypo_result = self._hypo_ext.extract(text) if self._hypo_ext else None
            hypothesis_text = hypo_result.primary if hypo_result else None
            _central_claim = (
                hypothesis_text
                or (claim_step.vulnerable_claim if claim_step else None)
                or text[:200]
            )

            # IRF scoring — pass stat_validity for F-dimension blending (v3.3)
            irf_scores = None
            if self._logos is not None:
                from .logos.irf_analyzer import IRFAnalyzer

                _irf = IRFAnalyzer(domain=self._domain)
                irf_scores = _irf.score(text, stat_validity=stat_validity)

            # Methodology detection
            methodology_class = None
            if self._method_det is not None:
                mc, _conf = self._method_det.detect(text)
                methodology_class = mc

            # Omega fusion
            logos_omega = irf_scores.composite if irf_scores else None
            hybrid_omega = None
            if self._fusion is not None and irf_scores is not None:
                sciexp_omega = self._compute_omega(
                    _precheck.run(text),
                    [s for s in [claim_step] if s is not None],
                )
                fusion_result = self._fusion.fuse(sciexp_omega, irf_scores)
                hybrid_omega = fusion_result.hybrid_omega

            return irf_scores, methodology_class, hypothesis_text, logos_omega, hybrid_omega

        except Exception:
            return None, None, None, None, None

    def _compute_hsta(self, text: str):
        """Compute HSTA 4D scores from text heuristics."""
        try:
            import re as _re

            from .types import HSTA4DScores

            t = text.lower()
            # N: Novelty — ratio of rare/unique technical terms
            words = set(_re.findall(r"\b[a-z]{5,}\b", t))
            common = {
                "the",
                "and",
                "that",
                "this",
                "with",
                "from",
                "have",
                "been",
                "were",
                "their",
                "which",
                "there",
            }
            novel_terms = words - common
            N = min(len(novel_terms) / 60, 1.0)
            # C: Consistency — low contradiction marker count = high consistency
            contradictions = sum(
                1
                for m in ["contradict", "inconsist", "however", "despite", "conflict", "discrepan"]
                if m in t
            )
            C = max(0.0, 1.0 - contradictions * 0.12)
            # T: Temporality — presence of version/date markers
            temporal = sum(
                1
                for m in [
                    "v1.",
                    "v2.",
                    "v3.",
                    "cycle",
                    "iteration",
                    "round",
                    "2024",
                    "2025",
                    "2026",
                ]
                if m in t
            )
            T = min(temporal / 4, 1.0)
            # R: Reproducibility — method detail completeness
            repro = sum(
                1
                for m in [
                    "protocol",
                    "step-by-step",
                    "method",
                    "procedure",
                    "config",
                    "parameter",
                    "seed",
                    "reproducib",
                ]
                if m in t
            )
            R = min(repro / 4, 1.0)
            return HSTA4DScores(N=round(N, 4), C=round(C, 4), T=round(T, 4), R=round(R, 4))
        except Exception:
            return None

    def _compute_bibliography(self, text: str):
        """Run BibliographyAnalyzer; returns BibliographyStats or None."""
        if self._biblio is None:
            return None
        try:
            return self._biblio.analyze(text)
        except Exception:
            return None

    def _compute_repro(self, text: str):
        """Run ReproducibilityChecklistExtractor; returns ReproducibilityChecklist or None."""
        if self._repro is None:
            return None
        try:
            return self._repro.extract(text)
        except Exception:
            return None

    def _compute_spar(self, report: CritiqueReport, report_text: str) -> dict | None:
        """Run SPAR claim-aware review on the completed CritiqueReport.

        Requires spar-framework installed.  Returns dict (ReviewResult.to_dict()) or None.
        """
        try:
            from spar_framework.engine import run_review  # type: ignore[import]

            from .spar_bridge.runtime import get_review_runtime
            from .spar_bridge.subject_mapper import report_to_subject

            runtime = get_review_runtime()
            subject = report_to_subject(report)
            result = run_review(
                runtime=runtime,
                subject=subject,
                source="sciexp",
                gate="ACCEPT" if report.omega_score >= 0.70 else "REVISION",
                report_text=report_text,
            )
            return result.to_dict()
        except Exception:
            return None

    @staticmethod
    def _compute_analysis_confidence(text: str, section_map) -> AnalysisConfidence:
        """Derive meta-uncertainty signal from document structure."""
        from .types import SectionMap

        sm: SectionMap = section_map
        coverage = sm.coverage if sm is not None else 0.0
        import re as _re

        artifact_count = len(_re.findall(r"\b[0-9a-fA-F]{64}\b", text))
        artifact_count += len(_re.findall(r"source_path\s*[:=]\s*\S+", text, _re.I))
        text_length = len(text)

        if coverage >= 0.70 and artifact_count >= 5:
            level = "HIGH"
            reason = "Strong section coverage and multiple traceable artifacts."
        elif coverage >= 0.40 or artifact_count >= 2:
            level = "MEDIUM"
            reason = f"Partial section coverage ({coverage:.0%}) or limited artifacts ({artifact_count})."
        else:
            level = "LOW"
            reason = (
                f"Sparse document: coverage={coverage:.0%}, artifacts={artifact_count}, "
                f"chars={text_length}."
            )

        return AnalysisConfidence(
            level=level,
            artifact_count=artifact_count,
            text_length=text_length,
            section_coverage=round(coverage, 4),
            reason=reason,
        )

    @staticmethod
    def _compute_omega(pc: PrecheckResult, steps: list[StepResult]) -> float:
        if pc.mode == SciExpMode.BLOCKED:
            return 0.0
        from .types import TraceabilityClass

        total = sum(len(s.findings) for s in steps)
        if total == 0:
            return 1.0
        traceable = sum(
            1 for s in steps for f in s.findings if f.traceability == TraceabilityClass.TRACEABLE
        )
        base = traceable / total
        mode_penalty = {
            SciExpMode.FULL: 0.0,
            SciExpMode.PARTIAL: 0.05,
            SciExpMode.LIMITED: 0.15,
        }.get(pc.mode, 0.0)
        return round(max(0.0, min(1.0, base - mode_penalty)), 4)


# ── Optional-component factory ─────────────────────────────────────────────


def _try_init_component(module_path: str, class_name: str):
    """Import and instantiate an optional component; return None on any failure.

    Silent failure is by design — LOGOS / BPH enrichment is always opt-in.
    """
    import importlib

    try:
        mod = importlib.import_module(module_path, package="veritas")
        return getattr(mod, class_name)()
    except Exception:  # optional dep unavailable — degrade silently
        return None


def _extract_file_text(path: Path) -> str:
    """Extract text from file — wraps Flamehaven-Filesearch when available."""
    try:
        import sys

        sys.path.insert(0, r"D:\Sanctum\Flamehaven-Filesearch")
        from flamehaven_filesearch.engine.file_parser import extract_text

        return extract_text(str(path))
    except Exception:
        pass  # flamehaven_filesearch unavailable; fall through to local extraction

    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".text"}:
        return path.read_text(encoding="utf-8", errors="replace")

    try:
        import fitz  # pymupdf

        doc = fitz.open(str(path))
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        pass  # pymupdf unavailable; try next extractor

    try:
        from docx import Document

        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        pass  # python-docx unavailable; fall through to raw read

    return path.read_text(encoding="utf-8", errors="replace")
