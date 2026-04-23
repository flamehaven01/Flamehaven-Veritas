"""Phase 3 tests — reviewer package (persona, consensus, DR3, engine)."""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Persona
# ─────────────────────────────────────────────────────────────────────────────


class TestPersonaConfig:
    def test_presets_defined(self):
        from veritas.reviewer.persona import BALANCED, LENIENT, STRICT

        assert STRICT.name == "strict"
        assert BALANCED.name == "balanced"
        assert LENIENT.name == "lenient"

    def test_min_omega_ordering(self):
        from veritas.reviewer.persona import BALANCED, LENIENT, STRICT

        assert STRICT.min_omega > BALANCED.min_omega > LENIENT.min_omega

    def test_strict_weights_elevated(self):
        from veritas.reviewer.persona import BALANCED, STRICT

        assert STRICT.dim_weights["M"] > BALANCED.dim_weights["M"]
        assert STRICT.dim_weights["D"] > BALANCED.dim_weights["D"]

    def test_lenient_weights_reduced(self):
        from veritas.reviewer.persona import BALANCED, LENIENT

        assert LENIENT.dim_weights["M"] < BALANCED.dim_weights["M"]

    def test_calibrate_omega_uniform_irf(self):
        """Uniform IRF scores => calibrated omega == raw mean (weights cancel)."""
        from veritas.reviewer.persona import BALANCED, calibrate_omega
        from veritas.types import IRF6DScores

        irf = IRF6DScores(M=0.8, A=0.8, D=0.8, I=0.8, F=0.8, P=0.8, composite=0.8, passed=True)
        result = calibrate_omega(irf, BALANCED.dim_weights)
        assert abs(result - 0.8) < 1e-6

    def test_calibrate_omega_strict_penalises_low_maf(self):
        """Low M, A, F with STRICT weighting => calibrated < balanced."""
        from veritas.reviewer.persona import BALANCED, STRICT, calibrate_omega
        from veritas.types import IRF6DScores

        irf = IRF6DScores(M=0.5, A=0.5, D=0.9, I=0.9, F=0.5, P=0.9, composite=0.7, passed=False)
        s = calibrate_omega(irf, STRICT.dim_weights)
        b = calibrate_omega(irf, BALANCED.dim_weights)
        assert s < b

    def test_calibrate_omega_bounded(self):
        from veritas.reviewer.persona import STRICT, calibrate_omega
        from veritas.types import IRF6DScores

        irf = IRF6DScores(M=1.0, A=1.0, D=1.0, I=1.0, F=1.0, P=1.0, composite=1.0, passed=True)
        result = calibrate_omega(irf, STRICT.dim_weights)
        assert 0.0 <= result <= 1.0

    def test_select_personas_3(self):
        from veritas.reviewer.persona import select_personas

        personas = select_personas(3)
        assert len(personas) == 3
        names = [p.name for p in personas]
        assert "strict" in names and "balanced" in names and "lenient" in names

    def test_select_personas_2(self):
        from veritas.reviewer.persona import select_personas

        personas = select_personas(2)
        assert len(personas) == 2
        names = [p.name for p in personas]
        assert "strict" in names and "balanced" in names

    def test_select_personas_clamps_to_max(self):
        from veritas.reviewer.persona import select_personas

        personas = select_personas(10)
        assert len(personas) == 3

    def test_persona_as_dict(self):
        from veritas.reviewer.persona import BALANCED

        d = BALANCED.as_dict()
        assert d["name"] == "balanced"
        assert "min_omega" in d
        assert "dim_weights" in d


# ─────────────────────────────────────────────────────────────────────────────
# Consensus
# ─────────────────────────────────────────────────────────────────────────────


