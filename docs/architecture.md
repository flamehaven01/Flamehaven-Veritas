# VERITAS v2.2 — System Architecture

## Overview

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (MVP)                    │
│  index.html  ·  app.js  ·  style.css                │
│  Drag-drop upload → API calls → inline preview       │
│  Download buttons: PDF · DOCX · MD                  │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (multipart / JSON)
┌──────────────────────▼──────────────────────────────┐
│               FastAPI Backend (port 8400)            │
│  api/app.py     CORS + static mount                  │
│  api/routes.py  /critique/upload · /critique/text   │
│                 /critique/download · /precheck       │
│  api/schemas.py Pydantic v2 I/O models               │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│            SciExpCritiqueEngine  (engine.py)         │
│                                                      │
│  1. precheck.run()          PRECHECK gate            │
│  2. pipeline.step0_classify  Experiment class        │
│  3. evidence.extract+resolve Evidence precedence     │
│  4. pipeline.step1-4        STEP 1-4 analysis        │
│  5. pipeline.step5_priority_fix  Priority verdict    │
│  6. _compute_omega()        Omega traceability score │
└──────┬─────────────────────────────┬────────────────┘
       │                             │
┌──────▼────────┐          ┌─────────▼──────────────┐
│  ingest/      │          │   rag/                  │
│  document.py  │          │   retriever.py          │
│               │          │   context_builder.py    │
│  PDF/DOCX/TXT │          │                         │
│  ──────────── │          │  EmbeddingGenerator     │
│  Flamehaven   │          │  _SimpleVectorStore     │
│  file_parser  │          │  cosine similarity      │
│  + fallbacks  │          │  top-k retrieval        │
└───────────────┘          └─────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│               Render Layer                           │
│  render/md_renderer.py    → .md (stdlib only)       │
│  render/docx_renderer.py  → .docx (python-docx)     │
│  render/pdf_renderer.py   → .pdf  (reportlab A4)    │
│                                                      │
│  Template registry (templates/base.py)              │
│    templates/bmj.py  BMJ Scientific Editing Report  │
│    templates/ku.py   KU Research Report Template    │
└─────────────────────────────────────────────────────┘
```

## Module Map

| Module | Responsibility | Key public API |
|---|---|---|
| `engine.py` | Orchestrate full pipeline | `SciExpCritiqueEngine.critique()` |
| `precheck.py` | Artifact sufficiency gate | `run(text) → PrecheckResult` |
| `pipeline.py` | STEP 0-5 analysis | `step0_classify`, `step1_claim_integrity`, … |
| `evidence.py` | Evidence precedence | `extract_evidence`, `resolve` |
| `types.py` | Type universe | All enums, dataclasses |
| `ingest/document.py` | Multi-format parser | `extract_text`, `extract_chunks` |
| `rag/retriever.py` | Embedding + vector store | `SciExpRetriever.index_chunks`, `.build_context` |
| `rag/context_builder.py` | Per-step RAG context | `build_all_contexts` |
| `templates/bmj.py` | BMJ template | `BMJTemplate.build(report)` |
| `templates/ku.py` | KU template | `KUTemplate.build(report)` |
| `render/md_renderer.py` | Markdown output | `render_md`, `save_md` |
| `render/docx_renderer.py` | Word output | `render_docx` |
| `render/pdf_renderer.py` | PDF output | `render_pdf` |
| `api/app.py` | FastAPI entry | `app`, `main()` |
| `api/routes.py` | HTTP endpoints | See API Reference |
| `api/schemas.py` | Pydantic models | `CritiqueRequest`, `CritiqueResponse` |

## Data Flow

```
File Upload
    │
    ▼
extract_text(file)          ← Flamehaven-Filesearch or fallback
    │
    ▼
precheck.run(text)          ← FULL / PARTIAL / LIMITED / BLOCKED
    │
    ├─[BLOCKED]─► return minimal report
    │
    ▼
step0_classify(text)        ← ExperimentClass (5 types)
evidence.extract+resolve    ← EvidenceRank 1-5 precedence
    │
    ▼
step1_claim_integrity       ← weight 0.40, finds HOLDs
step2_traceability          ← weight 0.30, uses HOLDs from step1
step3_series_continuity     ← weight 0.20
step4_publication_readiness ← weight 0.10
    │
    ▼
step5_priority_fix          ← ranks by NOT_TRACEABLE count
    │
    ▼
_compute_omega()            ← traceable/total − mode_penalty
    │
    ▼
CritiqueReport              ← serialised by api/schemas.py
    │
    ▼
render_md / render_docx / render_pdf   ← via template
```

## Omega Score

```
omega = (traceable_findings / total_findings) - mode_penalty
mode_penalty: FULL=0.00, PARTIAL=0.05, LIMITED=0.15
range: [0.0, 1.0]
```

## Flamehaven-Filesearch Integration

The system uses Flamehaven-Filesearch (`D:\Sanctum\Flamehaven-Filesearch`) as an **optional** dependency:

- **EmbeddingGenerator**: Gravitas Vectorizer v2.0, dim=384, deterministic
- **file_parser**: `extract_text(path)` handles PDF/DOCX/XLSX/PPTX
- **text_chunker**: `chunk_text(text, max_tokens, overlap_tokens)`

All integrations use `try/except` with graceful fallback — the system runs fully offline without Flamehaven.
