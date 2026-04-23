"""Section-aware academic document parser for VERITAS v3.3.

Detects canonical academic sections (ABSTRACT, INTRODUCTION, METHODS,
RESULTS, DISCUSSION, CONCLUSION) via regex header matching with a
position-based fallback for documents without explicit headers.

``SectionParser.parse(text)`` returns a ``SectionMap`` used downstream
by the STEP 1-5 pipeline to apply section-specific validation rules.
"""

from __future__ import annotations

import re

from ..types import DocumentSection, SectionMap

# ---------------------------------------------------------------------------
# Canonical section name → list of accepted header patterns
# ---------------------------------------------------------------------------

_CANONICAL: list[tuple[str, re.Pattern[str]]] = [
    (
        "ABSTRACT",
        re.compile(
            r"^\s*(?:#{1,3}\s*)?abstract\s*$",
            re.I | re.M,
        ),
    ),
    (
        "INTRODUCTION",
        re.compile(
            r"^\s*(?:#{1,3}\s*)?(?:introduction|background(?:\s+and\s+motivation)?)\s*$",
            re.I | re.M,
        ),
    ),
    (
        "METHODS",
        re.compile(
            r"^\s*(?:#{1,3}\s*)?(?:methods?|methodology|"
            r"materials?\s+(?:and\s+)?methods?|"
            r"experimental\s+(?:setup|design|section|methods?)|"
            r"study\s+design)\s*$",
            re.I | re.M,
        ),
    ),
    (
        "RESULTS",
        re.compile(
            r"^\s*(?:#{1,3}\s*)?(?:results?|findings?|outcomes?|"
            r"results?\s+and\s+(?:discussion|analysis))\s*$",
            re.I | re.M,
        ),
    ),
    (
        "DISCUSSION",
        re.compile(
            r"^\s*(?:#{1,3}\s*)?discussion\s*$",
            re.I | re.M,
        ),
    ),
    (
        "CONCLUSION",
        re.compile(
            r"^\s*(?:#{1,3}\s*)?(?:conclusions?|summary|"
            r"closing\s+remarks?|final\s+(?:remarks?|thoughts?))\s*$",
            re.I | re.M,
        ),
    ),
]

_CANONICAL_NAMES = [name for name, _ in _CANONICAL]

# Minimum characters for a section body to be considered non-empty
_MIN_SECTION_CHARS = 15


class SectionParser:
    """Parse an academic document text into a ``SectionMap``.

    Usage::

        parser = SectionParser()
        section_map = parser.parse(text)
        abstract_text = section_map.get("ABSTRACT")
    """

    def parse(self, text: str) -> SectionMap:
        """Detect and extract sections from *text*.

        Tries header-based detection first; falls back to position-based
        heuristics when no headers are found (short docs, plain-text reports).
        """
        anchors = self._find_anchors(text)

        if len(anchors) >= 2:
            return self._slice_by_anchors(text, anchors)

        # Not enough headers — try position-based heuristic
        return self._position_heuristic(text)

    # ------------------------------------------------------------------
    # Private: header detection
    # ------------------------------------------------------------------

    def _find_anchors(self, text: str) -> list[tuple[int, str]]:
        """Return list of (char_pos, canonical_name) sorted by position."""
        found: list[tuple[int, str]] = []
        for name, pattern in _CANONICAL:
            for m in pattern.finditer(text):
                found.append((m.start(), name))
        found.sort(key=lambda x: x[0])
        # Deduplicate: keep first occurrence of each canonical name
        seen: set[str] = set()
        deduped: list[tuple[int, str]] = []
        for pos, name in found:
            if name not in seen:
                seen.add(name)
                deduped.append((pos, name))
        return deduped

    def _slice_by_anchors(
        self,
        text: str,
        anchors: list[tuple[int, str]],
    ) -> SectionMap:
        """Slice *text* at anchor positions to produce sections."""
        sections: dict[str, DocumentSection] = {}
        for i, (start_pos, name) in enumerate(anchors):
            end_pos = anchors[i + 1][0] if i + 1 < len(anchors) else len(text)
            # Skip the header line itself
            body_start = text.find("\n", start_pos)
            body_start = body_start + 1 if body_start != -1 else start_pos
            body = text[body_start:end_pos].strip()
            if len(body) >= _MIN_SECTION_CHARS:
                sections[name] = DocumentSection(
                    name=name,
                    text=body,
                    start_pos=body_start,
                    end_pos=end_pos,
                )
        coverage = len(sections) / len(_CANONICAL_NAMES)
        return SectionMap(sections=sections, coverage=round(coverage, 4))

    # ------------------------------------------------------------------
    # Private: position-based fallback
    # ------------------------------------------------------------------

    def _position_heuristic(self, text: str) -> SectionMap:
        """Assign text regions to likely sections based on position ratios.

        For documents without explicit headers (e.g., plain-text experiment
        reports), approximate sections by document position:
          0-15%   -> INTRODUCTION
          15-45%  -> METHODS
          45-75%  -> RESULTS
          75-100% -> DISCUSSION / CONCLUSION

        Coverage is capped at 0.40 to signal low confidence.
        """
        n = len(text)
        if n < 200:
            return SectionMap(sections={}, coverage=0.0)

        splits = [
            ("INTRODUCTION", 0, int(n * 0.15)),
            ("METHODS", int(n * 0.15), int(n * 0.45)),
            ("RESULTS", int(n * 0.45), int(n * 0.75)),
            ("DISCUSSION", int(n * 0.75), n),
        ]
        sections: dict[str, DocumentSection] = {}
        for name, s, e in splits:
            body = text[s:e].strip()
            if len(body) >= _MIN_SECTION_CHARS:
                sections[name] = DocumentSection(name=name, text=body, start_pos=s, end_pos=e)
        coverage = min(len(sections) / len(_CANONICAL_NAMES), 0.40)
        return SectionMap(sections=sections, coverage=round(coverage, 4))
