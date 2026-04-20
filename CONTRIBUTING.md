# Contributing to VERITAS

Thank you for contributing. This document defines the standards for this project.

---

## Ground Rules

1. **Protocol fidelity first.** Any change to critique logic must remain compliant with
   the VERITAS v2.2 specification (`VERITAS *.txt`).
2. **No weaker traceability language.** The engine may only emit `traceable`,
   `partially traceable`, or `not traceable`. PRs that introduce softer terms will be
   rejected.
3. **Output CONTRACT is immutable.** The shape of PRECHECK (2 lines), STEP 0 (2 lines),
   STEP 1-4 (1 para, max 4 sentences), STEP 5 (2 sentences) must not be relaxed.
4. **Evidence Precedence is non-negotiable.** Rank 1 always overrides Rank 5.
   Do not introduce resolution heuristics that bypass the rank order.

---

## Development Setup

```bash
git clone <repo>
cd veritas
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Unix

pip install -e ".[dev]"
```

---

## Running Tests

```bash
pytest                          # full suite + coverage
pytest tests/test_precheck.py   # single module
pytest -k "test_blocked"        # filter by name
```

Coverage gate: **80% minimum**. PRs that drop below will not pass CI.

---

## Code Style

```bash
ruff check src tests            # lint
ruff format src tests           # format
mypy src                        # type check
```

All three must pass before opening a PR.

---

## PR Process

1. Branch from `main` using `feature/<short-description>` or `fix/<issue-number>`
2. Ensure `pytest`, `ruff`, and `mypy` pass locally
3. Update `CHANGELOG.md` under `[Unreleased]`
4. Open a PR — describe the change and which protocol section it affects
5. At least one reviewer approval required before merge

---

## What NOT to Do

- Do not add inference to fill missing evidence — treat unverified artifacts as absent
- Do not introduce narrative drift: stability metrics are not evidence of systemic superiority
- Do not merge breaking changes to the `CritiqueReport` schema without a major version bump

---

## Reporting Issues

Open a GitHub Issue. Include:
- The report text (or a minimal reproduction)
- The `PRECHECK MODE` the engine produced
- The expected vs actual critique output
