# Changelog

All notable changes to **veritas** are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)  
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [3.4.0] - 2026-04-23

### Added

#### Phase 1 — Domain Plugin Subsystem (IRF-6D Domain Architecture)
- `src/veritas/logos/domain/` package — `DomainRuleset` frozen dataclass, `DomainRegistry` singleton,
  `get_domain`, `register_domain`, `list_domain_keys` module-level helpers.
- Three built-in domains:
  - `biomedical` — verbatim migration of prior module-level marker banks (backward-compatible)
  - `cs` — CS/SE markers: benchmark, ablation, SOTA, arxiv, open-source, Docker
  - `math` — Formal math markers: axiom, lemma, QED, conjecture, tight bound
- External plugin support via Python entry_points group `veritas.domains`:
  third-party packages declare `[project.entry-points."veritas.domains"]` in their `pyproject.toml`
  and the domain is loaded automatically on registry init.
- `IRFAnalyzer(domain=None|str|DomainRuleset)` — domain-aware constructor; `None` fast-paths to
  biomedical for full backward compatibility. All existing `IRFAnalyzer()` callers unchanged.
- `LogosBridge(domain)` and `SciExpCritiqueEngine(domain)` — domain threaded end-to-end.
- `tests/test_domain.py` — 39 tests (DomainRuleset, DomainRegistry, entry_points mock,
  IRFAnalyzer constructor, backward compat, CS/math scoring divergence).

#### Phase 2 — CLI + API + JournalProfile Integration
- `veritas critique --domain <key>` — select IRF scoring domain per critique run.
- `veritas rebuttal --domain <key>` — domain-aware rebuttal critique.
- `veritas domains list` — list all registered domains (text + `--format json`).
- CLI domain validation: unknown key raises `ClickException` immediately at `_load_engine()`.
- `GET /api/v1/domains` — returns all registered domains with key, name, thresholds, marker counts.
- `CritiqueRequest.domain`, `RebuttalRequest.domain`, `JournalScoreRequest.domain` fields added.
- `DomainOut` Pydantic schema added to `api/schemas.py`.
- `JournalProfile.domain_hint: str = ""` — hints the preferred IRF domain for each journal:
  `ieee → "cs"`, `lancet → "biomedical"`, `nature/q1/q2/q3/default → ""` (agnostic).
- `JournalProfileOut.domain_hint` field added to REST API response.
- `tests/test_domain_integration.py` — 28 integration tests (CLI + API + JournalProfile.domain_hint).

### Changed
- `api/routes.py` — `critique/text`, `rebuttal`, `journal-score` endpoints now create per-request
  `SciExpCritiqueEngine(domain=req.domain)` instead of sharing the module-level `_engine` singleton.
  Singleton `_engine` kept for non-domain endpoints that do not need per-request domain selection.
- `_load_engine()` in `cli/main.py` now accepts `domain` parameter.

### Stats
- Tests: 575 passing (up from 508 at v3.3.0)
- Coverage: 86.14% (up from 85.44%)
- All CI checks green (ruff, mypy, pytest)

---

## [3.3.0] - 2026-04-23

### Added

#### Phase 1 — Core Rebuttal Engine
- `src/veritas/rebuttal/rebuttal_engine.py` — `RebuttalEngine.generate(report, style)` → `RebuttalReport`.
  Maps each CritiqueReport StepFinding → severity-graded `RebuttalItem` (CRITICAL/HIGH/MEDIUM/LOW)
  with 8 response templates per category. Issue ID format: `R-{step_id}.{finding_index}`.
  Computed properties: `rebuttal_coverage`, `critical_count`, `high_count`.
- `src/veritas/rebuttal/revision_tracker.py` — `RevisionTracker.compare(r1, r2)` → `RevisionResult`.
  Computes `delta_omega`, `addressed_fixes`, `rcs` (Revision Completeness Score).
  Grades: COMPLETE (≥0.80) / PARTIAL (≥0.50) / INSUFFICIENT (<0.50).
- `POST /api/v1/rebuttal` — text → structured RebuttalReport JSON.
- `POST /api/v1/rebuttal-upload` — file upload variant.
- `POST /api/v1/diff` — v1 + v2 text → RevisionResult JSON.
- `veritas rebuttal` CLI command with `--style`, `--format json`, `--render-letter` flags.
- `veritas diff <file1> <file2>` CLI command.
- `tests/test_rebuttal.py` — 52 tests (rebuttal engine + revision tracker).

