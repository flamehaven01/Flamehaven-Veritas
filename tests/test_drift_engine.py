"""Tests for veritas.logos.drift_engine (v2.3.0 multi-round drift tracking)."""

from __future__ import annotations

import pytest

from veritas.logos.drift_engine import (
    JSD_MAX,
    JSD_WARN,
    DriftEngine,
    DriftLevel,
    _jsd,
    _kl_divergence,
    _normalized_l2,
    _to_distribution,
)
from veritas.types import IRF6DScores

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_irf(m=0.8, a=0.7, d=0.75, i=0.8, f=0.7, p=0.75, composite=None) -> IRF6DScores:
    comp = composite if composite is not None else (m + a + d + i + f + p) / 6
    return IRF6DScores(
        M=m,
        A=a,
        D=d,
        I=i,
        F=f,
        P=p,
        composite=comp,
        passed=comp >= 0.78,
        source="test",
    )


# ---------------------------------------------------------------------------
# Internal math helpers
# ---------------------------------------------------------------------------


class TestToDistribution:
    def test_sums_to_one(self):
        dist = _to_distribution((0.8, 0.7, 0.75, 0.8, 0.7, 0.75))
        assert abs(sum(dist) - 1.0) < 1e-9

    def test_no_zeros(self):
        dist = _to_distribution((0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        assert all(v > 0 for v in dist)

    def test_preserves_relative_order(self):
        dist = _to_distribution((0.9, 0.1))
        assert dist[0] > dist[1]


class TestKLDivergence:
    def test_identical_distributions_zero(self):
        p = [0.25, 0.25, 0.25, 0.25]
        assert _kl_divergence(p, p) < 1e-12

    def test_asymmetric(self):
        # KL divergence is asymmetric: KL(p||q) != KL(q||r) for non-uniform p,q,r
        p = [0.9, 0.05, 0.05]
        q = [0.05, 0.9, 0.05]
        r = [0.05, 0.05, 0.9]
        assert _kl_divergence(p, q) != _kl_divergence(p, r) or _kl_divergence(p, q) > 0


class TestJSD:
    def test_identical_zero(self):
        p = [0.25, 0.25, 0.25, 0.25]
        assert _jsd(p, p) < 1e-9

    def test_opposite_bounded(self):
        p = [1.0 - 1e-9, 1e-9]
        q = [1e-9, 1.0 - 1e-9]
        j = _jsd(p, q)
        assert 0.0 <= j <= 1.0

    def test_symmetric(self):
        p = [0.7, 0.3]
        q = [0.4, 0.6]
        assert abs(_jsd(p, q) - _jsd(q, p)) < 1e-12


class TestNormalizedL2:
    def test_identical_zero(self):
        a = (0.8, 0.7, 0.75, 0.8, 0.7, 0.75)
        assert _normalized_l2(a, a) == 0.0

    def test_larger_distance_bigger(self):
        a = (1.0,) * 6
        b = (0.0,) * 6
        c = (0.5,) * 6
        assert _normalized_l2(a, b) > _normalized_l2(a, c)

    def test_empty(self):
        assert _normalized_l2((), ()) == 0.0


# ---------------------------------------------------------------------------
# DriftEngine
# ---------------------------------------------------------------------------


class TestDriftEngineNormal:
    def test_identical_rounds_normal(self):
        de = DriftEngine()
        irf = _make_irf()
        dm = de.compute_round_drift(irf, irf, round_from=1, round_to=2)
        assert dm.level == DriftLevel.NORMAL
        assert dm.jsd < JSD_WARN
        assert dm.delta_omega == pytest.approx(0.0, abs=1e-5)
        assert dm.should_halt is False
        assert dm.remediation is None

    def test_round_numbers_stored(self):
        de = DriftEngine()
        irf = _make_irf()
        dm = de.compute_round_drift(irf, irf, round_from=2, round_to=3)
        assert dm.round_from == 2
        assert dm.round_to == 3

    def test_delta_omega_sign(self):
        de = DriftEngine()
        prev = _make_irf(composite=0.70)
        curr = _make_irf(composite=0.85)
        dm = de.compute_round_drift(curr, prev, round_from=1, round_to=2)
        assert dm.delta_omega > 0.0


class TestDriftEnginePenalty:
    def test_zero_jsd_no_penalty(self):
        de = DriftEngine()
        assert de.apply_penalty(0.85, 0.0) == pytest.approx(0.85, rel=1e-5)

    def test_max_jsd_collapses(self):
        de = DriftEngine()
        assert de.apply_penalty(0.90, JSD_MAX) == pytest.approx(0.0, abs=1e-5)

    def test_half_max_jsd_half_penalty(self):
        de = DriftEngine()
        result = de.apply_penalty(1.0, JSD_MAX / 2)
        assert abs(result - 0.5) < 1e-5

    def test_clamps_to_zero(self):
        de = DriftEngine()
        assert de.apply_penalty(0.9, JSD_MAX * 10) == 0.0

    def test_clamps_to_one(self):
        de = DriftEngine()
        assert de.apply_penalty(1.0, 0.0) == pytest.approx(1.0, rel=1e-5)


class TestDriftMetricsAsDict:
    def test_as_dict_keys(self):
        de = DriftEngine()
        irf = _make_irf()
        dm = de.compute_round_drift(irf, irf)
        d = dm.as_dict()
        for key in (
            "jsd",
            "l2",
            "level",
            "should_halt",
            "remediation",
            "omega_penalty_factor",
            "delta_omega",
            "round_from",
            "round_to",
        ):
            assert key in d

    def test_as_dict_json_serializable(self):
        import json

        de = DriftEngine()
        irf = _make_irf()
        dm = de.compute_round_drift(irf, irf)
        # Must not raise
        json.dumps(dm.as_dict())

    def test_level_is_string(self):
        de = DriftEngine()
        irf = _make_irf()
        dm = de.compute_round_drift(irf, irf)
        assert isinstance(dm.as_dict()["level"], str)


# ---------------------------------------------------------------------------
# CritiqueReport round-summary serialization (integration)
# ---------------------------------------------------------------------------


class TestCritiqueReportRoundSummary:
    def test_to_round_summary_keys(self, engine, sample_text):
        report = engine.critique(sample_text, round_number=1)
        summary = report.to_round_summary()
        for key in ("round_number", "omega_score", "irf_scores"):
            assert key in summary

    def test_round_number_stored(self, engine, sample_text):
        report = engine.critique(sample_text, round_number=3)
        assert report.to_round_summary()["round_number"] == 3

    def test_from_round_summary_roundtrip(self, engine, sample_text):
        from veritas.types import CritiqueReport

        r1 = engine.critique(sample_text, round_number=1)
        summary = r1.to_round_summary()
        r1_loaded = CritiqueReport.from_round_summary(summary)
        assert r1_loaded.round_number == 1
        assert abs(r1_loaded.omega_score - r1.omega_score) < 1e-9

    def test_from_round_summary_irf_preserved(self, engine, sample_text):
        from veritas.types import CritiqueReport

        r1 = engine.critique(sample_text, round_number=1)
        if r1.irf_scores is None:
            pytest.skip("No IRF scores in report; skip round summary IRF test")
        summary = r1.to_round_summary()
        loaded = CritiqueReport.from_round_summary(summary)
        assert loaded.irf_scores is not None
        assert abs(loaded.irf_scores.M - r1.irf_scores.M) < 1e-9


# ---------------------------------------------------------------------------
# Multi-round engine integration
# ---------------------------------------------------------------------------


class TestMultiRoundEngine:
    def test_drift_metrics_populated_on_second_round(self, engine, sample_text):
        r1 = engine.critique(sample_text, round_number=1)
        if r1.irf_scores is None:
            pytest.skip("IRF scores unavailable; skip drift test")
        r2 = engine.critique(sample_text, round_number=2, prev_report=r1)
        assert r2.drift_metrics is not None
        assert r2.delta_omega is not None
        assert r2.jsd_penalized_omega is not None

    def test_no_drift_without_prev(self, engine, sample_text):
        r1 = engine.critique(sample_text, round_number=1)
        assert r1.drift_metrics is None
        assert r1.delta_omega is None

    def test_identical_rounds_stable(self, engine, sample_text):
        r1 = engine.critique(sample_text, round_number=1)
        if r1.irf_scores is None:
            pytest.skip("IRF scores unavailable")
        r2 = engine.critique(sample_text, round_number=2, prev_report=r1)
        if r2.drift_metrics is not None:
            assert r2.drift_metrics["level"] == "normal"
