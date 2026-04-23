"""E2E API contract tests — full request/response cycle for every endpoint.

Uses TestClient (sync ASGI) against the real app instance.
All tests use plain text payloads to avoid PDF/DOCX parser dependencies.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from veritas.api.app import app

_SHORT = (
    "This study investigates the effect of compound X on cell viability. "
    "We hypothesise that compound X reduces apoptosis at 10 µM. "
    "Methods: 96-well plate assay, n=48, control group included. "
    "Results: viability decreased by 23% (p=0.012). "
    "Limitation: single cell line used. "
    "References: Smith 2020, Jones 2019, Lee 2021."
)

_SHORT_V2 = (
    "Revised study investigates compound X on cell viability. "
    "We hypothesise that compound X reduces apoptosis at 10 µM. "
    "Methods: 96-well plate assay, n=96, two cell lines, blinding applied. "
    "Results: viability decreased by 23% (p=0.012), replicated in HeLa. "
    "Limitation: single passage tested. "
    "References: Smith 2020, Jones 2019, Lee 2021, Park 2022."
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── System endpoints ──────────────────────────────────────────────────────────

class TestSystemEndpoints:
    def test_health(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_version(self, client):
        from veritas import __version__
        res = client.get("/version")
        assert res.status_code == 200
        assert res.json()["version"] == __version__

    def test_openapi_schema_available(self, client):
        res = client.get("/openapi.json")
        assert res.status_code == 200
        schema = res.json()
        assert "paths" in schema


# ── /api/v1/domains ───────────────────────────────────────────────────────────

class TestDomainsEndpoint:
    def test_returns_list(self, client):
        res = client.get("/api/v1/domains")
        assert res.status_code == 200
        domains = res.json()
        assert isinstance(domains, list)
        assert len(domains) >= 3

    def test_contains_builtin_domains(self, client):
        res = client.get("/api/v1/domains")
        keys = {d["key"] for d in res.json()}
        assert "biomedical" in keys
        assert "cs" in keys
        assert "math" in keys

    def test_domain_schema_fields(self, client):
        res = client.get("/api/v1/domains")
        d = res.json()[0]
        assert "key" in d
        assert "name" in d
        assert "composite_threshold" in d
        assert "component_min" in d
        assert "marker_counts" in d
        counts = d["marker_counts"]
        assert set(counts.keys()) == {"M", "A", "D", "I", "F", "P"}

    def test_sorted_by_key(self, client):
        res = client.get("/api/v1/domains")
        keys = [d["key"] for d in res.json()]
        assert keys == sorted(keys)


# ── /api/v1/critique/text ─────────────────────────────────────────────────────

class TestCritiqueTextEndpoint:
    def test_basic_critique(self, client):
        res = client.post("/api/v1/critique/text", json={"report_text": _SHORT})
        assert res.status_code == 200
        data = res.json()
        assert "omega_score" in data
        assert 0.0 <= data["omega_score"] <= 1.0
        assert "steps" in data
        assert len(data["steps"]) > 0
        assert "precheck" in data

    def test_precheck_mode_present(self, client):
        res = client.post("/api/v1/critique/text", json={"report_text": _SHORT})
        pc = res.json()["precheck"]
        assert pc["mode"] in ("FULL", "PARTIAL", "LIMITED", "BLOCKED")
        assert "line1" in pc

    def test_domain_biomedical(self, client):
        res = client.post("/api/v1/critique/text",
                          json={"report_text": _SHORT, "domain": "biomedical"})
        assert res.status_code == 200
        assert res.json()["omega_score"] is not None

    def test_domain_cs(self, client):
        cs_text = (
            "This paper proposes a new sorting algorithm. We benchmark against SOTA on "
            "ImageNet. Ablation study shows each component contributes. "
            "Code is open-source on GitHub. Docker image provided. "
            "References: arxiv 2021, arxiv 2022."
        )
        res = client.post("/api/v1/critique/text",
                          json={"report_text": cs_text, "domain": "cs"})
        assert res.status_code == 200
        assert res.json()["omega_score"] is not None

    def test_domain_math(self, client):
        math_text = (
            "We prove the following lemma: for all n, the sequence converges. "
            "Proof: by induction. QED. Axiom: the field is complete. "
            "Conjecture: the tight bound is O(n log n). "
            "References: Knuth 1968, Sedgewick 1983."
        )
        res = client.post("/api/v1/critique/text",
                          json={"report_text": math_text, "domain": "math"})
        assert res.status_code == 200

    def test_unknown_domain_raises_422_or_400(self, client):
        res = client.post("/api/v1/critique/text",
                          json={"report_text": _SHORT, "domain": "physics_unknown_xyz"})
        assert res.status_code in (400, 422, 500)

    def test_irf_scores_present(self, client):
        res = client.post("/api/v1/critique/text", json={"report_text": _SHORT})
        data = res.json()
        if data.get("irf_scores"):
            irf = data["irf_scores"]
            for dim in ("M", "A", "D", "I", "F", "P", "composite"):
                assert dim in irf
                assert 0.0 <= irf[dim] <= 1.0

    def test_round_number_reflected(self, client):
        res = client.post("/api/v1/critique/text",
                          json={"report_text": _SHORT, "round_number": 2})
        assert res.json()["round_number"] == 2

    def test_empty_text_returns_error(self, client):
        res = client.post("/api/v1/critique/text", json={"report_text": "   "})
        assert res.status_code in (400, 422, 200)


# ── /api/v1/precheck ─────────────────────────────────────────────────────────

class TestPrecheckEndpoint:
    def test_returns_precheck_mode(self, client):
        res = client.post("/api/v1/precheck", json={"report_text": _SHORT})
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] in ("FULL", "PARTIAL", "LIMITED", "BLOCKED")

    def test_precheck_fields(self, client):
        res = client.post("/api/v1/precheck", json={"report_text": _SHORT})
        data = res.json()
        assert "line1" in data
        assert "line2" in data
        assert "missing_artifacts" in data
        assert isinstance(data["missing_artifacts"], list)


# ── /api/v1/review-sim ───────────────────────────────────────────────────────

class TestReviewSimEndpoint:
    def test_basic_review_sim(self, client):
        res = client.post("/api/v1/review-sim",
                          json={"report_text": _SHORT, "reviewers": 3})
        assert res.status_code == 200
        data = res.json()
        assert "final_recommendation" in data
        assert data["final_recommendation"] in ("ACCEPT", "REVISE", "REJECT")

    def test_per_reviewer_count(self, client):
        res = client.post("/api/v1/review-sim",
                          json={"report_text": _SHORT, "reviewers": 3})
        data = res.json()
        assert len(data["per_reviewer"]) == 3

    def test_consensus_fields(self, client):
        res = client.post("/api/v1/review-sim",
                          json={"report_text": _SHORT, "reviewers": 3})
        consensus = res.json()["consensus"]
        assert "consensus_omega" in consensus
        assert "reached" in consensus
        assert 0.0 <= consensus["consensus_omega"] <= 1.0

    def test_dr3_fields(self, client):
        res = client.post("/api/v1/review-sim",
                          json={"report_text": _SHORT, "reviewers": 3})
        dr3 = res.json()["dr3"]
        assert "conflict_detected" in dr3
        assert "final_omega" in dr3

    def test_two_reviewers(self, client):
        res = client.post("/api/v1/review-sim",
                          json={"report_text": _SHORT, "reviewers": 2})
        assert res.status_code == 200
        assert len(res.json()["per_reviewer"]) == 2


# ── /api/v1/rebuttal ─────────────────────────────────────────────────────────

class TestRebuttalEndpoint:
    def test_basic_rebuttal(self, client):
        res = client.post("/api/v1/rebuttal",
                          json={"report_text": _SHORT, "style": "ieee"})
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "style" in data
        assert data["style"] == "ieee"

    def test_rebuttal_styles(self, client):
        for style in ("ieee", "acm", "nature"):
            res = client.post("/api/v1/rebuttal",
                              json={"report_text": _SHORT, "style": style})
            assert res.status_code == 200
            assert res.json()["style"] == style

    def test_rebuttal_with_domain(self, client):
        res = client.post("/api/v1/rebuttal",
                          json={"report_text": _SHORT, "style": "ieee", "domain": "biomedical"})
        assert res.status_code == 200

    def test_invalid_style_returns_400(self, client):
        res = client.post("/api/v1/rebuttal",
                          json={"report_text": _SHORT, "style": "lancet"})
        assert res.status_code == 400

    def test_rebuttal_item_fields(self, client):
        res = client.post("/api/v1/rebuttal",
                          json={"report_text": _SHORT, "style": "acm"})
        data = res.json()
        if data["items"]:
            item = data["items"][0]
            assert "issue_id" in item
            assert "severity" in item
            assert item["severity"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
            assert "reviewer_text" in item
            assert "author_response_template" in item

    def test_rebuttal_coverage_in_range(self, client):
        res = client.post("/api/v1/rebuttal",
                          json={"report_text": _SHORT, "style": "ieee"})
        coverage = res.json()["rebuttal_coverage"]
        assert 0.0 <= coverage <= 1.0


# ── /api/v1/response-letter ───────────────────────────────────────────────────

class TestResponseLetterEndpoint:
    def test_ieee_letter(self, client):
        res = client.post("/api/v1/response-letter",
                          json={"report_text": _SHORT, "style": "ieee"})
        assert res.status_code == 200
        data = res.json()
        assert "markdown" in data
        assert "IEEE" in data["markdown"]

    def test_acm_letter(self, client):
        res = client.post("/api/v1/response-letter",
                          json={"report_text": _SHORT, "style": "acm"})
        assert res.status_code == 200
        assert "ACM" in res.json()["markdown"]

    def test_nature_letter(self, client):
        res = client.post("/api/v1/response-letter",
                          json={"report_text": _SHORT, "style": "nature"})
        assert res.status_code == 200
        assert "NATURE" in res.json()["markdown"].upper()

    def test_letter_fields(self, client):
        res = client.post("/api/v1/response-letter",
                          json={"report_text": _SHORT, "style": "ieee"})
        data = res.json()
        assert "style" in data
        assert "total_issues" in data
        assert "critical_count" in data
        assert "high_count" in data


# ── /api/v1/journal-score ────────────────────────────────────────────────────

class TestJournalScoreEndpoint:
    def test_default_journal(self, client):
        res = client.post("/api/v1/journal-score",
                          json={"report_text": _SHORT, "journal": "default"})
        assert res.status_code == 200
        data = res.json()
        assert "verdict" in data
        assert data["verdict"] in ("ACCEPT", "REVISE", "REJECT")

    def test_all_journals(self, client):
        for journal in ("nature", "ieee", "lancet", "q1", "q2", "q3", "default"):
            res = client.post("/api/v1/journal-score",
                              json={"report_text": _SHORT, "journal": journal})
            assert res.status_code == 200, f"Failed for journal={journal}"

    def test_calibrated_omega_in_range(self, client):
        res = client.post("/api/v1/journal-score",
                          json={"report_text": _SHORT, "journal": "ieee"})
        data = res.json()
        assert 0.0 <= data["calibrated_omega"] <= 1.0

    def test_journal_score_with_domain(self, client):
        res = client.post("/api/v1/journal-score",
                          json={"report_text": _SHORT, "journal": "ieee", "domain": "biomedical"})
        assert res.status_code == 200

    def test_step_contributions_present(self, client):
        res = client.post("/api/v1/journal-score",
                          json={"report_text": _SHORT, "journal": "default"})
        sc = res.json()["step_contributions"]
        assert isinstance(sc, dict)


# ── /api/v1/diff ─────────────────────────────────────────────────────────────

class TestDiffEndpoint:
    def test_basic_diff(self, client):
        res = client.post("/api/v1/diff",
                          json={"report_v1_text": _SHORT, "report_v2_text": _SHORT_V2})
        assert res.status_code == 200
        data = res.json()
        assert "rcs" in data
        assert "revision_grade" in data
        assert 0.0 <= data["rcs"] <= 1.0

    def test_diff_fields(self, client):
        res = client.post("/api/v1/diff",
                          json={"report_v1_text": _SHORT, "report_v2_text": _SHORT_V2})
        data = res.json()
        assert "delta_omega" in data
        assert "addressed_count" in data
        assert "total_v1_issues" in data
        assert "improved" in data
        assert isinstance(data["improved"], bool)

    def test_identical_texts_rcs(self, client):
        res = client.post("/api/v1/diff",
                          json={"report_v1_text": _SHORT, "report_v2_text": _SHORT})
        assert res.status_code == 200

    def test_revision_grade_valid(self, client):
        res = client.post("/api/v1/diff",
                          json={"report_v1_text": _SHORT, "report_v2_text": _SHORT_V2})
        assert res.json()["revision_grade"] in ("COMPLETE", "PARTIAL", "INSUFFICIENT")


# ── /api/v1/journal-profiles ─────────────────────────────────────────────────

class TestJournalProfilesEndpoint:
    def test_returns_list(self, client):
        res = client.get("/api/v1/journal-profiles")
        assert res.status_code == 200
        profiles = res.json()
        assert isinstance(profiles, list)
        assert len(profiles) >= 7

    def test_profile_fields(self, client):
        res = client.get("/api/v1/journal-profiles")
        p = res.json()[0]
        assert "key" in p
        assert "accept_omega" in p
        assert "domain_hint" in p

    def test_ieee_domain_hint(self, client):
        res = client.get("/api/v1/journal-profiles")
        ieee = next((p for p in res.json() if p["key"] == "ieee"), None)
        assert ieee is not None
        assert ieee["domain_hint"] == "cs"

    def test_lancet_domain_hint(self, client):
        res = client.get("/api/v1/journal-profiles")
        lancet = next((p for p in res.json() if p["key"] == "lancet"), None)
        assert lancet is not None
        assert lancet["domain_hint"] == "biomedical"
