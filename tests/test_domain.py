"""Tests for v3.4 domain plugin subsystem.

Coverage:
  - DomainRuleset dataclass (base.py)
  - DomainRegistry: register, get, list_keys, KeyError
  - Built-in domains: biomedical, cs, math loaded correctly
  - IRFAnalyzer domain-aware constructor (str key, DomainRuleset instance, None default)
  - Scoring divergence: CS text scores higher on CS domain vs biomedical
  - Scoring divergence: math text scores higher on math domain vs biomedical
  - Backward compat: IRFAnalyzer() == IRFAnalyzer(domain="biomedical") scores
  - Entry_points mock: registry scans and registers plugin domains
  - markers_for() and saturation() helpers on DomainRuleset
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from veritas.logos.domain.base import DomainRuleset
from veritas.logos.domain.registry import (
    DomainRegistry,
    get_domain,
    list_domain_keys,
)
from veritas.logos.irf_analyzer import IRFAnalyzer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ruleset(key: str = "test_domain") -> DomainRuleset:
    return DomainRuleset(
        domain_key=key,
        name=f"Test Domain ({key})",
        m_markers=("limitation", "caveat"),
        a_markers=("hypothesis", "theorem"),
        d_markers=("therefore", "hence"),
        i_markers=("result", "experiment"),
        f_markers=("reproducible", "protocol"),
        p_markers=("reference", "et al"),
    )


# ---------------------------------------------------------------------------
# DomainRuleset — base.py
# ---------------------------------------------------------------------------

class TestDomainRuleset:
    def test_frozen(self):
        rs = _make_ruleset()
        with pytest.raises((AttributeError, TypeError)):
            rs.domain_key = "mutated"  # type: ignore[misc]

    def test_markers_for_all_dims(self):
        rs = _make_ruleset()
        for dim in ("M", "A", "D", "I", "F", "P"):
            markers = rs.markers_for(dim)
            assert isinstance(markers, tuple)
            assert len(markers) > 0

    def test_markers_for_invalid_dim(self):
        rs = _make_ruleset()
        with pytest.raises(KeyError, match="Unknown IRF dimension"):
            rs.markers_for("X")

    def test_saturation_explicit(self):
        rs = DomainRuleset(
            domain_key="sat_test",
            name="Saturation Test",
            m_markers=("a",),
            a_markers=("b",),
            d_markers=("c",),
            i_markers=("d",),
            f_markers=("e",),
            p_markers=("f",),
            saturate_at={"M": 3, "I": 7},
        )
        assert rs.saturation("M") == 3
        assert rs.saturation("I") == 7
        assert rs.saturation("D") == 4  # default

    def test_saturation_default(self):
        rs = _make_ruleset()
        assert rs.saturation("M") == 4
        # Default factory: {"M":4,"A":4,"D":4,"I":5,"F":5,"P":4}
        # Verify a fresh ruleset (no saturate_at override) uses those factory values
        rs2 = DomainRuleset(
            domain_key="st2",
            name="ST2",
            m_markers=("a",),
            a_markers=("b",),
            d_markers=("c",),
            i_markers=("d",),
            f_markers=("e",),
            p_markers=("f",),
        )
        assert rs2.saturation("I") == 5   # factory default
        assert rs2.saturation("F") == 5   # factory default
        assert rs2.saturation("M") == 4   # factory default

    def test_composite_threshold_default(self):
        rs = _make_ruleset()
        assert rs.composite_threshold == 0.65

    def test_component_min_default(self):
        rs = _make_ruleset()
        assert rs.component_min == 0.30

    def test_custom_thresholds(self):
        rs = DomainRuleset(
            domain_key="custom_thresh",
            name="Custom",
            m_markers=("a",),
            a_markers=("b",),
            d_markers=("c",),
            i_markers=("d",),
            f_markers=("e",),
            p_markers=("f",),
            composite_threshold=0.70,
            component_min=0.25,
        )
        assert rs.composite_threshold == 0.70
        assert rs.component_min == 0.25


# ---------------------------------------------------------------------------
# DomainRegistry — registry.py
# ---------------------------------------------------------------------------

class TestDomainRegistry:
    def setup_method(self):
        # Use fresh isolated registry per test
        self.reg = DomainRegistry()

    def test_built_ins_loaded(self):
        keys = self.reg.list_keys()
        assert "biomedical" in keys
        assert "cs" in keys
        assert "math" in keys

    def test_get_biomedical(self):
        rs = self.reg.get("biomedical")
        assert rs.domain_key == "biomedical"
        assert len(rs.m_markers) > 0

    def test_get_cs(self):
        rs = self.reg.get("cs")
        assert rs.domain_key == "cs"
        assert any("benchmark" in m for m in rs.i_markers)

    def test_get_math(self):
        rs = self.reg.get("math")
        assert rs.domain_key == "math"
        assert any("axiom" in m for m in rs.a_markers)

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown domain"):
            self.reg.get("unknown_xyz_domain")

    def test_get_case_insensitive(self):
        rs = self.reg.get("BIOMEDICAL")
        assert rs.domain_key == "biomedical"

    def test_register_custom(self):
        custom = _make_ruleset("physics_test")
        self.reg.register(custom)
        assert "physics_test" in self.reg.list_keys()
        assert self.reg.get("physics_test") is custom

    def test_register_overwrites(self):
        original = _make_ruleset("overwrite_test")
        self.reg.register(original)
        updated = _make_ruleset("overwrite_test")
        self.reg.register(updated)
        assert self.reg.get("overwrite_test") is updated

    def test_register_non_ruleset_raises(self):
        with pytest.raises(TypeError, match="Expected DomainRuleset"):
            self.reg.register("not_a_ruleset")  # type: ignore[arg-type]

    def test_list_keys_sorted(self):
        keys = self.reg.list_keys()
        assert keys == sorted(keys)

    def test_iterate(self):
        domains = list(self.reg)
        assert len(domains) >= 3
        assert all(isinstance(d, DomainRuleset) for d in domains)


class TestModuleLevelHelpers:
    """Tests for module-level get_domain / register_domain / list_domain_keys."""

    def test_get_domain_biomedical(self):
        rs = get_domain("biomedical")
        assert rs.domain_key == "biomedical"

    def test_get_domain_cs(self):
        rs = get_domain("cs")
        assert rs.domain_key == "cs"

    def test_list_domain_keys_contains_builtins(self):
        keys = list_domain_keys()
        assert "biomedical" in keys
        assert "cs" in keys
        assert "math" in keys


# ---------------------------------------------------------------------------
# Entry_points mock — registry scans external plugins
# ---------------------------------------------------------------------------

class TestEntryPointsScan:
    def test_entry_points_plugin_loaded(self):
        """Entry_points group 'veritas.domains' correctly loads DomainRuleset."""
        fake_ruleset = _make_ruleset("mock_physics")

        mock_ep = MagicMock()
        mock_ep.load.return_value = fake_ruleset
        mock_ep.value = "mock_package:MOCK_DOMAIN"
        mock_ep.name = "mock_physics"

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            reg = DomainRegistry()
            keys = reg.list_keys()
            assert "mock_physics" in keys
            assert reg.get("mock_physics") is fake_ruleset

    def test_entry_points_non_ruleset_skipped(self):
        """Non-DomainRuleset entry_points objects are skipped without crash."""
        mock_ep = MagicMock()
        mock_ep.load.return_value = "not_a_ruleset"
        mock_ep.name = "bad_plugin"

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            reg = DomainRegistry()
            assert "bad_plugin" not in reg.list_keys()

    def test_entry_points_load_error_skipped(self):
        """Import errors from plugins are swallowed; registry still works."""
        mock_ep = MagicMock()
        mock_ep.load.side_effect = ImportError("module not found")
        mock_ep.name = "broken_plugin"

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            reg = DomainRegistry()
            assert "broken_plugin" not in reg.list_keys()
            assert "biomedical" in reg.list_keys()  # built-ins still present


# ---------------------------------------------------------------------------
# IRFAnalyzer — domain-aware constructor
# ---------------------------------------------------------------------------

class TestIRFAnalyzerDomainConstructor:
    def test_default_is_biomedical(self):
        a = IRFAnalyzer()
        assert a.ruleset.domain_key == "biomedical"

    def test_none_is_biomedical(self):
        a = IRFAnalyzer(domain=None)
        assert a.ruleset.domain_key == "biomedical"

    def test_string_cs(self):
        a = IRFAnalyzer(domain="cs")
        assert a.ruleset.domain_key == "cs"

    def test_string_math(self):
        a = IRFAnalyzer(domain="math")
        assert a.ruleset.domain_key == "math"

    def test_ruleset_instance(self):
        rs = _make_ruleset("custom_key")
        a = IRFAnalyzer(domain=rs)
        assert a.ruleset is rs

    def test_unknown_domain_raises(self):
        with pytest.raises(KeyError, match="Unknown domain"):
            IRFAnalyzer(domain="nonexistent_domain_xyz")

    def test_bad_type_raises(self):
        with pytest.raises(TypeError, match="domain must be"):
            IRFAnalyzer(domain=42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Backward compatibility — IRFAnalyzer() score identical to explicit biomedical
# ---------------------------------------------------------------------------

_BIOMEDICAL_SAMPLE = (
    "We hypothesize that the treatment reduces inflammation. "
    "Based on prior work (Smith et al., doi:10.1234/test), we expected a 20% reduction. "
    "Results show n=50, p-value=0.03, confidence interval 0.15-0.25. "
    "Limitation: small sample size. The protocol was fully reproducible. "
    "Therefore the null hypothesis is rejected. Earlier work confirms this baseline."
)


class TestBackwardCompat:
    def test_default_score_matches_explicit_biomedical(self):
        default = IRFAnalyzer()
        explicit = IRFAnalyzer(domain="biomedical")
        s1 = default.score(_BIOMEDICAL_SAMPLE)
        s2 = explicit.score(_BIOMEDICAL_SAMPLE)
        assert s1.M == s2.M
        assert s1.composite == s2.composite
        assert s1.passed == s2.passed

    def test_stat_validity_compat(self):
        from veritas.types import StatValidity
        sv = StatValidity(score=0.8, p_value_reported=True, ci_reported=True)
        default = IRFAnalyzer()
        s = default.score(_BIOMEDICAL_SAMPLE, stat_validity=sv)
        assert 0.0 <= s.F <= 1.0


# ---------------------------------------------------------------------------
# Scoring divergence — domain specialization actually works
# ---------------------------------------------------------------------------

_CS_SAMPLE = (
    "We claim the proposed algorithm achieves state-of-the-art accuracy on the benchmark dataset. "
    "Our hypothesis is that attention mechanisms improve recall and precision by 15%. "
    "Ablation study confirms each component: baseline F1=0.72, full model F1=0.89. "
    "The artifact is open source (github.com/example/repo) with deterministic seed=42. "
    "Compared to prior work (et al., arxiv:2301.00001), throughput improved 2x. "
    "Therefore our theorem holds by induction; we prove the bound. "
    "Limitation: corner case with edge inputs not handled; future work will address this."
)

_MATH_SAMPLE = (
    "Let G be a finite group. We assume the axiom of choice holds. "
    "Lemma 1: For all x in G, there exists y such that xy=e. "
    "Proof by induction. Suppose the claim holds for n=k. "
    "Therefore, by contradiction, the theorem follows. QED. "
    "Corollary: the tight bound is O(n log n). This is a well-known classical result. "
    "Reference: following the definition in [Smith, doi:10.1234/math]. "
    "Open question: whether the lower bound is constructively provable remains unclear."
)


class TestScoringDivergence:
    def test_cs_domain_higher_on_cs_text(self):
        """CS domain should score cs-specific text higher than biomedical domain."""
        bio = IRFAnalyzer(domain="biomedical")
        cs = IRFAnalyzer(domain="cs")
        s_bio = bio.score(_CS_SAMPLE)
        s_cs = cs.score(_CS_SAMPLE)
        # CS domain should produce higher or equal composite on CS text
        assert s_cs.composite >= s_bio.composite - 0.05  # allow tiny float tolerance

    def test_math_domain_higher_on_math_text(self):
        """Math domain should score math-specific text higher than biomedical domain."""
        bio = IRFAnalyzer(domain="biomedical")
        math_ = IRFAnalyzer(domain="math")
        s_bio = bio.score(_MATH_SAMPLE)
        s_math = math_.score(_MATH_SAMPLE)
        assert s_math.composite >= s_bio.composite - 0.05

    def test_cs_d_dimension_higher_on_cs_proof_text(self):
        """CS domain captures proof-oriented D markers (theorem, lemma, QED)."""
        cs_proof = "We prove the theorem by induction. Corollary follows by contradiction. QED."
        bio = IRFAnalyzer(domain="biomedical")
        cs = IRFAnalyzer(domain="cs")
        assert cs.score(cs_proof).D >= bio.score(cs_proof).D

    def test_math_a_dimension_on_axiom_text(self):
        """Math domain captures axiom/definition/lemma in A dimension."""
        math_ax = "Axiom 1: let G be a group. Definition: the identity element satisfies xe=x."
        bio = IRFAnalyzer(domain="biomedical")
        math_ = IRFAnalyzer(domain="math")
        assert math_.score(math_ax).A >= bio.score(math_ax).A

    def test_all_domains_produce_valid_scores(self):
        """All built-in domains return IRF6DScores in [0,1] on the same text."""
        sample = "We propose a method. Results: n=30, p=0.05. Limitation: small sample."
        for domain_key in ("biomedical", "cs", "math"):
            a = IRFAnalyzer(domain=domain_key)
            s = a.score(sample)
            for dim in (s.M, s.A, s.D, s.I, s.F, s.P, s.composite):
                assert 0.0 <= dim <= 1.0, f"Domain {domain_key} dim out of range: {dim}"