#### Phase 2 — Journal Profiles + Scorer
- `src/veritas/journal/journal_profiles.py` — 7 built-in journal profiles:
  `nature` (Ω≥0.92), `ieee` (≥0.85), `lancet` (≥0.90), `q1` (≥0.85),
  `q2` (≥0.78), `q3` (≥0.70), `default` (≥0.78).
  Each profile carries per-step multipliers (e.g., `nature` M/F weight × 1.6).
- `src/veritas/journal/journal_scorer.py` — `JournalScorer.score(report, journal)` →
  `JournalScoringResult`. Calibrated omega formula:
  `Σ(q_i × m_i × w_i) / Σ(m_i × w_i)` (q=step quality, m=journal multiplier, w=step weight).
  Verdict: ACCEPT/REVISE/REJECT vs profile thresholds.
- `GET /api/v1/journal-profiles` — returns all profile configs + thresholds.
- `POST /api/v1/journal-score` — text + journal key → calibrated omega + verdict.
- `POST /api/v1/journal-score-upload` — file upload variant.
- `veritas critique --journal <key>` flag for journal-calibrated scoring.
- `veritas journal-profiles` CLI command (table output).
- `tests/test_journal.py` — 49 tests (profiles + scorer + CLI).

#### Phase 3 — Response Letter Renderer + Web UI
- `src/veritas/render/response_letter.py` — `ResponseLetterRenderer.render(report, style)` →
  Markdown response letter. Supports `ieee`, `acm`, `nature` style configs.
  Groups items by severity, formats point-by-point reviewer–response exchanges.
  `render_to_file()` convenience method. Zero new dependencies.
- `POST /api/v1/response-letter` — text + style → full Markdown response letter.
- `veritas rebuttal --render-letter` flag outputs/saves the formatted letter.
- Web UI — new tabs: **Rebuttal Builder** (paste text → severity-grouped items + download letter)
  and **Journal Score** (journal select → calibrated Ω hero + step contribution table).
- `frontend/dist/style.css` — CSS for result tabs (`.result-tabs`, `.rtab`),
  rebuttal items (`.rebuttal-item`, severity badges), journal hero + step table.
- `tests/test_response_letter.py` — 35 tests (renderer, all styles, edge cases, render_to_file).
- `tests/test_integration.py` — 33 tests (end-to-end critique→rebuttal→journal→diff,
  CLI smoke tests, API round-trips, ResponseLetterRenderer × 3 styles).

### Changed
- `src/veritas/api/schemas.py` — added `RebuttalRequest`, `RebuttalResponse`, `DiffRequest`,
  `DiffResponse`, `JournalScoreRequest`, `JournalScoreResponse`, `JournalProfileOut`,
  `ResponseLetterRequest`, `ResponseLetterResponse`.
- `src/veritas/cli/main.py` — added `veritas rebuttal`, `veritas diff`,
  `veritas journal-profiles` commands; added `--journal` flag to `veritas critique`;
  added `--render-letter` flag to `veritas rebuttal`.
- `pyproject.toml` — version bumped `3.2.0 → 3.3.0`.

### Tests
- **508 tests passing** (up from 440 in v3.2.0), **85.44% coverage** (gate: ≥80%).
- SIDRCE Ω = 0.9977 S++ (maintained).

---

## [3.2.0] - 2026-04-23

### Added

#### Multi-Reviewer Peer Simulation (Phase 3 — v3.2.0)
- `src/veritas/reviewer/` — complete peer-review simulation engine:
  - `persona.py` — `PersonaConfig`, `calibrate_omega()`, `STRICT/BALANCED/LENIENT` presets,
    `select_personas(n)`. Calibration formula: `Σ(w_d × irf_d) / Σ(w_d)` per IRF-6D vector.
  - `consensus.py` — `CrossValidator.check_consensus()` with spread-threshold gating (≤ 0.30).
    `ConsensusResult`: mean omega, variance, spread, reached flag, ACCEPT/REVISE/REJECT.
  - `dr3.py` — `DR3Protocol.resolve()` conflict resolution when consensus_omega < 0.60.
    Tiebreaker: BALANCED persona × 0.90 penalty factor.
  - `engine.py` — `ReviewSimEngine.run(text, reviewers)`: runs base critique once, applies
    per-persona calibration, aggregates via CrossValidator + DR3. `ReviewSimResult.render_text()`.
- `POST /api/v1/review-sim` API endpoint with `ReviewSimRequest/Response` Pydantic schemas.
- `veritas review-sim <file>` CLI command (JSON / text output, `--reviewers 2|3`).
- `tests/test_reviewer.py` — 53 tests covering all reviewer package components.

