"""Methodology detector for VERITAS — AI Critique Experimental Report Analysis Framework.

Classifies experiment/paper methodology from text patterns.
Adapted from BioMedical-Paper-Harvester evidence_pattern_learning.py
and extended for SCI-EXP experimental report vocabulary.

Returns MethodologyClass (primary) and confidence score [0.0, 1.0].
"""
from __future__ import annotations

import re
from typing import Optional

from ..types import MethodologyClass

# Pattern banks: (MethodologyClass, markers, threshold_hits)
_PATTERNS: list[tuple[MethodologyClass, list[str], int]] = [
    (
        MethodologyClass.RCT,
        ["randomized", "randomised", "controlled trial", "placebo",
         "double-blind", "single-blind", "allocation", "arm ", "arms "],
        2,
    ),
    (
        MethodologyClass.META_ANALYSIS,
        ["meta-analysis", "meta analysis", "systematic review",
         "forest plot", "pooled", "heterogeneity", "funnel plot",
         "cochrane", "prisma"],
        2,
    ),
    (
        MethodologyClass.COHORT,
        ["cohort", "prospective", "retrospective", "longitudinal",
         "follow-up", "incidence", "participants followed"],
        2,
    ),
    (
        MethodologyClass.CASE_STUDY,
        ["case study", "case report", "n=1", "single patient",
         "single subject", "subject presented"],
        1,
    ),
    (
        MethodologyClass.SURVEY,
        ["survey", "questionnaire", "respondent", "likert",
         "interview", "focus group", "cross-sectional study"],
        2,
    ),
    (
        MethodologyClass.COMPUTATIONAL,
        ["simulation", "algorithm", "computational", "neural network",
         "deep learning", "model train", "inference", "benchmark",
         "dataset", "epoch", "loss curve", "accuracy"],
        3,
    ),
    (
        MethodologyClass.EXPERIMENTAL,
        ["experiment", "laboratory", "in vitro", "in vivo",
         "ablation", "parity", "rca", "extension", "multiaxis",
         "test run", "baseline run", "control group"],
        2,
    ),
    (
        MethodologyClass.OBSERVATIONAL,
        ["observational", "cross-sectional", "prevalence",
         "no intervention", "natural experiment"],
        1,
    ),
]


class MethodologyDetector:
    """Detect primary research/experiment methodology from text.

    Usage::

        det = MethodologyDetector()
        mc, conf = det.detect(text)
    """

    def detect(
        self, text: str
    ) -> tuple[MethodologyClass, float]:
        """Return (MethodologyClass, confidence).

        Confidence is normalised hit-count in [0, 1].
        Returns (UNKNOWN, 0.0) if no pattern fires above threshold.
        """
        t = text.lower()
        scores: list[tuple[float, MethodologyClass]] = []

        for method, markers, threshold in _PATTERNS:
            hits = sum(1 for m in markers if m in t)
            if hits >= threshold:
                confidence = min(hits / (threshold * 2), 1.0)
                scores.append((confidence, method))

        if not scores:
            return MethodologyClass.UNKNOWN, 0.0

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1], round(scores[0][0], 3)

    def detect_all(self, text: str) -> list[tuple[MethodologyClass, float]]:
        """Return all matched methodologies sorted by confidence (descending)."""
        t = text.lower()
        results: list[tuple[MethodologyClass, float]] = []

        for method, markers, threshold in _PATTERNS:
            hits = sum(1 for m in markers if m in t)
            if hits >= threshold:
                confidence = min(hits / (threshold * 2), 1.0)
                results.append((method, round(confidence, 3)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results
