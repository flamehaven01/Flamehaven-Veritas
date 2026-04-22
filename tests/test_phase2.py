"""Tests for Phase 2 modules: MICA session, CR-EP governance, RAG retriever, auto-template."""

from __future__ import annotations

import json
import pathlib
import tempfile

import pytest

# ── BM25 tests ─────────────────────────────────────────────────────────────────


class TestBM25:
    def _make_bm25(self):
        from veritas.rag.retriever import BM25

        bm = BM25()
        bm.fit(["the cat sat on the mat", "the dog ran in the park", "cat and dog are pets"])
        return bm

    def test_fit_sets_corpus_size(self):
        bm = self._make_bm25()
        assert bm.corpus_size == 3

    def test_fit_sets_avgdl(self):
        bm = self._make_bm25()
        assert bm.avgdl > 0

    def test_score_returns_positive_for_matching(self):
        bm = self._make_bm25()
        s = bm.score("cat", 0)
        assert s > 0

    def test_score_zero_for_empty_avgdl(self):
        from veritas.rag.retriever import BM25

        bm = BM25()
        assert bm.score("cat", 0) == 0.0

    def test_search_returns_sorted_results(self):
        bm = self._make_bm25()
        results = bm.search("cat", top_k=3)
        assert len(results) > 0
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_top_k_limit(self):
        bm = self._make_bm25()
        results = bm.search("cat", top_k=1)
        assert len(results) <= 1

    def test_tokenize_lowercase(self):
        from veritas.rag.retriever import BM25

        tokens = BM25._tokenize("Hello World TEST")
        assert all(t == t.lower() for t in tokens)

    def test_nonmatching_query_gives_empty(self):
        bm = self._make_bm25()
        results = bm.search("zzzzunknownzzz", top_k=5)
        assert results == []


# ── RRF fusion tests ───────────────────────────────────────────────────────────


class TestRRF:
    def test_basic_fusion(self):
        from veritas.rag.retriever import rrf_fusion

        r1 = [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.5}]
        r2 = [{"id": "b", "score": 0.8}, {"id": "c", "score": 0.3}]
        out = rrf_fusion([r1, r2], k=60, top_k=3)
        ids = [x["id"] for x in out]
        assert "b" in ids  # appears in both lists → higher fused score

    def test_rrf_score_highest_for_consensus(self):
        from veritas.rag.retriever import rrf_fusion

        r1 = [{"id": "x", "score": 1.0}]
        r2 = [{"id": "x", "score": 1.0}]
        out = rrf_fusion([r1, r2], k=60, top_k=1)
        assert out[0]["id"] == "x"
        assert out[0]["rrf_score"] > 1 / 61  # sum of two 1/(60+1)

    def test_top_k_respected(self):
        from veritas.rag.retriever import rrf_fusion

        r1 = [{"id": i, "score": 1.0 / (i + 1)} for i in range(10)]
        out = rrf_fusion([r1], k=60, top_k=3)
        assert len(out) <= 3

    def test_empty_lists(self):
        from veritas.rag.retriever import rrf_fusion

        out = rrf_fusion([[], []], k=60, top_k=5)
        assert out == []


# ── chunk_text tests ───────────────────────────────────────────────────────────


class TestChunkText:
    def test_empty_returns_empty(self):
        from veritas.rag.retriever import chunk_text

        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_short_text_single_chunk(self):
        from veritas.rag.retriever import chunk_text

        chunks = chunk_text("This is a short text.", max_tokens=512)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "This is a short text."

    def test_chunk_dict_has_required_keys(self):
        from veritas.rag.retriever import chunk_text

        chunks = chunk_text("Hello world.")
        assert "text" in chunks[0]
        assert "pages" in chunks[0]
        assert "headings" in chunks[0]

    def test_heading_is_captured(self):
        from veritas.rag.retriever import chunk_text

        text = "# Introduction\nThis is the intro.\n\n## Methods\nHere are methods."
        chunks = chunk_text(text, max_tokens=512)
        all_headings = [h for c in chunks for h in c["headings"]]
        assert "Introduction" in all_headings or "Methods" in all_headings

    def test_long_text_splits(self):
        from veritas.rag.retriever import chunk_text

        long_text = " ".join(["word"] * 2000)
        chunks = chunk_text(long_text, max_tokens=100)
        assert len(chunks) > 1


# ── SciExpRetriever integration ────────────────────────────────────────────────