#### React-Compatible Frontend (v3.2.0 UI)
- `frontend/dist/index.html` — tabbed UI: Critique tab + Review Sim tab.
- `frontend/dist/app.js` — clean rewrite (no duplicate code), adds Review Sim panel with
  reviewer cards, CrossValidator consensus display, DR3 conflict banner, final verdict.
- `frontend/dist/style.css` — shared styles served via FastAPI StaticFiles.

#### API & App Fixes
- `src/veritas/api/app.py` — fixed frontend path: `parents[4]` → `parents[3] / "frontend" / "dist"`;
  version bumped `2.1.0 → 3.2.0`.
- `src/veritas/api/schemas.py` — added `ReviewSimRequest`, `PersonaReviewOut`, `ConsensusOut`,
  `DR3Out`, `ReviewSimResponse`; added `delta_omega`, `drift_level` to `CritiqueResponse`.

### Changed
- `pyproject.toml` version `2.5.0 → 3.2.0`
- CLI fallback version `2.5.0 → 3.2.0`

---

## [2.5.0] - 2026-04-22


### Added

#### Session Memory (MICA v0.2.3 Native Extraction)
- `src/veritas/session/mica_store.py` — MICA session lifecycle (zero external deps).
  - `detect_state()`, `resolve_paths()`, `count_invariants()` extracted from MICA v0.2.3
  - `MICAStore`: `start() / show() / log_di_violation() / close()` lifecycle
  - `DIViolation` dataclass, `SessionStatus.render()`
  - CLI: `veritas session start | show | close`

#### CR-EP Governance Gate (v2.7.2 Native Extraction)
- `src/veritas/governance/cr_ep_gate.py` — CR-EP state machine (zero external deps).
  - `detect_state()`: INIT -> CONTEXT_RESOLVED -> WHY_VALIDATED -> EXECUTING -> CLOSED
  - `bootstrap(root, profile)`: nano / lite / standard / full profiles
  - `append_event()` / `read_log()`: append-only enforcement_log.jsonl
  - `validate_artifacts()`, `check_violations()` guard conditions
  - CLI: `veritas govern init | status | log`

#### RAG Retriever (Flamehaven-Filesearch Native Extraction)
- `src/veritas/rag/retriever.py` — Hybrid BM25 + cosine + RRF retriever (zero external deps).
  - `BM25`: Robertson formula, k1=1.5, b=0.75, Korean+English tokenizer
  - `rrf_fusion()`: Reciprocal Rank Fusion, k=60
  - `chunk_text()`: heading-aware sliding window, word-count fallback for long sentences
  - `SciExpRetriever`: `index() / retrieve() / build_context()` hybrid pipeline
  - CLI: `veritas critique --rag` enables RAG context injection

#### Auto-Template Selection
- `src/veritas/templates/base.py` — `select_template(report)`:
  - RCA / ABLATION -> "ku" template
  - PARITY / EXTENSION / MULTIAXIS / None -> "bmj" template (safe default)
- `veritas critique --template auto` (now the default)
## [2.3.0] — 2026-04-22

### Added

#### Multi-Round Drift Tracking
- **`src/veritas/logos/drift_engine.py`** — NEW: `DriftEngine`, `DriftMetrics`, `DriftLevel`
  Pure-Python JSD/L2 divergence computation between consecutive IRF-6D score vectors.
  Algorithms extracted from Flamehaven-LOGOS `DriftController` + `OmegaScorer` — zero new external deps.
  - `DriftEngine.compute_round_drift(current, previous)` → `DriftMetrics`
  - `DriftEngine.apply_penalty(omega, jsd)` — SIDRCE JSD-gate: at JSD=0.06 omega collapses to 0
  - Thresholds: `JSD_MAX=0.06` (CRITICAL), `JSD_WARN=0.04` (WARNING), `L2_MAX=0.20`, `L2_WARN=0.10`

- **`src/veritas/types.py`** — `CritiqueReport` gains 3 new fields:
  - `delta_omega: float | None` — signed omega change vs previous round
  - `drift_metrics: dict | None` — `DriftMetrics.as_dict()` JSON-serializable snapshot
  - `jsd_penalized_omega: float | None` — JSD-gated omega (multi-round only)
  - `to_round_summary() -> dict` — minimal JSON snapshot for `--prev` reload
  - `from_round_summary(data) -> CritiqueReport` — reconstruct prev round from JSON

