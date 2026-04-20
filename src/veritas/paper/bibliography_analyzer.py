"""Bibliography analysis — reference quality metrics from document text.

Patterns derived from:
  - latex-scientific-paper-templates/bib/labreport.bst
      (author-year, <=5 authors, natbib)
  - Markdown-Templates/bibliography/assets/citation-style.csl
      (Harvard Anglia Ruskin University author-date style)
  - reproducible_research naming convention (YYYY-MM-DD provenance)
"""
from __future__ import annotations

import re
from datetime import date

from ..types import BibliographyStats

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------
_YEAR_PAT       = re.compile(r'\b(19[5-9]\d|20[0-2]\d)\b')
_REF_HEADER     = re.compile(
    r'\n\s*(?:REFERENCES?|BIBLIOGRAPHY|WORKS\s+CITED|CITATIONS?)\s*\n',
    re.IGNORECASE,
)
_NUMBERED_REF   = re.compile(
    r'(?m)^\s*(?:\[\d+\]|\(\d+\)|\d+\.)\s+[A-Z\[]',
)
_AUTHORYEAR_REF = re.compile(
    r'[A-Z][a-z\-]+(?:\s+[A-Z][a-z\-]+)*'
    r'(?:\s+et\s+al\.)?'
    r'[,\s]+\(?(?:19[5-9]\d|20[0-2]\d)\)?',
)
_VANCOUVER_PAT  = re.compile(r'(?m)^\s*\d+\.\s+[A-Z][a-z]+\s+\w+')
_APA_PAT        = re.compile(r'\b[A-Z][a-z]+,\s+[A-Z]\.\s*\(?(?:19|20)\d{2}\)')
_HARVARD_PAT    = re.compile(r'\b[A-Z][a-z]+,\s+[A-Z][a-z]+\s+(?:19|20)\d{2},')


class BibliographyAnalyzer:
    """Analyze reference quality metrics from plain document text.

    Usage::
        analyzer = BibliographyAnalyzer()
        stats = analyzer.analyze(text, author_name="Smith")
    """

    def analyze(self, text: str, author_name: str = "") -> BibliographyStats:
        """Return BibliographyStats extracted from *text*.

        Args:
            text:        Full document text.
            author_name: Primary author surname for self-citation detection.
        """
        ref_text  = self._extract_ref_section(text)
        scan_zone = ref_text if ref_text else text[-4000:]
        years     = [int(y) for y in _YEAR_PAT.findall(scan_zone)]
        current   = date.today().year

        return BibliographyStats(
            total_refs             = self._count_refs(scan_zone),
            recent_ratio           = self._recent_ratio(years, current),
            oldest_year            = min(years) if years else None,
            newest_year            = max(years) if years else None,
            formats_detected       = self._detect_formats(scan_zone),
            self_citation_detected = (
                self._detect_self_cites(scan_zone, author_name)
                if author_name else False
            ),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_ref_section(self, text: str) -> str:
        m = _REF_HEADER.search(text)
        return text[m.end():] if m else ""

    def _count_refs(self, zone: str) -> int:
        numbered = _NUMBERED_REF.findall(zone)
        if numbered:
            return len(numbered)
        # Fallback: author-year occurrences (deduplicated by rough line count)
        return len(_AUTHORYEAR_REF.findall(zone))

    def _recent_ratio(self, years: list[int], current: int) -> float:
        if not years:
            return 0.0
        recent = sum(1 for y in years if current - y <= 5)
        return round(recent / len(years), 4)

    def _detect_formats(self, zone: str) -> list[str]:
        formats = []
        if _VANCOUVER_PAT.search(zone):
            formats.append("Vancouver")
        if _APA_PAT.search(zone):
            formats.append("APA")
        if _HARVARD_PAT.search(zone):
            formats.append("Harvard")
        return formats or ["Unknown"]

    def _detect_self_cites(self, zone: str, author_name: str) -> bool:
        last    = author_name.strip().split()[-1]
        pattern = re.compile(re.escape(last), re.IGNORECASE)
        return bool(pattern.search(zone))
