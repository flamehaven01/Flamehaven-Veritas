"""Tests for SectionParser (v3.3 section-aware parsing)."""

from __future__ import annotations

import pytest

from veritas.ingest.section_parser import SectionParser
from veritas.types import SectionMap


@pytest.fixture()
def parser() -> SectionParser:
    return SectionParser()


# ---------------------------------------------------------------------------
# Helper text fixtures
# ---------------------------------------------------------------------------

FULL_PAPER = """
Abstract
This study investigates the effect of novel catalyst X on reaction yield.
We hypothesise that temperature modulation will improve conversion rates.

Introduction
Catalytic reactions have been studied extensively since the 1960s. Background
work by Smith et al. (2020) provides the theoretical basis for this work.

Methods
Fifty samples were prepared using a standard protocol. Temperature was varied
between 25°C and 80°C in 5°C increments. Each condition was replicated 3×.

Results
Mean yield was 72% ± 4%. A statistically significant difference was observed
(p = 0.012). Effect size Cohen's d = 0.85 (large).

Discussion
The elevated temperature improved yield, consistent with Arrhenius kinetics.
However, temperatures above 70°C introduced degradation artefacts.

Conclusion
Temperature modulation improves yield up to 70°C. Further studies should
address catalyst stability at elevated temperatures.
""".strip()

MARKDOWN_HEADERS = """
# Abstract
Machine learning models were benchmarked against traditional methods.

## Introduction
The rapid development of ML techniques requires systematic evaluation.

## Methods
We evaluated 5 models on 3 benchmark datasets using 10-fold cross-validation.

## Results
Deep learning achieved 92% accuracy vs 78% for baseline (p < 0.001).

## Discussion
Performance gains are most pronounced for high-dimensional inputs.

## Conclusion
Deep learning outperforms baseline on all benchmark tasks evaluated.
""".strip()

NO_HEADERS_LONG = (
    "We propose a novel method for measuring enzyme kinetics. "
    "The experimental setup involved 96-well plates with varying substrate concentration. "
    "Results showed a linear relationship between concentration and reaction rate. "
    "The data suggests Michaelis-Menten kinetics apply. Conclusions are limited by sample size. "
) * 20  # ~400 words — long enough for position heuristic

SHORT_TEXT = "Too short for sections."

PARTIAL_PAPER = """
Abstract
We propose an approach for text classification.

Methods
Data was collected from public sources. Preprocessing included tokenization.
""".strip()


# ---------------------------------------------------------------------------
# Header-based detection tests
# ---------------------------------------------------------------------------


class TestHeaderDetection:
    def test_all_six_sections_detected(self, parser):
        sm = parser.parse(FULL_PAPER)
        assert sm.has("ABSTRACT")
        assert sm.has("INTRODUCTION")
        assert sm.has("METHODS")
        assert sm.has("RESULTS")
        assert sm.has("DISCUSSION")
        assert sm.has("CONCLUSION")

    def test_coverage_full(self, parser):
        sm = parser.parse(FULL_PAPER)
        assert sm.coverage == pytest.approx(1.0, abs=0.01)

    def test_markdown_headers(self, parser):
        sm = parser.parse(MARKDOWN_HEADERS)
        assert sm.has("ABSTRACT")
        assert sm.has("METHODS")
        assert sm.has("RESULTS")

    def test_section_text_not_empty(self, parser):
        sm = parser.parse(FULL_PAPER)
        abstract = sm.get("ABSTRACT")
        assert abstract is not None
        assert len(abstract) > 20

    def test_section_text_does_not_include_header(self, parser):
        sm = parser.parse(FULL_PAPER)
        abstract = sm.get("ABSTRACT")
        assert abstract is not None
        # The word "Abstract" as a standalone header should not appear
        # as the very first token of the text body
        assert not abstract.strip().lower().startswith("abstract\n")

    def test_results_contains_p_value(self, parser):
        sm = parser.parse(FULL_PAPER)
        results = sm.get("RESULTS")
        assert results is not None
        assert "p = 0.012" in results

    def test_partial_paper(self, parser):
        sm = parser.parse(PARTIAL_PAPER)
        assert sm.has("ABSTRACT")
        assert sm.has("METHODS")
        assert not sm.has("RESULTS")

    def test_partial_coverage_below_one(self, parser):
        sm = parser.parse(PARTIAL_PAPER)
        assert sm.coverage < 1.0

    def test_case_insensitive_headers(self, parser):
        text = "ABSTRACT\nSome abstract text here.\n\nMETHODS\nMethods text."
        sm = parser.parse(text)
        assert sm.has("ABSTRACT")
        assert sm.has("METHODS")


# ---------------------------------------------------------------------------
# Position-based fallback tests
# ---------------------------------------------------------------------------


class TestPositionHeuristic:
    def test_fallback_returns_sectionmap(self, parser):
        sm = parser.parse(NO_HEADERS_LONG)
        assert isinstance(sm, SectionMap)

    def test_fallback_coverage_capped(self, parser):
        sm = parser.parse(NO_HEADERS_LONG)
        # Coverage must be <= 0.40 for position-based fallback
        assert sm.coverage <= 0.40

    def test_too_short_returns_empty(self, parser):
        sm = parser.parse(SHORT_TEXT)
        assert len(sm.sections) == 0
        assert sm.coverage == 0.0

    def test_fallback_sections_nonempty(self, parser):
        sm = parser.parse(NO_HEADERS_LONG)
        assert len(sm.sections) > 0

    def test_fallback_at_least_intro_methods(self, parser):
        sm = parser.parse(NO_HEADERS_LONG)
        # Position heuristic assigns these two
        assert sm.has("INTRODUCTION") or sm.has("METHODS")


# ---------------------------------------------------------------------------
# SectionMap API tests
# ---------------------------------------------------------------------------


class TestSectionMapAPI:
    def test_get_returns_none_for_missing(self, parser):
        sm = parser.parse(PARTIAL_PAPER)
        assert sm.get("CONCLUSION") is None

    def test_has_case_insensitive(self, parser):
        sm = parser.parse(FULL_PAPER)
        assert sm.has("abstract")
        assert sm.has("ABSTRACT")

    def test_combined_joins_sections(self, parser):
        sm = parser.parse(FULL_PAPER)
        combined = sm.combined("RESULTS", "DISCUSSION")
        assert "yield" in combined.lower()
        assert len(combined) > 50

    def test_combined_skips_missing(self, parser):
        sm = parser.parse(PARTIAL_PAPER)
        combined = sm.combined("RESULTS", "DISCUSSION", "CONCLUSION")
        # None of these exist in PARTIAL_PAPER; combined should be empty
        assert combined.strip() == ""

    def test_word_count_via_document_section(self, parser):
        sm = parser.parse(FULL_PAPER)
        abstract_sec = sm.sections.get("ABSTRACT")
        assert abstract_sec is not None
        assert abstract_sec.word_count > 5