- **`src/veritas/engine.py`** — `critique()` + `critique_from_file()` gain `prev_report: CritiqueReport | None = None` parameter.
  When `prev_report` is provided and both reports have IRF scores, drift is computed automatically.

#### CLI Enhancements
- **`veritas critique --prev PATH`** — load previous round summary JSON for drift tracking
- **`veritas critique --save-round`** — auto-save `{stem}_r{N}.json` alongside output for chained rounds
- **`veritas batch PATTERN`** — batch critique with `ThreadPoolExecutor`:
  - `--jobs N` (default: 4) parallel workers
  - `--output-dir DIR` output directory
  - emits `summary_index.json` with per-file omega + status

#### Formatters
- **`src/veritas/cli/formatters.py`** — `_drift_block()` renders ROUND DIFF table in markdown output
  (JSD, L2, level, omega penalty factor, delta Omega, JSD-penalized Omega; only appears when drift_metrics present)

### Architecture
- **Zero new external dependencies** — all algorithms are stdlib-only pure Python extracted natively
- `DriftEngine` replaces future `flamehaven-logos` import risk (hardcoded path eliminated for drift)

### Quality
- **Tests**: new `tests/test_drift_engine.py` covering JSD math, penalty formula, round-summary I/O, multi-round integration
- **Tests**: `tests/test_cli.py` updated — `TestVersion` asserts `"2.3"`, `TestMultiRoundCLI`, `TestBatch` added
- Version gate: `test_version_flag` asserts `"2.3"` in output

---

## [2.2.1] — 2026-04-21

### Fixed
- **`cli/main.py`** — fallback `_VERSION` updated to `"2.2.1"`; previously reported `2.1.0`
  when `importlib.metadata` lookup failed in CI environments
- **`spar_bridge/layer_a/b/c.py`** — `from spar_framework.result_types import CheckResult`
  replaced with `try/except ImportError` fallback to `_compat.CheckResult`; CI no longer
  fails with `ModuleNotFoundError` when `spar-framework` is not installed
- **`spar_bridge/runtime.py`** — `ReviewRuntime` import made conditional; `get_review_runtime()`
  raises `ImportError` with install instructions when `spar-framework` is absent
- **`tests/test_spar_bridge.py`** — `TestRuntime` class decorated with
  `@pytest.mark.skipif(not _SPAR_AVAILABLE, ...)` so CI skips runtime tests gracefully

### Added
- **`src/veritas/spar_bridge/_compat.py`** — fallback `CheckResult` dataclass matching
  `spar_framework.result_types.CheckResult` interface (`check_id`, `label`, `status`,
  `detail`, `meta`) for CI-safe operation without optional `spar` extra

### Quality
- **Tests**: 159 passing, 2 skipped (spar runtime, CI-only) — up from 109 in v2.2.0
- **Coverage**: 82.34% (gate: 80%)
- **mypy**: 0 errors in 45 source files
- **ruff**: 0 lint errors, format clean

---

## [2.2.0] — 2026-04-19

### Added

#### Enrichment Engines
- **LOGOS IRF-Calc 6D** integration via `LogosBridge` — six-dimensional reasoning quality
  scoring (M/A/D/I/F/P); composite ≥ 0.78 = PASS
- **HSTA 4D** scoring via `HSTA4DScores` — Novelty/Consistency/Temporality/Reproducibility
  bibliometric assessment auto-computed from document text
- **Omega fusion** via `OmegaFusion` — hybrid omega blending SCI-EXP Omega with LOGOS
  composite for unified quality gate

#### Paper Intelligence Layer
- `BibliographyAnalyzer` — extracts reference quality metrics from document text:
  total refs, format detection (Vancouver/APA/Harvard), year range, self-citation flag,
  quality score (0–1)
- `ReproducibilityChecklistExtractor` — 8-criterion ARRIVE 2.0 / CONSORT 2010 / STROBE /
  TOP Guidelines assessment (DATA, CODE, PREREG, POWER, STATS, BLIND, EXCL, CONF)
- Both analyzers wired into `SciExpCritiqueEngine` and auto-populate `CritiqueReport` fields
- `paper/__init__.py` exports `BibliographyAnalyzer`, `ReproducibilityChecklistExtractor`

#### Type System
- `BibliographyStats` dataclass — `total_refs`, `recent_ratio`, `oldest_year`, `newest_year`,
  `formats_detected`, `self_citation_detected`, `quality_score` property
- `ReproducibilityItem` dataclass — `code`, `criterion`, `satisfied`, `note`
- `ReproducibilityChecklist` dataclass — `items`, `score` property, `default()` factory
- `CritiqueReport` extended with `bibliography_stats` and `reproducibility_checklist` fields