class TestSciExpRetriever:
    def test_index_returns_count(self):
        from veritas.rag.retriever import SciExpRetriever

        r = SciExpRetriever()
        n = r.index("The cat sat on the mat. A dog ran in the park.")
        assert n >= 1

    def test_retrieve_returns_list(self):
        from veritas.rag.retriever import SciExpRetriever

        r = SciExpRetriever()
        r.index("Hypothesis: X causes Y. Methods: RCT design. Results: p<0.05.")
        hits = r.retrieve("hypothesis")
        assert isinstance(hits, list)

    def test_retrieve_empty_before_index(self):
        from veritas.rag.retriever import SciExpRetriever

        r = SciExpRetriever()
        assert r.retrieve("anything") == []

    def test_build_context_returns_string(self):
        from veritas.rag.retriever import SciExpRetriever

        r = SciExpRetriever()
        r.index("The experiment tested drug A against placebo. Outcome: significant.")
        ctx = r.build_context("drug experiment")
        assert isinstance(ctx, str)
        assert len(ctx) > 0


# ── MICA session tests ─────────────────────────────────────────────────────────


class TestMICAStore:
    def test_start_creates_files(self, tmp_path):
        from veritas.session.mica_store import MICAStore

        store = MICAStore(tmp_path)
        state = store.start()
        assert state == "INVOCATION_MODE"
        assert (tmp_path / "memory" / "mica.yaml").exists()
        assert (tmp_path / "memory" / "archive.mica.latest.json").exists()

    def test_show_inactive_before_start(self, tmp_path):
        from veritas.session.mica_store import MICAStore

        store = MICAStore(tmp_path)
        status = store.show()
        assert status.state == "INACTIVE"

    def test_show_active_after_start(self, tmp_path):
        from veritas.session.mica_store import MICAStore

        store = MICAStore(tmp_path)
        store.start()
        status = store.show()
        assert status.state == "INVOCATION_MODE"
        assert status.contract == "CLOSED"

    def test_log_di_violation_persists(self, tmp_path):
        from veritas.session.mica_store import DIViolation, MICAStore

        store = MICAStore(tmp_path)
        store.start()
        store.log_di_violation(DIViolation(origin_episode="test episode", lesson_ref="ref-001"))
        archive = json.loads((tmp_path / "memory" / "archive.mica.latest.json").read_text())
        assert len(archive["design_invariants"]) == 1

    def test_close_writes_timestamp(self, tmp_path):
        from veritas.session.mica_store import MICAStore

        store = MICAStore(tmp_path)
        store.start()
        store.close()
        archive = json.loads((tmp_path / "memory" / "archive.mica.latest.json").read_text())
        assert archive["session_closed"] is not None

    def test_count_invariants(self):
        from veritas.session.mica_store import count_invariants

        archive = {
            "design_invariants": [
                {"severity": "critical", "origin_episode": "x"},
                {"severity": "high", "origin_episode": "y"},
                {"severity": "low", "origin_episode": "z"},
            ]
        }
        crit, high, normalized = count_invariants(archive)
        assert crit == 1
        assert high == 1
        assert len(normalized) == 3

    def test_detect_state_inactive(self, tmp_path):
        from veritas.session.mica_store import detect_state

        state, yaml_p, _ = detect_state(tmp_path)
        assert state == "INACTIVE"
        assert yaml_p is None


# ── CR-EP gate tests ───────────────────────────────────────────────────────────


