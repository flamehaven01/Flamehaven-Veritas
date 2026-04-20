"""Tests for PRECHECK gate."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from veritas.precheck import run
from veritas.types    import SciExpMode


FULL_REPORT = """
Method: dissolve 10 mg compound in 5 mL DMSO. source_path: /data/exp/raw_v1.csv
sha256_hash_manifest: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2
Data: raw_values_v1.csv contains absorbance readings.
Figure 1 shows dose-response curves. PASS_RUN1 confirmed.
Statistical analysis: ANOVA p<0.05, post-hoc Tukey.
Hypothesis: compound reduces cell viability at IC50=25 uM.
Verdict: PASS — numeric stability confirmed at 95% confidence interval.
"""

BLOCKED_REPORT = "Something happened and then we concluded it was fine."


def test_precheck_full():
    r = run(FULL_REPORT)
    assert r.mode == SciExpMode.FULL
    assert r.line1 != ""
    assert r.line2 != ""


def test_precheck_blocked():
    r = run(BLOCKED_REPORT)
    assert r.mode in (SciExpMode.BLOCKED, SciExpMode.LIMITED)


def test_precheck_missing_artifacts_reported():
    r = run(BLOCKED_REPORT)
    assert isinstance(r.missing_artifacts, list)


def test_precheck_with_partial_artifacts():
    partial = "Method: mixed chemicals. Figure 1 shows results."
    r = run(partial)
    assert r.mode in (SciExpMode.FULL, SciExpMode.PARTIAL, SciExpMode.LIMITED, SciExpMode.BLOCKED)


def test_precheck_output_lines_not_empty(sample_text):
    r = run(sample_text)
    assert len(r.line1) > 0
    assert len(r.line2) > 0
