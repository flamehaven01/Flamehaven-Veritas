# Changelog

All notable changes to **veritas** are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)  
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

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