class TestCREPGate:
    def test_detect_state_init_when_no_dir(self, tmp_path):
        from veritas.governance.cr_ep_gate import detect_state

        assert detect_state(tmp_path) == "INIT"

    def test_bootstrap_creates_dir(self, tmp_path):
        from veritas.governance.cr_ep_gate import bootstrap

        state = bootstrap(tmp_path)
        assert (tmp_path / ".cr-ep" / "session.json").exists()
        assert state != "INIT"

    def test_bootstrap_nano_profile(self, tmp_path):
        from veritas.governance.cr_ep_gate import bootstrap

        bootstrap(tmp_path, profile="nano")
        assert (tmp_path / ".cr-ep" / "session.json").exists()
        assert not (tmp_path / ".cr-ep" / "why_gate.json").exists()

    def test_append_and_read_log(self, tmp_path):
        from veritas.governance.cr_ep_gate import append_event, bootstrap, read_log

        bootstrap(tmp_path)  # creates session.json + initial log
        append_event(tmp_path, "STATE_VIOLATION", "test reason")
        events = read_log(tmp_path)
        assert len(events) >= 2
        event_types = [e["event_type"] for e in events]
        assert "STATE_VIOLATION" in event_types

    def test_validate_artifacts_no_errors_after_bootstrap(self, tmp_path):
        from veritas.governance.cr_ep_gate import bootstrap, validate_artifacts

        bootstrap(tmp_path, profile="standard")
        errors = validate_artifacts(tmp_path)
        assert errors == []

    def test_validate_missing_dir(self, tmp_path):
        from veritas.governance.cr_ep_gate import validate_artifacts

        errors = validate_artifacts(tmp_path)
        assert any("Missing" in e for e in errors)

    def test_check_violations_detects_illegal_state(self, tmp_path):
        from veritas.governance.cr_ep_gate import bootstrap, check_violations

        bootstrap(tmp_path, profile="full")
        # Remove why_gate.json to simulate illegal state
        (tmp_path / ".cr-ep" / "why_gate.json").unlink()
        errs = check_violations(tmp_path)
        assert any("scope_declaration" in e for e in errs)

    def test_state_order_list_complete(self):
        from veritas.governance.cr_ep_gate import STATE_ORDER

        assert "INIT" in STATE_ORDER
        assert "CLOSED" in STATE_ORDER
        assert STATE_ORDER.index("INIT") < STATE_ORDER.index("CLOSED")


# ── Auto-template tests ────────────────────────────────────────────────────────


class TestAutoTemplate:
    def _make_report(self, ec):
        from veritas.precheck import run as precheck_run
        from veritas.types import CritiqueReport, ExperimentClass

        pc = precheck_run("Abstract: Test.")
        return CritiqueReport(precheck=pc, experiment_class=ec)

    def test_rca_maps_to_ku(self):
        from veritas.templates.base import select_template
        from veritas.types import ExperimentClass

        r = self._make_report(ExperimentClass.RCA)
        assert select_template(r) == "ku"

    def test_ablation_maps_to_ku(self):
        from veritas.templates.base import select_template
        from veritas.types import ExperimentClass

        r = self._make_report(ExperimentClass.ABLATION)
        assert select_template(r) == "ku"

    def test_parity_maps_to_bmj(self):
        from veritas.templates.base import select_template
        from veritas.types import ExperimentClass

        r = self._make_report(ExperimentClass.PARITY)
        assert select_template(r) == "bmj"

    def test_extension_maps_to_bmj(self):
        from veritas.templates.base import select_template
        from veritas.types import ExperimentClass

        r = self._make_report(ExperimentClass.EXTENSION)
        assert select_template(r) == "bmj"

    def test_multiaxis_maps_to_bmj(self):
        from veritas.templates.base import select_template
        from veritas.types import ExperimentClass

        r = self._make_report(ExperimentClass.MULTIAXIS)
        assert select_template(r) == "bmj"

    def test_none_class_maps_to_bmj(self):
        from veritas.templates.base import select_template

        r = self._make_report(None)
        assert select_template(r) == "bmj"


# ── CLI version + new commands ────────────────────────────────────────────────


class TestVersion250:
    def test_version_flag(self):
        from click.testing import CliRunner

        from veritas.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert "2.5" in result.output

    def test_session_start(self, tmp_path):
        from click.testing import CliRunner

        from veritas.cli.main import main

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["session", "start"])
            assert result.exit_code == 0
            assert "MICA session started" in result.output

    def test_session_show(self, tmp_path):
        from click.testing import CliRunner

        from veritas.cli.main import main

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(main, ["session", "start"])
            result = runner.invoke(main, ["session", "show"])
            assert result.exit_code == 0
            assert "MICA state" in result.output

    def test_govern_init(self, tmp_path):
        from click.testing import CliRunner

        from veritas.cli.main import main

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["govern", "init"])
            assert result.exit_code == 0
            assert "CR-EP initialized" in result.output

    def test_govern_status(self, tmp_path):
        from click.testing import CliRunner

        from veritas.cli.main import main

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(main, ["govern", "init"])
            result = runner.invoke(main, ["govern", "status"])
            assert result.exit_code == 0
            assert "CR-EP state" in result.output

    def test_govern_log(self, tmp_path):
        from click.testing import CliRunner

        from veritas.cli.main import main

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(main, ["govern", "init"])
            result = runner.invoke(main, ["govern", "log"])
            assert result.exit_code == 0