#### LaTeX Output
- `render/latex_renderer.py` — `LatexRenderer` class + `render_latex()` function
- Generates standalone `.tex` (no external `.cls` required) with color palette inspired by
  `labreport.cls` (navy, royalblue, traceable green, partial amber, not-traceable red)
- Optional `compile_pdf=True` — runs `xelatex` twice via subprocess
- CLI `--format tex` now supported

#### Template Enhancements
- BMJ and KU templates gain two conditional sections:
  - Section 9: Bibliography Analysis (rendered when `bibliography_stats` present)
  - Section 10: Reproducibility Checklist (rendered when `reproducibility_checklist` present)

#### Markdown Renderer
- `_biblio_md()` — Bibliography Analysis table appended when `bibliography_stats` set
- `_repro_md()` — Reproducibility Checklist table appended when `reproducibility_checklist` set

#### Assets (from external repo integration)
- `render/assets/harvard.csl` — Harvard Anglia Ruskin University citation style (Pandoc-compatible)

### Changed
- `SciExpCritiqueEngine.__init__` — initializes `BibliographyAnalyzer` and
  `ReproducibilityChecklistExtractor` as optional components (silent-fail on import error)
- `SciExpCritiqueEngine.critique()` — calls `_compute_bibliography()` and `_compute_repro()`
  and populates `CritiqueReport` fields
- `render/__init__.py` — exports `render_latex`, `LatexRenderer`
- `cli/main.py` — `--format` choice extended with `tex`

### Fixed
- `templates/ku.py` line 54 — `step1.vulnerable_claim` accessed when `step1 is None`;
  guarded with `step1 and step1.vulnerable_claim` (pre-existing bug, exposed by new tests)

### Tests
- 52 new tests across 3 new modules:
  - `tests/test_bibliography_analyzer.py` (12 tests)
  - `tests/test_reproducibility_checklist.py` (15 tests)
  - `tests/test_latex_renderer.py` (25 tests)
- Total suite: **109 tests**, all passing
- Coverage: **81.83%** (gate: 80%)

---

## [2.1.0] — 2026-04-19

### Added
- Full Python package implementation of VERITAS v2.2 protocol
- `SciExpCritiqueEngine` orchestrator with 7-phase pipeline (PRECHECK + STEP 0-5)
- `PrecheckEngine` — artifact sufficiency gate with FULL/PARTIAL/LIMITED/BLOCKED modes
- `EvidenceResolver` — 5-rank evidence precedence with conflict naming
- `CritiquePipeline` — STEP 0 experiment classification (PARITY/EXTENSION/RCA/ABLATION/MULTIAXIS)
- STEP 1 Claim Integrity analysis (40% weight)
- STEP 2 Traceability Audit (30% weight) — artifact chain, deviation log, interpretation gap, cross-cycle
- STEP 3 Series Continuity (20% weight) — handoff contract, next-cycle readiness, narrative drift
- STEP 4 Publication Readiness (10% weight) — internal rule compliance, misread risk
- STEP 5 Priority Fix synthesis — single fix, optional next liability
- FastAPI REST API with `/critique`, `/precheck`, `/classify`, `/health`, `/version`
- Pydantic v2 request/response schemas
- pytest test suite with 80% coverage gate
- GitHub Actions CI/CD (ci.yml, release.yml)
- Evidence conflict detection and named resolution
- MICA Playbook CLI mode (`--mica`) — structured JSON for agent/skill pipeline integration
- Dual output mode: REST API + CLI
- A4 professional report templates: BMJ Scientific Editing + KU Research Report
- Output formats: MD, PDF (ReportLab), DOCX (python-docx)
- Frontend MVP: file upload UI with drag-and-drop, format selector, live preview

### Protocol Compliance
- Output CONTRACT enforced: PRECHECK=2 lines, STEP 0=2 lines max, STEP 1-4=1 para max 4 sentences, STEP 5=2 sentences
- Traceability language locked to three classes; weaker terms (`unclear`, `suggestive`) rejected
- HOLD handling audit (1.4) implemented
- Round protocol (Round 1 vs Round 2+) state machine

---

## [2.0.0] — (prior, txt protocol definition)

### Added
- VERITAS protocol defined as text specification
- PRECHECK gate design
- Evidence Precedence hierarchy (ranks 1-5)
- STEP 0 through STEP 5 procedure definition
- OUTPUT CONTRACT specification
- ROUND PROTOCOL (Round 1 / Round 2+) definition
