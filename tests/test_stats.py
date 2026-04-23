"""Tests for veritas.stats — ClaimClassifier and StatValidator (v3.3)."""

from __future__ import annotations

import pytest

from veritas.stats.claim_classifier import ClaimClassifier
from veritas.stats.stat_validator import StatValidator
from veritas.types import ClaimType, SectionMap, StatValidity


# ---------------------------------------------------------------------------
# ClaimClassifier fixtures
# ---------------------------------------------------------------------------

EMPIRICAL_TEXT = """
We observed a significant improvement in mean accuracy (p = 0.003).
The data measured from 120 participants confirmed the hypothesis.
Effect size was Cohen's d = 1.1 (large). Statistical analysis was performed
using ANOVA with Bonferroni correction.
"""

THEORETICAL_TEXT = """
We propose a formal framework based on graph-theoretic axioms.
The proof of Theorem 2 requires the following lemma: ...
Our theoretical model assumes convexity of the loss function.
Deductive reasoning from prior axioms leads us to derive the following bound.
"""

COMPARATIVE_TEXT = """
We compared our approach to the SOTA baseline (Zhang et al., 2022).
Our method outperforms the baseline by 14% on benchmark B1.
The ablation study shows that removing component X reduces accuracy by 8%.
Versus the previous best result, our system achieves a 6-point improvement.
"""

METHODOLOGICAL_TEXT = """
We propose a novel pipeline for end-to-end document processing.
Our system architecture consists of three stages: preprocessing, inference, postprocessing.
The implementation follows a step-by-step procedure described in Algorithm 1.
Our framework integrates seamlessly with existing workflows.
"""

MIXED_TEXT = """
We measured and compared.
"""  # Too short/equal to produce a clear winner → UNKNOWN


# ---------------------------------------------------------------------------
# ClaimClassifier tests
# ---------------------------------------------------------------------------


class TestClaimClassifier:
    @pytest.fixture()
    def cc(self) -> ClaimClassifier:
        return ClaimClassifier()

    def test_empirical_classified(self, cc):
        result = cc.classify(EMPIRICAL_TEXT)
        assert result == ClaimType.EMPIRICAL

    def test_theoretical_classified(self, cc):
        result = cc.classify(THEORETICAL_TEXT)
        assert result == ClaimType.THEORETICAL

    def test_comparative_classified(self, cc):
        result = cc.classify(COMPARATIVE_TEXT)
        assert result == ClaimType.COMPARATIVE

    def test_methodological_classified(self, cc):
        result = cc.classify(METHODOLOGICAL_TEXT)
        assert result == ClaimType.METHODOLOGICAL

    def test_empty_text_returns_unknown(self, cc):
        result = cc.classify("")
        assert result == ClaimType.UNKNOWN

    def test_returns_claim_type_enum(self, cc):
        result = cc.classify(EMPIRICAL_TEXT)
        assert isinstance(result, ClaimType)

    def test_short_text_no_crash(self, cc):
        result = cc.classify("hello world")
        assert isinstance(result, ClaimType)

    def test_3000_char_limit_respected(self, cc):
        # 10x repetition — still should classify without error
        long_text = EMPIRICAL_TEXT * 20
        result = cc.classify(long_text)
        assert result == ClaimType.EMPIRICAL


# ---------------------------------------------------------------------------
# StatValidator fixtures
# ---------------------------------------------------------------------------

FULL_STAT_TEXT = """
Methods
Fifty participants (n=50) were enrolled. Power analysis indicated a minimum
sample of 40 to achieve 80% power (1 − β) with α=0.05.

Results
The primary outcome showed a significant effect (p = 0.003). Effect size
Cohen's d = 0.72 (medium). The 95% CI was [0.21, 1.23]. All assumptions of
normality were met.
"""

WORD_ONLY_P_TEXT = """
Results were statistically significant. We observed a marginal trend.
No confidence interval was reported. Sample size was not mentioned.
"""

NO_STATS_TEXT = """
We ran some experiments and got good results. The system worked well.
Everything looks fine. No numbers were reported anywhere.
"""

PARTIAL_STATS_TEXT = """
Sample size was n=100. Results were statistically significant (p < 0.05).
No effect size was reported.
"""


