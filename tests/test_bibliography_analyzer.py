"""Tests for BibliographyAnalyzer."""

from veritas.paper.bibliography_analyzer import BibliographyAnalyzer
from veritas.types import BibliographyStats

ANA = BibliographyAnalyzer()

_NUMBERED_TEXT = """
Some paper body text here.

REFERENCES

1. Smith J, Jones A. A study on things. J Med. 2023;10:1-10.
2. Brown K et al. Another study. Nature. 2020;500:200-210.
3. White L. Old reference. Science. 2005;300:100.
4. Green M. Very old work. J Biol. 1985;100:50-60.
5. Black N. Recent work. Cell. 2024;180:1-15.
"""

_AUTHORYEAR_TEXT = """
Smith et al. (2021) found that the method works well.
Previous studies (Jones, 2019; Brown, 2022) confirmed this.
Older work (White 2002) is also relevant.
"""

_APA_TEXT = """
Smith, J. (2022). Title. Journal.
Brown, K. (2019). Another. Another Journal.
"""


def test_count_numbered_refs():
    stats = ANA.analyze(_NUMBERED_TEXT)
    assert stats.total_refs == 5


def test_recent_ratio():
    stats = ANA.analyze(_NUMBERED_TEXT)
    # years 2023, 2020, 2005, 1985, 2024 — current year is >= 2024
    # recent (<=5yr from current): 2023, 2020 (if year <= 2025), 2024 → at least 2
    assert 0.0 < stats.recent_ratio <= 1.0


def test_year_range():
    stats = ANA.analyze(_NUMBERED_TEXT)
    assert stats.oldest_year == 1985
    assert stats.newest_year == 2024


def test_quality_score_nonzero():
    stats = ANA.analyze(_NUMBERED_TEXT)
    assert 0.0 < stats.quality_score <= 1.0


def test_quality_score_zero_no_refs():
    stats = ANA.analyze("No references here at all.")
    assert stats.quality_score == 0.0


def test_detect_apa_format():
    stats = ANA.analyze(_APA_TEXT)
    assert "APA" in stats.formats_detected


def test_no_self_citation_when_name_absent():
    stats = ANA.analyze(_NUMBERED_TEXT, author_name="Smith")
    # "Smith" does appear in ref 1 — should be detected
    assert stats.self_citation_detected is True


def test_no_self_citation_when_name_not_in_text():
    stats = ANA.analyze(_NUMBERED_TEXT, author_name="Rodriguez")
    assert stats.self_citation_detected is False


def test_returns_bibliography_stats_instance():
    result = ANA.analyze("Some text 2020.")
    assert isinstance(result, BibliographyStats)


def test_formats_default_unknown():
    stats = ANA.analyze("No citation patterns here.")
    assert stats.formats_detected == ["Unknown"]


def test_ref_section_extraction():
    """Should prefer text after REFERENCES header."""
    text = "Body: Smith 1990 is old.\n\nREFERENCES\n\n1. New A. Work. 2022.\n2. Modern B. Study. 2023.\n"
    stats = ANA.analyze(text)
    assert stats.total_refs == 2