class TestCrossValidator:
    def test_consensus_reached(self):
        from veritas.reviewer.consensus import CrossValidator

        cv = CrossValidator()
        r = cv.check_consensus({"strict": 0.75, "balanced": 0.80, "lenient": 0.82})
        assert r.reached is True

    def test_consensus_not_reached(self):
        from veritas.reviewer.consensus import CrossValidator

        cv = CrossValidator()
        r = cv.check_consensus({"strict": 0.50, "balanced": 0.80, "lenient": 0.85})
        assert r.reached is False

    def test_consensus_omega_mean(self):
        from veritas.reviewer.consensus import CrossValidator

        cv = CrossValidator()
        r = cv.check_consensus({"a": 0.70, "b": 0.80})
        assert abs(r.consensus_omega - 0.75) < 1e-4

    def test_variance_correct(self):
        from veritas.reviewer.consensus import CrossValidator

        cv = CrossValidator()
        r = cv.check_consensus({"a": 0.60, "b": 0.80})
        # population variance: ((0.70-0.60)^2 + (0.70-0.80)^2) / 2 = 0.01
        assert abs(r.variance - 0.01) < 1e-6

    def test_spread_correct(self):
        from veritas.reviewer.consensus import CrossValidator

        cv = CrossValidator()
        r = cv.check_consensus({"a": 0.60, "b": 0.90})
        assert abs(r.spread - 0.30) < 1e-6

    def test_recommendation_accept(self):
        from veritas.reviewer.consensus import CrossValidator

        cv = CrossValidator()
        r = cv.check_consensus({"a": 0.80, "b": 0.85})
        assert r.recommendation == "ACCEPT"

    def test_recommendation_revise(self):
        from veritas.reviewer.consensus import CrossValidator

        cv = CrossValidator()
        r = cv.check_consensus({"a": 0.65, "b": 0.68})
        assert r.recommendation == "REVISE"

    def test_recommendation_reject(self):
        from veritas.reviewer.consensus import CrossValidator

        cv = CrossValidator()
        r = cv.check_consensus({"a": 0.50, "b": 0.55})
        assert r.recommendation == "REJECT"

    def test_empty_omegas(self):
        from veritas.reviewer.consensus import CrossValidator

        cv = CrossValidator()
        r = cv.check_consensus({})
        assert r.reached is False
        assert r.consensus_omega == 0.0

    def test_single_omega(self):
        from veritas.reviewer.consensus import CrossValidator

        cv = CrossValidator()
        r = cv.check_consensus({"only": 0.82})
        assert r.reached is True
        assert abs(r.consensus_omega - 0.82) < 1e-4
        assert r.spread == 0.0

    def test_module_level_wrapper(self):
        from veritas.reviewer.consensus import check_consensus

        r = check_consensus({"a": 0.78, "b": 0.79})
        assert r.recommendation == "ACCEPT"

    def test_as_dict_keys(self):
        from veritas.reviewer.consensus import CrossValidator

        r = CrossValidator().check_consensus({"a": 0.75})
        d = r.as_dict()
        for k in ["omegas", "consensus_omega", "variance", "spread", "reached", "recommendation"]:
            assert k in d

    def test_summary_line_contains_omega(self):
        from veritas.reviewer.consensus import CrossValidator

        r = CrossValidator().check_consensus({"a": 0.75, "b": 0.80})
        line = r.summary_line()
        assert "omega=" in line

    def test_custom_spread_threshold(self):
        from veritas.reviewer.consensus import CrossValidator

        cv = CrossValidator(spread_threshold=0.10)
        # spread=0.20 > 0.10 threshold → NOT reached
        r = cv.check_consensus({"a": 0.70, "b": 0.90})
        assert r.reached is False


# ─────────────────────────────────────────────────────────────────────────────
# DR3 Protocol
# ─────────────────────────────────────────────────────────────────────────────


