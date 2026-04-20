# VERITAS v2.2 — MICA Playbook

> **MICA v0.2.3 | mode=INVOCATION_MODE | DI=4crit/2high | pct=CLOSED**

This playbook is for any AI agent (Claude Code, Copilot CLI, etc.) that
needs to operate VERITAS v2.2 as a skill — via CLI or API.
Load this file at session start as your memory contract.

---

## What is VERITAS?

VERITAS is a 7-phase experimental report analysis engine that
produces structured, evidence-graded critiques of scientific papers and
experimental documents. It enforces traceability and reproducibility
standards aligned with BMJ Scientific Editing and KU Research Report
templates.

**Pipeline:** PRECHECK → STEP 0 (Classification) → STEP 1 (Claims) →
STEP 2 (Traceability) → STEP 3 (Continuity) → STEP 4 (Publication)
→ STEP 5 (Priority Fix)

**Omega score:** 0.0–1.0 quality indicator. ≥0.80 = publication-ready.

---

## CLI Invocation

### Install (first time)
```bash
cd "D:\Sanctum\VERITAS — EXPERIMENTAL REPORT ANALYSIS v2.1"
pip install -e .
```

### Core commands
```bash
# Analyse a PDF (MD output, token-efficient)
veritas critique paper.pdf

# Analyse a DOCX
veritas critique paper.docx

# Analyse inline text
veritas critique --text "Abstract: ..."

# Read from stdin (pipe mode)
cat paper.txt | veritas critique --stdin

# Export to PDF (requires --out)
veritas critique paper.pdf --format pdf --out report.pdf

# Export to DOCX
veritas critique paper.pdf --format docx --out report.docx

# Use KU template instead of default BMJ
veritas critique paper.pdf --template ku

# Quick precheck only
veritas precheck paper.pdf

# Show engine + MICA status
sciexp info

# Print this playbook (for re-loading into a session)
sciexp playbook
```

### Default output (MD, stdout)
- Token cost: ~800 tokens for a typical paper
- Format: structured markdown — paste directly into AI context
- Includes: PRECHECK status, STEP 0–5 prose, IRF 6D table (if LOGOS active),
  HSTA 4D scores, HOLD events, evidence conflicts, omega score

### File format support
| Extension | Requires |
|-----------|----------|
| `.pdf` | PyMuPDF (`pip install PyMuPDF`) |
| `.docx` | python-docx (`pip install python-docx`) |
| `.md`, `.txt` | no extra deps |

---

## API Invocation (Mode 1)

```bash
# Health check
curl http://localhost:8400/health

# Upload and critique
curl -X POST http://localhost:8400/api/v1/critique \
  -F "file=@paper.pdf" \
  -F "template=bmj" \
  -F "round_number=1"
```

**Start server:**
```bash
cd "D:\Sanctum\VERITAS — EXPERIMENTAL REPORT ANALYSIS v2.1"
uvicorn src.veritas.api.app:app --port 8400 --reload
```

---

## Design Invariants (DIs)

These are binding constraints. Violating any DI is a critique error.

### DI-001 — OUTPUT_CONTRACT [CRITICAL]
Each step has a fixed output length. Do not shorten or omit:
- PRECHECK: status line + missing artifact list
- STEP 0: 2 sentences (class + reason)
- STEP 1–4: 1 paragraph prose + per-finding traceability badge
- STEP 5: most vulnerable claim + priority fix

### DI-002 — TRACEABILITY_VOCAB [CRITICAL]
Three values **only**:
- `traceable`
- `partially traceable`
- `not traceable`

No synonyms. No paraphrases. These map to exact badge codes `[+]`, `[~]`, `[-]`.

### DI-003 — EVIDENCE_PRECEDENCE [CRITICAL]
Evidence rank 1 (raw data) > rank 5 (author claim).
When sources conflict, the lower rank (stronger evidence) wins unless
the higher-rank source explicitly documents the methodology.

### DI-004 — HOLD_UNDOCUMENTED [CRITICAL]
A HOLD event without `cause_stated=true` → classified as UNDOCUMENTED.
Each undocumented HOLD reduces STEP 4 score and must appear in output.

### DI-005 — IRF_F_GATE [HIGH]
If LOGOS IRF is active and falsification dimension F < 0.40:
- Add reproducibility warning to STEP 3
- Apply −0.05 penalty to hybrid omega

### DI-006 — HYBRID_OMEGA [HIGH]
Final omega = 0.6 × sciexp_omega + 0.4 × logos_composite
Always report both raw sciexp_omega AND hybrid omega.

---

## Interpreting CLI Output (MD format)

```
# VERITAS v2.2 — Report
Round: 1  Omega: 0.7430 → hybrid 0.7215
...
## PRECHECK
[status: PASS | PARTIAL | FAIL]
...
## STEP 0 — Experiment Classification
Class: EXPERIMENTAL
...
### IRF-Calc 6D (LOGOS)
| Dim | Score | ... |
...
## STEP 1 — Claim Integrity (w=0.40)
[prose paragraph]
- CLAIM-001 [+] Raw data confirmed in supplementary.
- CLAIM-002 [-] Author claims p<0.05 but no test statistics provided.
...
## STEP 5 — Priority Fix
[most vulnerable claim] [priority fix action]
...
---
not traceable: 2  partially traceable: 1
```

**Quick actions based on output:**
- Omega ≥ 0.80 → publication-ready
- Omega 0.60–0.80 → revisions needed; review STEP 5 priority fix
- Omega < 0.60 → major issues; check PRECHECK and STEP 1
- BLOCKED status → critical artifacts missing; request from author

---

## Agent Workflow Pattern

```
1. Load this playbook (session start)
2. Receive paper/document from user
3. Run: veritas critique <file> --format md
4. Read MD output (pasted into context, ~800 tokens)
5. Synthesize insights, surface priority fixes
6. Optionally: veritas critique <file> --round 2 for iterative refinement
7. If export requested: veritas critique <file> --format pdf --out out.pdf
```

### Chain pattern (iterative critique)
```bash
# Round 1: initial critique
veritas critique draft_v1.pdf --format md

# Round 2: after revisions
veritas critique draft_v2.pdf --round 2 --format md

# Final export
veritas critique draft_v2.pdf --format pdf --out final_report.pdf
```

---

## MICA Archive

- Contract: `memory/mica.yaml`
- Archive (DI bindings): `memory/sciexp.mica.archive.json`
- Playbook: `memory/playbook.md` (this file)

**MICA hook (for AI session init):**
```
[MICA] VERITAS v2.2 | mode=INVOCATION_MODE | DI=4crit/2high | pct=CLOSED
```

---

*VERITAS v2.2 | MICA v0.2.3 | Flamehaven Sovereign Asset*
