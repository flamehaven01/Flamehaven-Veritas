# VERITAS v2.2 — API Reference

Base URL: `http://localhost:8400`

## Endpoints

### POST `/api/v1/critique/text`
Submit raw text for critique.

**Request body (JSON):**
```json
{
  "report_text": "...",
  "template": "bmj",
  "round_number": 1
}
```

**Response:** `CritiqueResponse` (see schema below)

---

### POST `/api/v1/critique/upload`
Upload a document file for critique.

**Request:** `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `file` | file | PDF / DOCX / DOC / TXT / MD |
| `template` | string | `bmj` (default) or `ku` |
| `round_number` | int | Critique round (default: 1) |

**Response:** `CritiqueResponse`

---

### POST `/api/v1/critique/download`
Upload a document and receive a formatted report file.

**Request:** `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `file` | file | PDF / DOCX / DOC / TXT / MD |
| `format` | string | `pdf`, `docx`, `md`, or `tex` |
| `template` | string | `bmj` (default) or `ku` |
| `round_number` | int | Critique round (default: 1) |

**Response:** File download
- `application/pdf` for `format=pdf`
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document` for `format=docx`
- `text/markdown` for `format=md`
- `text/x-tex` for `format=tex`

---

### POST `/api/v1/precheck`
Run PRECHECK gate only (no full pipeline).

**Request body (JSON):** Same as `/critique/text`

**Response:**
```json
{
  "mode": "FULL",
  "missing_artifacts": [],
  "line1": "PRECHECK MODE: FULL",
  "line2": "All 6 artifact classes present."
}
```

---

### GET `/health`
Health check.

**Response:** `{"status": "ok", "version": "2.2.0"}`

---

### GET `/version`
Version info.

**Response:** `{"version": "2.2.0", "protocol": "VERITAS v2.2"}`

---

## Response Schema — `CritiqueResponse`

```json
{
  "precheck": {
    "mode": "FULL | PARTIAL | LIMITED | BLOCKED",
    "missing_artifacts": ["sha256_hash_manifest"],
    "line1": "PRECHECK MODE: PARTIAL",
    "line2": "Primary claim evaluable; 1 secondary artifact absent."
  },
  "experiment_class": "EXTENSION",
  "experiment_class_secondary": null,
  "experiment_class_reason": "...",
  "steps": [
    {
      "step_id": "0",
      "weight": 0.0,
      "prose": "Experiment class: EXTENSION. ...",
      "findings": [],
      "vulnerable_claim": null,
      "not_applicable": false
    },
    {
      "step_id": "1",
      "weight": 0.40,
      "prose": "The central claim is traceable...",
      "findings": [
        {
          "code": "1.1",
          "description": "Central claim identified: ...",
          "traceability": "traceable",
          "verbatim_quote": null
        }
      ],
      "vulnerable_claim": "...",
      "not_applicable": false
    }
  ],
  "priority_fix": "The priority fix is...",
  "next_liability": "Once STEP 1 is resolved...",
  "round_number": 1,
  "omega_score": 0.7143,
  "not_traceable_count": 2,
  "partially_traceable_count": 1,
  "evidence_conflicts": [],
  "hold_events": [],
  "irf_scores": {
    "M": 0.810, "A": 0.750, "D": 0.820, "I": 0.780, "F": 0.700, "P": 0.830,
    "composite": 0.782,
    "passed": true
  },
  "hsta_scores": {
    "N": 0.900, "C": 0.760, "T": 0.750, "R": 0.500,
    "composite": 0.728
  },
  "bibliography_stats": {
    "total_refs": 24,
    "recent_ratio": 0.625,
    "oldest_year": 2010,
    "newest_year": 2025,
    "formats_detected": ["APA"],
    "self_citation_detected": false,
    "quality_score": 0.713
  },
  "reproducibility_checklist": {
    "score": 0.750,
    "items": [
      {"code": "DATA", "criterion": "Open data availability", "satisfied": true,  "note": "data available at ..."},
      {"code": "CODE", "criterion": "Code / software availability", "satisfied": false, "note": ""},
      {"code": "PREREG", "criterion": "Pre-registration", "satisfied": null, "note": ""},
      {"code": "POWER", "criterion": "Statistical power / sample size", "satisfied": true, "note": "power = 0.80 at ..."}
    ]
  }
}
```

## Traceability Values

The `traceability` field in findings is locked to exactly 3 values:

| Value | Meaning |
|---|---|
| `traceable` | Fully anchored to a measured artifact |
| `partially traceable` | Some anchoring present, incomplete |
| `not traceable` | No artifact anchor found |

## ExperimentClass Values

| Class | Description |
|---|---|
| `PARITY` | Reproducibility / baseline identity check |
| `RCA` | Root-cause analysis / failure investigation |
| `ABLATION` | Component removal / isolation study |
| `MULTIAXIS` | Cross-cycle / multi-variable comparison |
| `EXTENSION` | New component / augmentation (default) |

## PRECHECK Modes

| Mode | Condition |
|---|---|
| `FULL` | All 6 artifact classes present |
| `PARTIAL` | Primary claim evaluable; ≥1 secondary artifact missing |
| `LIMITED` | Primary claim artifact absent; one central claim evaluable |
| `BLOCKED` | Report body absent or no evaluable claim |

## IRF-Calc 6D Dimensions

| Key | Full Name | Threshold |
|---|---|---|
| M | Methodic Doubt | — |
| A | Axiom / Hypothesis | — |
| D | Deduction | — |
| I | Induction | — |
| F | Falsification | — |
| P | Paradigm | — |
| composite | Mean(M+A+D+I+F+P) | ≥ 0.78 = PASS |

## Reproducibility Checklist Criteria

| Code | Criterion | Standard |
|---|---|---|
| DATA | Open data availability | TOP Guidelines |
| CODE | Code / software availability | TOP Guidelines |
| PREREG | Pre-registration declaration | CONSORT 2010 |
| POWER | Statistical power / sample size | CONSORT 2010 |
| STATS | Statistics description | STROBE |
| BLIND | Blinding / randomization | ARRIVE 2.0 |
| EXCL | Exclusion criteria | ARRIVE 2.0 |
| CONF | Conflict of interest | All guidelines |

## Output Contract (Protocol Compliance)

- **PRECHECK**: exactly 2 lines output
- **STEP 0**: max 2 lines
- **STEP 1-4**: 1 paragraph, max 4 sentences
- **STEP 5**: exactly 2 sentences
- **Traceability language**: locked to 3 exact strings (no substitutes)
- **HOLD events** without stated cause = `HoldDisposition.UNDOCUMENTED` (never silently resolved)