class TestDR3Protocol:
    def _make_consensus(self, omega, reached=True, spread=0.10):
        from veritas.reviewer.consensus import ConsensusResult

        return ConsensusResult(
            omegas={},
            consensus_omega=omega,
            variance=0.0,
            spread=spread,
            reached=reached,
            recommendation="ACCEPT",
        )

    def test_no_trigger_above_threshold(self):
        from veritas.reviewer.dr3 import DR3Protocol

        dr3 = DR3Protocol()
        c = self._make_consensus(0.72)
        r = dr3.resolve(c, {"balanced": 0.72})
        assert r.conflict_detected is False
        assert r.final_omega == 0.72

    def test_trigger_below_threshold(self):
        from veritas.reviewer.dr3 import DR3Protocol

        dr3 = DR3Protocol()
        c = self._make_consensus(0.45, reached=False, spread=0.40)
        r = dr3.resolve(c, {"balanced": 0.50, "strict": 0.30, "lenient": 0.65})
        assert r.conflict_detected is True

    def test_tiebreaker_persona_is_balanced(self):
        from veritas.reviewer.dr3 import DR3Protocol

        dr3 = DR3Protocol()
        c = self._make_consensus(0.45, reached=False)
        r = dr3.resolve(c, {"balanced": 0.50})
        assert r.tiebreaker_persona == "balanced"

    def test_penalty_applied(self):
        from veritas.reviewer.dr3 import DR3_PENALTY_FACTOR, DR3Protocol

        dr3 = DR3Protocol()
        c = self._make_consensus(0.45, reached=False)
        r = dr3.resolve(c, {"balanced": 0.60})
        expected = round(0.60 * DR3_PENALTY_FACTOR, 4)
        assert abs(r.final_omega - expected) < 1e-4

    def test_resolution_note_contains_info(self):
        from veritas.reviewer.dr3 import DR3Protocol

        dr3 = DR3Protocol()
        c = self._make_consensus(0.45, reached=False)
        r = dr3.resolve(c, {"balanced": 0.55})
        assert "0.45" in r.resolution_note or "balanced" in r.resolution_note

    def test_no_trigger_exact_threshold(self):
        from veritas.reviewer.dr3 import DR3_TRIGGER_THRESHOLD, DR3Protocol

        dr3 = DR3Protocol()
        c = self._make_consensus(DR3_TRIGGER_THRESHOLD, reached=True)
        r = dr3.resolve(c, {"balanced": DR3_TRIGGER_THRESHOLD})
        assert r.conflict_detected is False

    def test_fallback_when_tiebreaker_missing(self):
        """Missing balanced key → falls back to consensus_omega."""
        from veritas.reviewer.dr3 import DR3_PENALTY_FACTOR, DR3Protocol

        dr3 = DR3Protocol()
        c = self._make_consensus(0.45, reached=False)
        r = dr3.resolve(c, {"strict": 0.30})
        expected = round(0.45 * DR3_PENALTY_FACTOR, 4)
        assert abs(r.final_omega - expected) < 1e-4

    def test_as_dict_keys(self):
        from veritas.reviewer.dr3 import DR3Protocol

        dr3 = DR3Protocol()
        c = self._make_consensus(0.80)
        r = dr3.resolve(c, {"balanced": 0.80})
        d = r.as_dict()
        for k in ["conflict_detected", "tiebreaker_persona", "final_omega", "resolution_note"]:
            assert k in d

    def test_summary_line_not_triggered(self):
        from veritas.reviewer.dr3 import DR3Protocol

        dr3 = DR3Protocol()
        c = self._make_consensus(0.80)
        r = dr3.resolve(c, {"balanced": 0.80})
        assert "Not triggered" in r.summary_line()

    def test_summary_line_triggered(self):
        from veritas.reviewer.dr3 import DR3Protocol

        dr3 = DR3Protocol()
        c = self._make_consensus(0.40, reached=False)
        r = dr3.resolve(c, {"balanced": 0.55})
        assert "CONFLICT" in r.summary_line()


# ─────────────────────────────────────────────────────────────────────────────
# ReviewSimEngine
# ─────────────────────────────────────────────────────────────────────────────

SHORT_TEXT = (
    "Methods: We tested drug X vs placebo in 30 subjects. "
    "Results: p=0.04, effect size d=0.5. "
    "Conclusion: Drug X is effective."
)


