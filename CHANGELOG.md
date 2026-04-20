# Changelog

All notable changes to **veritas** are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)  
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

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
