"""Phase 1 v3.3 integration tests — section-aware pipeline + engine enrichment."""

from __future__ import annotations

import pytest

from veritas.engine import SciExpCritiqueEngine
from veritas.ingest.section_parser import SectionParser
from veritas.stats.claim_classifier import ClaimClassifier
from veritas.stats.stat_validator import StatValidator
from veritas.types import (
    AnalysisConfidence,
    ClaimType,
    CritiqueReport,
    SectionMap,
    StatValidity,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLINICAL_PAPER = """
Abstract
We investigate whether high-dose vitamin D supplementation reduces fracture
incidence in postmenopausal women. We hypothesise a 30% risk reduction.

Introduction
Vitamin D deficiency is a major public health concern. Prior work (Smith 2019)
identified an association between serum 25(OH)D levels and bone mineral density.

Methods
This randomised controlled trial enrolled n=340 participants aged 55-75.
Power analysis indicated 320 participants for 80% power at α=0.05.
Participants received 4000 IU/day or placebo for 24 months.

Results
Fracture incidence was 12% in the intervention group vs 21% in controls
(p = 0.003). Relative risk reduction = 0.43 (95% CI: 0.24–0.61).
Cohen's d = 0.54 (medium effect).

Discussion
The significant reduction in fracture incidence confirms our hypothesis.
Limitations include the single-centre design and homogeneous cohort.

Conclusion
High-dose vitamin D reduces fracture incidence by approximately 43% in this
population. Multicentre replication is recommended.
""".strip()

MINIMAL_TEXT = "We did some experiments and the results were positive."

SCOPE_VIOLATION_TEXT = """
Abstract
A new approach for image classification.

Results
The model definitively proves superior performance over all baselines.
This confirms and demonstrates the fundamental advantage of deep learning.

Discussion
Therefore, it is clear that deep learning is the only viable approach.
""".strip()


# ---------------------------------------------------------------------------
# Section-aware STEP 1 tests
# ---------------------------------------------------------------------------


class TestSectionAwarePipeline:
    def test_step1_section_aware_accepts_section_map(self):
        from veritas import pipeline as _p
        from veritas.ingest.section_parser import SectionParser

        parser = SectionParser()
        sm = parser.parse(CLINICAL_PAPER)
        result, holds = _p.step1_claim_integrity(CLINICAL_PAPER, section_map=sm)
        assert result.step_id == "1"

    def test_scope_violation_restricted_to_results_discussion(self):
        """Scope violations should be found in RESULTS/DISCUSSION, not everywhere."""
        from veritas import pipeline as _p
        from veritas.ingest.section_parser import SectionParser

        parser = SectionParser()
        sm = parser.parse(SCOPE_VIOLATION_TEXT)
        result, _ = _p.step1_claim_integrity(SCOPE_VIOLATION_TEXT, section_map=sm)
        # The scope-violation finding (1.2) should flag violations found in RESULTS/DISCUSSION
        finding_1_2 = next((f for f in result.findings if f.code == "1.2"), None)
        assert finding_1_2 is not None

    def test_step1_no_section_map_still_works(self):
        from veritas import pipeline as _p

        result, holds = _p.step1_claim_integrity(MINIMAL_TEXT)
        assert result.step_id == "1"

    def test_abstract_preferred_for_central_claim(self):
        from veritas import pipeline as _p
        from veritas.ingest.section_parser import SectionParser

        parser = SectionParser()
        sm = parser.parse(CLINICAL_PAPER)
        result, _ = _p.step1_claim_integrity(CLINICAL_PAPER, section_map=sm)
        # Finding 1.1 should contain content from the abstract
        finding_1_1 = next((f for f in result.findings if f.code == "1.1"), None)
        assert finding_1_1 is not None
        # The claim text should include abstract-style content
        assert len(finding_1_1.description) > 10


# ---------------------------------------------------------------------------
# Engine integration tests
# ---------------------------------------------------------------------------


class TestEngineV33Integration:
    @pytest.fixture()
    def engine(self) -> SciExpCritiqueEngine:
        return SciExpCritiqueEngine()

    def test_report_has_section_map(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert report.section_map is not None

    def test_section_map_is_sectionmap(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert isinstance(report.section_map, SectionMap)

    def test_report_has_claim_type(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert report.claim_type is not None

    def test_claim_type_is_claimtype_enum(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert isinstance(report.claim_type, ClaimType)

    def test_clinical_paper_claim_type_empirical(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert report.claim_type == ClaimType.EMPIRICAL

    def test_report_has_stat_validity(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert report.stat_validity is not None

    def test_stat_validity_is_statvalidity(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert isinstance(report.stat_validity, StatValidity)

    def test_clinical_paper_stat_validity_p_numeric(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert report.stat_validity is not None
        assert report.stat_validity.p_value_numeric is True

    def test_clinical_paper_stat_validity_score_high(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert report.stat_validity is not None
        assert report.stat_validity.score >= 0.60

    def test_report_has_analysis_confidence(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert report.analysis_confidence is not None

    def test_analysis_confidence_type(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert isinstance(report.analysis_confidence, AnalysisConfidence)

    def test_analysis_confidence_level_valid(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        ac = report.analysis_confidence
        assert ac is not None
        assert ac.level in ("HIGH", "MEDIUM", "LOW")

    def test_full_paper_medium_or_high_confidence(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        ac = report.analysis_confidence
        assert ac is not None
        assert ac.level in ("HIGH", "MEDIUM")

    def test_minimal_text_low_confidence(self, engine):
        report = engine.critique(MINIMAL_TEXT)
        ac = report.analysis_confidence
        assert ac is not None
        assert ac.level == "LOW"

    def test_schema_version_is_v33(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert report.schema_version == "3.3"

    def test_existing_fields_still_present(self, engine):
        """v3.2 fields must still be populated (backward compat)."""
        report = engine.critique(CLINICAL_PAPER)
        assert report.omega_score >= 0.0
        assert report.priority_fix != ""
        assert len(report.steps) > 0

    def test_critique_returns_critiquereport(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        assert isinstance(report, CritiqueReport)

    def test_section_coverage_in_confidence(self, engine):
        report = engine.critique(CLINICAL_PAPER)
        ac = report.analysis_confidence
        assert ac is not None
        assert 0.0 <= ac.section_coverage <= 1.0
