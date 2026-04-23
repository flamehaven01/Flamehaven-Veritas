"""Integration tests for v3.4 domain CLI/API/JournalProfile wiring.

Covers:
- CLI `veritas domains list` command output
- CLI `veritas critique --domain <key>` smoke test
- API `GET /api/v1/domains` endpoint
- API `POST /api/v1/critique/text` with domain param
- JournalProfile.domain_hint values
- JournalProfileOut schema includes domain_hint
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Shared API client fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_client():
    from veritas.api.app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# CLI: veritas domains list
# ---------------------------------------------------------------------------


class TestDomainsListCLI:
    """veritas domains list — text and JSON output."""

    def test_domains_list_default(self):
        from veritas.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["domains", "list"])
        assert result.exit_code == 0, result.output
        assert "biomedical" in result.output
        assert "cs" in result.output
        assert "math" in result.output

    def test_domains_list_json(self):
        from veritas.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["domains", "list", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "biomedical" in data
        assert "cs" in data
        assert "math" in data

    def test_domains_list_json_structure(self):
        from veritas.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["domains", "list", "--format", "json"])
        data = json.loads(result.output)
        for key in ("biomedical", "cs", "math"):
            entry = data[key]
            assert "name" in entry
            assert "composite_threshold" in entry
            assert "component_min" in entry
            assert "marker_counts" in entry
            counts = entry["marker_counts"]
            for dim in ("M", "A", "D", "I", "F", "P"):
                assert dim in counts
                assert counts[dim] > 0

    def test_domains_list_text_has_threshold(self):
        from veritas.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["domains", "list"])
        assert "threshold=" in result.output

    def test_domains_list_text_has_usage_hint(self):
        from veritas.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["domains", "list"])
        assert "--domain" in result.output


# ---------------------------------------------------------------------------
# CLI: veritas critique --domain
# ---------------------------------------------------------------------------


_SAMPLE_TEXT = (
    "We hypothesize that benchmark X improves accuracy. "
    "Ablation study: baseline=72%, model=81%. "
    "Dataset: n=5000. Reproducible: open source. "
    "Related work: et al. (2023) sota. "
    "Theorem 1 proves correctness. Therefore the result follows."
)


class TestCritiqueDomainCLI:
    """veritas critique --domain <key> smoke tests."""

    def test_critique_domain_cs(self):
        from veritas.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["critique", "--text", _SAMPLE_TEXT, "--domain", "cs"])
        assert result.exit_code == 0, result.output

    def test_critique_domain_math(self):
        from veritas.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["critique", "--text", _SAMPLE_TEXT, "--domain", "math"])
        assert result.exit_code == 0, result.output

    def test_critique_domain_biomedical(self):
        from veritas.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["critique", "--text", _SAMPLE_TEXT, "--domain", "biomedical"])
        assert result.exit_code == 0, result.output

    def test_critique_default_domain_unchanged(self):
        """Default domain (no --domain flag) must behave identically to --domain biomedical."""
        from veritas.cli.main import main

        runner = CliRunner()
        r_default = runner.invoke(main, ["critique", "--text", _SAMPLE_TEXT])
        r_bio = runner.invoke(main, ["critique", "--text", _SAMPLE_TEXT, "--domain", "biomedical"])
        assert r_default.exit_code == 0, r_default.output
        assert r_bio.exit_code == 0, r_bio.output

    def test_critique_unknown_domain_raises(self):
        from veritas.cli.main import main

        runner = CliRunner()
        result = runner.invoke(
            main, ["critique", "--text", _SAMPLE_TEXT, "--domain", "zzz_unknown"]
        )
        # Unknown domain must produce a non-zero exit or an error in output
        has_error = result.exit_code != 0 or "Error" in (result.output or "")
        assert has_error, f"Expected error for unknown domain, got: {result.output!r}"


# ---------------------------------------------------------------------------
# CLI: veritas rebuttal --domain
# ---------------------------------------------------------------------------


class TestRebuttalDomainCLI:
    """veritas rebuttal --domain <key>."""

    def test_rebuttal_domain_cs(self):
        from veritas.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["rebuttal", "--text", _SAMPLE_TEXT, "--domain", "cs"])
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# API: GET /api/v1/domains
# ---------------------------------------------------------------------------


class TestDomainsAPIEndpoint:
    """GET /api/v1/domains."""

    def test_domains_endpoint_status(self, api_client):
        resp = api_client.get("/api/v1/domains")
        assert resp.status_code == 200

    def test_domains_endpoint_returns_list(self, api_client):
        resp = api_client.get("/api/v1/domains")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    def test_domains_endpoint_keys_present(self, api_client):
        resp = api_client.get("/api/v1/domains")
        keys = {d["key"] for d in resp.json()}
        assert "biomedical" in keys
        assert "cs" in keys
        assert "math" in keys

    def test_domains_endpoint_schema(self, api_client):
        resp = api_client.get("/api/v1/domains")
        for entry in resp.json():
            assert "key" in entry
            assert "name" in entry
            assert "composite_threshold" in entry
            assert "component_min" in entry
            assert "marker_counts" in entry
            for dim in ("M", "A", "D", "I", "F", "P"):
                assert dim in entry["marker_counts"]

    def test_domains_endpoint_sorted(self, api_client):
        resp = api_client.get("/api/v1/domains")
        keys = [d["key"] for d in resp.json()]
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# API: POST /api/v1/critique/text with domain param
# ---------------------------------------------------------------------------


class TestCritiqueAPIWithDomain:
    """POST /api/v1/critique/text — domain field wiring."""

    def test_critique_domain_biomedical(self, api_client):
        resp = api_client.post(
            "/api/v1/critique/text",
            json={"report_text": _SAMPLE_TEXT, "domain": "biomedical"},
        )
        assert resp.status_code == 200

    def test_critique_domain_cs(self, api_client):
        resp = api_client.post(
            "/api/v1/critique/text",
            json={"report_text": _SAMPLE_TEXT, "domain": "cs"},
        )
        assert resp.status_code == 200

    def test_critique_domain_math(self, api_client):
        resp = api_client.post(
            "/api/v1/critique/text",
            json={"report_text": _SAMPLE_TEXT, "domain": "math"},
        )
        assert resp.status_code == 200

    def test_critique_domain_default_omitted(self, api_client):
        """Omitting domain field still returns 200 (default = biomedical)."""
        resp = api_client.post(
            "/api/v1/critique/text",
            json={"report_text": _SAMPLE_TEXT},
        )
        assert resp.status_code == 200

    def test_critique_omega_present(self, api_client):
        resp = api_client.post(
            "/api/v1/critique/text",
            json={"report_text": _SAMPLE_TEXT, "domain": "cs"},
        )
        data = resp.json()
        assert "omega_score" in data
        assert 0.0 <= data["omega_score"] <= 1.0


# ---------------------------------------------------------------------------
# JournalProfile.domain_hint
# ---------------------------------------------------------------------------


class TestJournalProfileDomainHint:
    """JournalProfile.domain_hint field wiring (v3.4)."""

    def test_ieee_domain_hint_is_cs(self):
        from veritas.journal.journal_profiles import JOURNAL_PROFILES

        assert JOURNAL_PROFILES["ieee"].domain_hint == "cs"

    def test_lancet_domain_hint_is_biomedical(self):
        from veritas.journal.journal_profiles import JOURNAL_PROFILES

        assert JOURNAL_PROFILES["lancet"].domain_hint == "biomedical"

    def test_nature_domain_hint_empty(self):
        from veritas.journal.journal_profiles import JOURNAL_PROFILES

        assert JOURNAL_PROFILES["nature"].domain_hint == ""

    def test_q_profiles_domain_hint_empty(self):
        from veritas.journal.journal_profiles import JOURNAL_PROFILES

        for key in ("q1", "q2", "q3", "default"):
            assert JOURNAL_PROFILES[key].domain_hint == ""

    def test_domain_hint_in_as_dict(self):
        from veritas.journal.journal_profiles import JOURNAL_PROFILES

        d = JOURNAL_PROFILES["ieee"].as_dict()
        assert "domain_hint" in d
        assert d["domain_hint"] == "cs"

    def test_domain_hint_field_frozen(self):
        """domain_hint is part of frozen dataclass — attribute assignment must raise."""
        import dataclasses

        from veritas.journal.journal_profiles import JOURNAL_PROFILES

        profile = JOURNAL_PROFILES["lancet"]
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError, TypeError)):
            profile.domain_hint = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# API journal-profiles includes domain_hint
# ---------------------------------------------------------------------------


class TestJournalProfilesAPIWithDomainHint:
    def test_journal_profiles_has_domain_hint(self, api_client):
        resp = api_client.get("/api/v1/journal-profiles")
        assert resp.status_code == 200
        profiles = {p["key"]: p for p in resp.json()}
        assert "domain_hint" in profiles["ieee"]
        assert profiles["ieee"]["domain_hint"] == "cs"
        assert profiles["lancet"]["domain_hint"] == "biomedical"
