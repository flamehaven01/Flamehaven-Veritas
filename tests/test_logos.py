"""Tests: LOGOS IRF analyser, methodology detector, hypothesis extractor, omega fusion."""

from __future__ import annotations

import pytest

from veritas.logos.irf_analyzer import IRFAnalyzer
from veritas.logos.omega_fusion import OmegaFusion
from veritas.paper.hypothesis_extractor import HypothesisExtractor
from veritas.paper.methodology_detector import MethodologyDetector
from veritas.types import IRF6DScores, MethodologyClass

# ── Fixtures ──────────────────────────────────────────────────────────────────

RICH_TEXT = """
We hypothesize that the training procedure is reproducible across three seeds.
Based on prior work (Smith et al. 2024, doi:10.1234/abc), the expected baseline
accuracy is 92%. The experiment consists of a randomized ablation study with
a control group and treatment group. Data was measured over 5 iterations.
Results show accuracy improved from 89% to 93% therefore confirming the hypothesis.
However, a key limitation is that we assume consistent hardware configurations.
The method protocol requires step-by-step reproduction with seed=42.
The null hypothesis H0: no significant difference between groups.
This would be falsified if the control group exceeds 94% accuracy.
Reference: prior cycle v2 established the 92% baseline (reference: v2_run_log).
"""

COMPUTATIONAL_TEXT = """
We trained a deep learning model for 100 epochs on the ImageNet dataset.
The algorithm uses a neural network with batch normalization. Benchmark
accuracy on the test set was 89.2% (n=50000). The computational simulation
involved grid search across learning rates. Loss curve converged at epoch 45.
"""

SURVEY_TEXT = """
A survey of 500 respondents was conducted using questionnaire methodology.
Cross-sectional study design was employed. Likert scale responses were
aggregated. Interview data collected from 50 focus group participants.
"""


# ── IRFAnalyzer ───────────────────────────────────────────────────────────────


class TestIRFAnalyzer:
    def test_returns_irf6d_scores(self):
        analyzer = IRFAnalyzer()
        scores = analyzer.score(RICH_TEXT)
        assert isinstance(scores, IRF6DScores)
        assert scores.source == "local"

    def test_all_dimensions_in_range(self):
        analyzer = IRFAnalyzer()
        scores = analyzer.score(RICH_TEXT)
        for dim in [scores.M, scores.A, scores.D, scores.I, scores.F, scores.P]:
            assert 0.0 <= dim <= 1.0, f"Dimension out of range: {dim}"

    def test_composite_in_range(self):
        analyzer = IRFAnalyzer()
        scores = analyzer.score(RICH_TEXT)
        assert 0.0 <= scores.composite <= 1.0

    def test_rich_text_scores_higher_than_empty(self):
        analyzer = IRFAnalyzer()
        rich = analyzer.score(RICH_TEXT)
        empty = analyzer.score("nothing here")
        assert rich.composite > empty.composite

    def test_passed_bool_present(self):
        analyzer = IRFAnalyzer()
        scores = analyzer.score(RICH_TEXT)
        assert isinstance(scores.passed, bool)

    def test_as_dict_keys(self):
        analyzer = IRFAnalyzer()
        d = analyzer.score(RICH_TEXT).as_dict()
        for key in ("M", "A", "D", "I", "F", "P", "composite", "passed", "source"):
            assert key in d


# ── OmegaFusion ───────────────────────────────────────────────────────────────


class TestOmegaFusion:
    def _make_scores(self, **kwargs) -> IRF6DScores:
        defaults = dict(
            M=0.6, A=0.6, D=0.6, I=0.6, F=0.6, P=0.6, composite=0.6, passed=True, source="local"
        )
        defaults.update(kwargs)
        return IRF6DScores(**defaults)

    def test_no_irf_returns_sciexp_omega(self):
        fusion = OmegaFusion()
        result = fusion.fuse(sciexp_omega=0.80, irf_scores=None)
        assert result.hybrid_omega == pytest.approx(0.80, abs=0.001)
        assert not result.f_risk

    def test_hybrid_is_weighted(self):
        fusion = OmegaFusion(w_sciexp=0.6, w_logos=0.4)
        scores = self._make_scores(composite=0.70)
        result = fusion.fuse(sciexp_omega=0.80, irf_scores=scores)
        expected = 0.6 * 0.80 + 0.4 * 0.70
        assert result.hybrid_omega == pytest.approx(expected, abs=0.01)

    def test_f_risk_penalty(self):
        fusion = OmegaFusion()
        scores = self._make_scores(F=0.20, composite=0.55)
        result = fusion.fuse(sciexp_omega=0.75, irf_scores=scores)
        assert result.f_risk
        assert result.f_risk_msg is not None
        # penalty of 0.05 applied
        raw = 0.6 * 0.75 + 0.4 * 0.55
        assert result.hybrid_omega == pytest.approx(raw - 0.05, abs=0.01)

    def test_weights_normalised(self):
        fusion = OmegaFusion(w_sciexp=3.0, w_logos=1.0)
        assert abs(fusion.w_sciexp + fusion.w_logos - 1.0) < 1e-9


# ── MethodologyDetector ───────────────────────────────────────────────────────


class TestMethodologyDetector:
    def test_computational_detected(self):
        det = MethodologyDetector()
        mc, conf = det.detect(COMPUTATIONAL_TEXT)
        assert mc == MethodologyClass.COMPUTATIONAL
        assert conf > 0.0

    def test_survey_detected(self):
        det = MethodologyDetector()
        mc, conf = det.detect(SURVEY_TEXT)
        assert mc == MethodologyClass.SURVEY

    def test_unknown_on_empty(self):
        det = MethodologyDetector()
        mc, conf = det.detect("")
        assert mc == MethodologyClass.UNKNOWN
        assert conf == 0.0

    def test_detect_all_returns_list(self):
        det = MethodologyDetector()
        results = det.detect_all(RICH_TEXT)
        assert isinstance(results, list)


# ── HypothesisExtractor ───────────────────────────────────────────────────────


class TestHypothesisExtractor:
    def test_finds_hypothesis(self):
        ext = HypothesisExtractor()
        result = ext.extract(RICH_TEXT)
        assert result.primary is not None
        assert len(result.primary) > 5

    def test_finds_null_hypothesis(self):
        ext = HypothesisExtractor()
        result = ext.extract(RICH_TEXT)
        assert len(result.null_hypothesis) >= 1

    def test_finds_falsification_criteria(self):
        ext = HypothesisExtractor()
        result = ext.extract(RICH_TEXT)
        assert len(result.falsification_criteria) >= 1

    def test_summary_non_empty(self):
        ext = HypothesisExtractor()
        result = ext.extract(RICH_TEXT)
        summary = result.summary()
        assert len(summary) > 5

    def test_empty_text_graceful(self):
        ext = HypothesisExtractor()
        result = ext.extract("")
        assert result.primary is None
        assert result.hypothesis == []