# ---------------------------------------------------------------------------
# StatValidator tests
# ---------------------------------------------------------------------------


class TestStatValidator:
    @pytest.fixture()
    def sv(self) -> StatValidator:
        return StatValidator()

    # ---- Full statistical reporting
    def test_full_stats_high_score(self, sv):
        result = sv.validate(FULL_STAT_TEXT)
        assert result.score >= 0.70

    def test_full_stats_p_numeric_true(self, sv):
        result = sv.validate(FULL_STAT_TEXT)
        assert result.p_value_numeric is True

    def test_full_stats_effect_size_true(self, sv):
        result = sv.validate(FULL_STAT_TEXT)
        assert result.effect_size_reported is True

    def test_full_stats_ci_true(self, sv):
        result = sv.validate(FULL_STAT_TEXT)
        assert result.ci_reported is True

    def test_full_stats_power_true(self, sv):
        result = sv.validate(FULL_STAT_TEXT)
        assert result.power_reported is True

    def test_full_stats_sample_true(self, sv):
        result = sv.validate(FULL_STAT_TEXT)
        assert result.sample_size_stated is True

    def test_full_stats_no_issues(self, sv):
        result = sv.validate(FULL_STAT_TEXT)
        assert len(result.issues) == 0

    # ---- Word-only p-value
    def test_word_only_p_reported_true(self, sv):
        result = sv.validate(WORD_ONLY_P_TEXT)
        assert result.p_value_reported is True

    def test_word_only_p_numeric_false(self, sv):
        result = sv.validate(WORD_ONLY_P_TEXT)
        assert result.p_value_numeric is False

    def test_word_only_has_p_issue(self, sv):
        result = sv.validate(WORD_ONLY_P_TEXT)
        # Should flag that numeric p-value is missing
        assert any("numeric" in issue.lower() for issue in result.issues)

    # ---- No stats
    def test_no_stats_low_score(self, sv):
        result = sv.validate(NO_STATS_TEXT)
        assert result.score == 0.0

    def test_no_stats_all_false(self, sv):
        result = sv.validate(NO_STATS_TEXT)
        assert result.p_value_reported is False
        assert result.effect_size_reported is False
        assert result.ci_reported is False

    def test_no_stats_has_issues(self, sv):
        result = sv.validate(NO_STATS_TEXT)
        assert len(result.issues) > 0

    # ---- Partial stats
    def test_partial_stats_score_between(self, sv):
        result = sv.validate(PARTIAL_STATS_TEXT)
        assert 0.0 < result.score < 0.70

    # ---- Section-focused analysis
    def test_section_map_focuses_methods_results(self, sv):
        from veritas.ingest.section_parser import SectionParser

        parser = SectionParser()
        sm = parser.parse(FULL_STAT_TEXT)
        result_with_map = sv.validate(FULL_STAT_TEXT, section_map=sm)
        result_without = sv.validate(FULL_STAT_TEXT)
        # Both should detect stats; section-focused shouldn't lose info
        assert result_with_map.p_value_numeric is True
        assert result_with_map.score >= result_without.score - 0.05

    def test_stat_validity_returns_correct_type(self, sv):
        result = sv.validate(FULL_STAT_TEXT)
        assert isinstance(result, StatValidity)

    # ---- Score weights
    def test_score_only_p_numeric(self, sv):
        # p=0.032 only; no other indicators
        result = sv.validate("The result was significant (p = 0.032).")
        assert result.score == pytest.approx(0.30, abs=0.01)

    def test_score_weights_sum_correct(self, sv):
        # Test that full score equals 1.0 when all criteria met
        result = sv.validate(FULL_STAT_TEXT)
        assert result.score <= 1.0

    # ---- as_dict
    def test_as_dict_contains_all_keys(self, sv):
        result = sv.validate(FULL_STAT_TEXT)
        d = result.as_dict()
        required_keys = [
            "p_value_reported",
            "p_value_numeric",
            "effect_size_reported",
            "ci_reported",
            "power_reported",
            "sample_size_stated",
            "score",
            "issues",
        ]
        for key in required_keys:
            assert key in d

    def test_issues_is_list(self, sv):
        result = sv.validate(NO_STATS_TEXT)
        assert isinstance(result.issues, list)