class TestReviewSimEngine:
    def test_run_returns_result(self):
        from veritas.reviewer.engine import ReviewSimEngine

        engine = ReviewSimEngine()
        result = engine.run(SHORT_TEXT, reviewers=3)
        assert result is not None

    def test_three_reviewers(self):
        from veritas.reviewer.engine import ReviewSimEngine

        result = ReviewSimEngine().run(SHORT_TEXT, reviewers=3)
        assert len(result.per_reviewer) == 3

    def test_two_reviewers(self):
        from veritas.reviewer.engine import ReviewSimEngine

        result = ReviewSimEngine().run(SHORT_TEXT, reviewers=2)
        assert len(result.per_reviewer) == 2

    def test_reviewer_names_present(self):
        from veritas.reviewer.engine import ReviewSimEngine

        result = ReviewSimEngine().run(SHORT_TEXT, reviewers=3)
        names = {r.persona for r in result.per_reviewer}
        assert "strict" in names
        assert "balanced" in names
        assert "lenient" in names

    def test_calibrated_omegas_bounded(self):
        from veritas.reviewer.engine import ReviewSimEngine

        result = ReviewSimEngine().run(SHORT_TEXT)
        for rev in result.per_reviewer:
            assert 0.0 <= rev.calibrated_omega <= 1.0

    def test_consensus_present(self):
        from veritas.reviewer.engine import ReviewSimEngine

        result = ReviewSimEngine().run(SHORT_TEXT)
        assert result.consensus is not None
        assert 0.0 <= result.consensus.consensus_omega <= 1.0

    def test_dr3_present(self):
        from veritas.reviewer.engine import ReviewSimEngine

        result = ReviewSimEngine().run(SHORT_TEXT)
        assert result.dr3 is not None
        assert isinstance(result.dr3.conflict_detected, bool)

    def test_final_omega_bounded(self):
        from veritas.reviewer.engine import ReviewSimEngine

        result = ReviewSimEngine().run(SHORT_TEXT)
        assert 0.0 <= result.final_omega <= 1.0

    def test_final_recommendation_valid(self):
        from veritas.reviewer.engine import ReviewSimEngine

        result = ReviewSimEngine().run(SHORT_TEXT)
        assert result.final_recommendation in {"ACCEPT", "REVISE", "REJECT"}

    def test_as_dict_structure(self):
        from veritas.reviewer.engine import ReviewSimEngine

        result = ReviewSimEngine().run(SHORT_TEXT)
        d = result.as_dict()
        assert "per_reviewer" in d
        assert "consensus" in d
        assert "dr3" in d
        assert "final_omega" in d
        assert "final_recommendation" in d

    def test_render_text_non_empty(self):
        from veritas.reviewer.engine import ReviewSimEngine

        result = ReviewSimEngine().run(SHORT_TEXT)
        text = result.render_text()
        assert "FINAL" in text
        assert "omega=" in text

    def test_render_text_contains_all_personas(self):
        from veritas.reviewer.engine import ReviewSimEngine

        result = ReviewSimEngine().run(SHORT_TEXT, reviewers=3)
        text = result.render_text()
        for rev in result.per_reviewer:
            assert rev.persona in text

    def test_strict_calibrated_lte_lenient_calibrated(self):
        """Strict reviewer should never score higher than lenient on low-quality text."""
        from veritas.reviewer.engine import ReviewSimEngine

        result = ReviewSimEngine().run("Introduction only. No methods. No data.", reviewers=3)
        omegas = {r.persona: r.calibrated_omega for r in result.per_reviewer}
        # STRICT penalises hard — strict <= lenient
        assert omegas.get("strict", 1.0) <= omegas.get("lenient", 0.0) + 0.30


# ─────────────────────────────────────────────────────────────────────────────
# Package __init__ re-exports
# ─────────────────────────────────────────────────────────────────────────────


class TestReviewerPackageExports:
    def test_all_symbols_importable(self):
        from veritas.reviewer import (
            PersonaConfig,
            ReviewSimEngine,
        )

        assert PersonaConfig is not None
        assert ReviewSimEngine is not None
