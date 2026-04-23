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

## Writing a Domain Plugin (v3.4+)

VERITAS v3.4 introduces a domain plugin architecture for extending IRF-6D scoring beyond the default
biomedical domain. You can contribute new domains (physics, economics, social science, etc.) or
override built-in ones.

### 1. Define a DomainRuleset

```python
# my_package/veritas_physics.py
from veritas.logos.domain.base import DomainRuleset

PHYSICS = DomainRuleset(
    domain_key="physics",                # unique key (lowercase, no spaces)
    name="Experimental Physics",         # human-readable label
    # IRF-6D marker banks — tuples of lowercase keyword fragments
    m_markers=("uncertainty", "systematic error", "measurement"),
    a_markers=("lagrangian", "hamiltonian", "wave function"),
    d_markers=("derivation", "proof", "conservation law"),
    i_markers=("experimental data", "cross-section", "event yield"),
    f_markers=("exclusion limit", "null hypothesis", "falsifiable"),
    p_markers=("standard model", "quantum field theory"),
    composite_threshold=0.78,            # min composite IRF to PASS
    component_min=0.25,                  # min per-dimension to avoid floor penalty
    saturate_at={                        # optional — markers needed for saturation (1.0)
        "M": 4, "A": 4, "D": 4, "I": 5, "F": 5, "P": 4
    },
)
```

### 2. Register via entry_points

In your `pyproject.toml`:

```toml
[project.entry-points."veritas.domains"]
physics = "my_package.veritas_physics:PHYSICS"
```

### 3. Install and verify

```bash
pip install -e .
veritas domains list   # physics should appear
veritas critique paper.pdf --domain physics
```

### Rules

- `domain_key` must be lowercase, alphanumeric + underscore only, unique across all installed plugins
- All 6 marker banks (`m_markers` through `p_markers`) must be non-empty tuples of strings
- `composite_threshold` must be in [0.5, 1.0]
- Tests: add `tests/test_my_domain.py` with at least one scoring divergence test

### Contribution Pathway

If your domain plugin is general-purpose (e.g. physics, economics, social science), open a PR to
`flamehaven01/Flamehaven-Veritas` to include it as a built-in domain.
PRs for built-in domains must include ≥ 10 tests and demonstrate scoring divergence vs biomedical.

---

## Reporting Issues

Open a GitHub Issue. Include:
- The report text (or a minimal reproduction)
- The `PRECHECK MODE` the engine produced
- The expected vs actual critique output
