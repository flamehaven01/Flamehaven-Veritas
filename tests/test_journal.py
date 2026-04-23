"""Tests for veritas.journal — JournalProfile + JournalScorer (Phase 2, v3.3)."""

from __future__ import annotations

import pytest

from veritas.engine import SciExpCritiqueEngine
from veritas.journal.journal_profiles import (
    JOURNAL_PROFILES,
    JournalProfile,
    JournalVerdict,
    get_profile,
)
from veritas.journal.journal_scorer import JournalScorer, JournalScoringResult
from veritas.types import (
    CritiqueReport,
    PrecheckResult,
    SciExpMode,
    StepResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_step(step_id: str, weight: float = 1.0, not_applicable: bool = False):
    return StepResult(step_id=step_id, weight=weight, prose=".", not_applicable=not_applicable)


def _make_report(omega: float = 0.8, steps=None):
    return CritiqueReport(
        precheck=PrecheckResult(SciExpMode.FULL, []),
        steps=steps or [],
        omega_score=omega,
    )


PAPER_TEXT = """
Abstract
High-dose vitamin D reduces fracture risk in elderly patients aged 65-80.
Methods
RCT n=340, power=0.80, alpha=0.05. 4000 IU/day for 12 months.
Results
Fracture incidence: 12% vs 21% (p=0.003), 95% CI 0.24-0.61, Cohen d=0.54.
Discussion
Results confirm clinical significance. Some limitations exist.
Conclusion
High-dose vitamin D reduces fractures by 43% (p=0.003).
""".strip()


# ---------------------------------------------------------------------------
# JOURNAL_PROFILES data integrity
# ---------------------------------------------------------------------------


class TestJournalProfiles:
    def test_all_required_keys_present(self):
        for key in ("nature", "ieee", "lancet", "q1", "q2", "q3", "default"):
            assert key in JOURNAL_PROFILES

    def test_profiles_are_frozen(self):
        profile = JOURNAL_PROFILES["nature"]
        with pytest.raises((AttributeError, TypeError)):
            profile.key = "hacked"  # type: ignore[misc]

    def test_accept_omega_gt_revise_omega(self):
        for key, p in JOURNAL_PROFILES.items():
            assert p.accept_omega > p.revise_omega, f"{key}: accept must exceed revise"

    def test_omega_thresholds_in_range(self):
        for p in JOURNAL_PROFILES.values():
            assert 0.0 < p.revise_omega < p.accept_omega <= 1.0

    def test_nature_is_strictest(self):
        nature = JOURNAL_PROFILES["nature"]
        q3 = JOURNAL_PROFILES["q3"]
        assert nature.accept_omega > q3.accept_omega

    def test_default_matches_v32_behavior(self):
        default = JOURNAL_PROFILES["default"]
        assert default.accept_omega == pytest.approx(0.78)
        assert default.revise_omega == pytest.approx(0.60)
        assert default.step_weights == {}

    def test_as_dict_keys(self):
        d = JOURNAL_PROFILES["ieee"].as_dict()
        assert set(d.keys()) == {"key", "name", "accept_omega", "revise_omega", "step_weights", "description"}

    def test_get_profile_valid_key(self):
        p = get_profile("nature")
        assert isinstance(p, JournalProfile)
        assert p.key == "nature"

    def test_get_profile_case_insensitive(self):
        p = get_profile("IEEE")
        assert p.key == "ieee"

    def test_get_profile_unknown_key_raises(self):
        with pytest.raises(KeyError, match="Unknown journal profile"):
            get_profile("nonexistent_journal_xyz")

    def test_verdict_for_accept(self):
        p = JOURNAL_PROFILES["q3"]
        assert p.verdict_for(0.75) == JournalVerdict.ACCEPT

    def test_verdict_for_revise(self):
        p = JOURNAL_PROFILES["q3"]
        assert p.verdict_for(0.60) == JournalVerdict.REVISE

    def test_verdict_for_reject(self):
        p = JOURNAL_PROFILES["q3"]
        assert p.verdict_for(0.40) == JournalVerdict.REJECT

    def test_verdict_exact_accept_threshold(self):
        p = JOURNAL_PROFILES["q3"]
        assert p.verdict_for(p.accept_omega) == JournalVerdict.ACCEPT

    def test_verdict_exact_revise_threshold(self):
        p = JOURNAL_PROFILES["q3"]
        assert p.verdict_for(p.revise_omega) == JournalVerdict.REVISE


# ---------------------------------------------------------------------------
# JournalScoringResult
# ---------------------------------------------------------------------------


class TestJournalScoringResult:
    def _result(self, raw: float = 0.7, calib: float = 0.75, verdict=JournalVerdict.REVISE):
        return JournalScoringResult(
            journal_key="q2",
            journal_name="Q2",
            raw_omega=raw,
            calibrated_omega=calib,
            omega_delta=calib - raw,
            verdict=verdict,
            accept_threshold=0.78,
            revise_threshold=0.60,
            step_contributions={},
        )

    def test_as_dict_keys(self):
        d = self._result().as_dict()
        assert "journal_key" in d
        assert "calibrated_omega" in d
        assert "verdict" in d
        assert "step_contributions" in d

    def test_omega_delta_positive_when_calibrated_higher(self):
        r = self._result(raw=0.7, calib=0.75)
        assert r.omega_delta == pytest.approx(0.05)

    def test_omega_delta_negative_when_calibrated_lower(self):
        r = self._result(raw=0.8, calib=0.70)
        assert r.omega_delta == pytest.approx(-0.10)


# ---------------------------------------------------------------------------
# JournalScorer — unit tests
# ---------------------------------------------------------------------------


class TestJournalScorer:
    @pytest.fixture()
    def scorer(self):
        return JournalScorer()

    def test_returns_scoring_result(self, scorer):
        report = _make_report(omega=0.8)
        result = scorer.score(report, journal="default")
        assert isinstance(result, JournalScoringResult)

    def test_default_journal_calibrated_equals_raw_when_no_steps(self, scorer):
        report = _make_report(omega=0.8, steps=[])
        result = scorer.score(report, journal="default")
        assert result.calibrated_omega == pytest.approx(0.8)
        assert result.omega_delta == pytest.approx(0.0)

    def test_no_steps_passes_through_verdict(self, scorer):
        report = _make_report(omega=0.9, steps=[])
        result = scorer.score(report, journal="q3")
        assert result.verdict == JournalVerdict.ACCEPT

    def test_unknown_journal_raises_keyerror(self, scorer):
        report = _make_report()
        with pytest.raises(KeyError):
            scorer.score(report, journal="fake_journal_xyz")

    def test_calibrated_omega_in_unit_interval(self, scorer):
        for journal in JOURNAL_PROFILES:
            steps = [_make_step(str(i)) for i in range(1, 6)]
            report = _make_report(omega=0.9, steps=steps)
            result = scorer.score(report, journal=journal)
            assert 0.0 <= result.calibrated_omega <= 1.0, f"Failed for {journal}"

    def test_accept_threshold_matches_profile(self, scorer):
        profile = get_profile("nature")
        report = _make_report(omega=0.95)
        result = scorer.score_with_profile(report, profile)
        assert result.accept_threshold == profile.accept_omega
        assert result.revise_threshold == profile.revise_omega

    def test_step_contributions_populated(self, scorer):
        steps = [_make_step("1"), _make_step("2")]
        report = _make_report(omega=0.75, steps=steps)
        result = scorer.score(report, journal="ieee")
        assert "1" in result.step_contributions
        assert "2" in result.step_contributions

    def test_not_applicable_steps_excluded(self, scorer):
        steps = [_make_step("1"), _make_step("2", not_applicable=True)]
        report = _make_report(omega=0.75, steps=steps)
        result = scorer.score(report, journal="ieee")
        assert "1" in result.step_contributions
        assert "2" not in result.step_contributions

    def test_nature_multipliers_shift_omega(self, scorer):
        # Steps with no findings → per-step quality = 1.0 → calibrated = 1.0
        steps = [_make_step(str(i), weight=1.0) for i in range(1, 6)]
        report = _make_report(omega=0.7, steps=steps)
        result_nature = scorer.score(report, journal="nature")
        result_default = scorer.score(report, journal="default")
        # Both profiles: no findings → quality=1.0 each → calibrated_omega=1.0
        assert result_nature.calibrated_omega == pytest.approx(1.0)
        assert result_default.calibrated_omega == pytest.approx(1.0)

    def test_journal_name_stored(self, scorer):
        report = _make_report()
        result = scorer.score(report, journal="lancet")
        assert "Lancet" in result.journal_name

    def test_verdict_accept_when_omega_above_threshold(self, scorer):
        report = _make_report(omega=0.98)
        result = scorer.score(report, journal="nature")
        assert result.verdict == JournalVerdict.ACCEPT

    def test_verdict_reject_when_omega_below_revise_threshold(self, scorer):
        report = _make_report(omega=0.30)
        result = scorer.score(report, journal="nature")
        assert result.verdict == JournalVerdict.REJECT


# ---------------------------------------------------------------------------
# JournalScorer — integration with full engine
# ---------------------------------------------------------------------------


class TestJournalScorerIntegration:
    @pytest.fixture()
    def scorer(self):
        return JournalScorer()

    @pytest.fixture()
    def engine(self):
        return SciExpCritiqueEngine()

    def test_real_paper_scoring(self, scorer, engine):
        report = engine.critique(PAPER_TEXT)
        result = scorer.score(report, journal="q2")
        assert isinstance(result, JournalScoringResult)
        assert 0.0 <= result.calibrated_omega <= 1.0

    def test_all_profiles_runnable(self, scorer, engine):
        report = engine.critique(PAPER_TEXT)
        for key in JOURNAL_PROFILES:
            result = scorer.score(report, journal=key)
            assert result.journal_key == key

    def test_as_dict_serializable(self, scorer, engine):
        import json
        report = engine.critique(PAPER_TEXT)
        result = scorer.score(report, journal="ieee")
        d = result.as_dict()
        json.dumps(d)  # must not raise
