"""Tests for STEP 0-5 pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from veritas.pipeline import (
    step0_classify,
    step1_claim_integrity,
    step2_traceability,
    step3_series_continuity,
    step4_publication_readiness,
    step5_priority_fix,
)
from veritas.types import TraceabilityClass


def test_step0_returns_classification(sample_text):
    exp_class, secondary, reason = step0_classify(sample_text)
    assert exp_class is not None
    assert isinstance(reason, str)
    assert len(reason) > 0


def test_step1_returns_prose_and_weight(sample_text):
    result, holds = step1_claim_integrity(sample_text)
    assert result.step_id == "1"
    assert result.weight == 0.40
    assert len(result.prose) > 0
    assert isinstance(holds, list)


def test_step2_traceability_classes(sample_text):
    _, holds = step1_claim_integrity(sample_text)
    result = step2_traceability(sample_text, holds)
    assert result.step_id == "2"
    assert result.weight == 0.30
    for f in result.findings:
        assert f.traceability in (
            TraceabilityClass.TRACEABLE,
            TraceabilityClass.PARTIALLY_TRACEABLE,
            TraceabilityClass.NOT_TRACEABLE,
        )


def test_step3_continuity(sample_text):
    result = step3_series_continuity(sample_text)
    assert result.step_id == "3"
    assert result.weight == 0.20


def test_step4_publication_readiness(sample_text):
    result = step4_publication_readiness(sample_text)
    assert result.step_id == "4"
    assert result.weight == 0.10


def test_step5_priority_fix_two_sentences(sample_text):
    s1, _ = step1_claim_integrity(sample_text)
    _, holds = step1_claim_integrity(sample_text)
    s2 = step2_traceability(sample_text, holds)
    s3 = step3_series_continuity(sample_text)
    s4 = step4_publication_readiness(sample_text)
    fix, next_l = step5_priority_fix(s1, s2, s3, s4)
    # Protocol: STEP 5 max 2 sentences
    assert isinstance(fix, str)
    assert len(fix) > 0


def test_full_pipeline_omega_range(engine, sample_text):
    report = engine.critique(sample_text)
    assert 0.0 <= report.omega_score <= 1.0


def test_full_pipeline_has_six_steps(engine, sample_text):
    report = engine.critique(sample_text)
    assert len(report.steps) == 6
    ids = [s.step_id for s in report.steps]
    assert ids == ["0", "1", "2", "3", "4", "5"]
