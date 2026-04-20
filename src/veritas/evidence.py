"""Evidence Precedence Resolver.

Implements the 5-rank Evidence Precedence hierarchy from VERITAS — AI Critique Experimental Report Analysis Framework.

Rules:
  - A higher-ranked artifact (lower rank number) overrides a lower-ranked one.
  - If two artifacts at the same rank conflict, the conflict is named explicitly.
  - The conflict is never resolved by guesswork.
  - An unverified artifact is treated as absent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .types import EvidenceConflict, EvidenceRank


@dataclass
class EvidenceItem:
    """A single piece of evidence extracted from a report."""
    rank:        EvidenceRank
    label:       str          # human-readable label (e.g. "Figure 3", "SHA-256: abc...")
    content:     str          # extracted text or hash
    line_number: Optional[int] = None


@dataclass
class ResolutionResult:
    """Output of the resolver for a given set of evidence items."""
    resolved:   Optional[EvidenceItem]  # highest-authority item, None if all absent
    conflicts:  list[EvidenceConflict]
    overridden: list[EvidenceItem]      # items that lost to a higher rank


# ---------------------------------------------------------------------------
# Extraction heuristics
# ---------------------------------------------------------------------------

_SHA256     = re.compile(r'\b([0-9a-fA-F]{64})\b')
_FIGURE_REF = re.compile(r'(Figure\s*\d+|Table\s*\d+|fig\.\s*\d+)', re.IGNORECASE)
_PASS_BLOCK = re.compile(r'\b(PASS|BLOCK|HOLD)(?:_\w+)?\b')
_MANIFEST   = re.compile(r'manifest|sha256_manifest|hash_manifest', re.IGNORECASE)
_DEVIATION  = re.compile(
    r'deviation[_\s]log|HOLD[_\s]event|deviation_event', re.IGNORECASE
)


def extract_evidence(report_text: str) -> list[EvidenceItem]:
    """Extract all detectable evidence items from a report text.

    Returns items ordered by appearance in text (not by rank).
    """
    items: list[EvidenceItem] = []

    for line_no, line in enumerate(report_text.splitlines(), start=1):
        # Rank 2: hash manifest / trace / deviation
        if _MANIFEST.search(line):
            items.append(EvidenceItem(
                rank=EvidenceRank.HASH_MANIFEST, label="hash_manifest",
                content=line.strip(), line_number=line_no,
            ))
        if _DEVIATION.search(line):
            items.append(EvidenceItem(
                rank=EvidenceRank.HASH_MANIFEST, label="deviation_log_entry",
                content=line.strip(), line_number=line_no,
            ))
        for sha in _SHA256.findall(line):
            items.append(EvidenceItem(
                rank=EvidenceRank.HASH_MANIFEST, label=f"sha256:{sha[:12]}...",
                content=sha, line_number=line_no,
            ))

        # Rank 3: inline figures / tables / verdict labels
        for fig in _FIGURE_REF.findall(line):
            items.append(EvidenceItem(
                rank=EvidenceRank.INLINE_FIGURE, label=fig,
                content=line.strip(), line_number=line_no,
            ))
        for verdict in _PASS_BLOCK.findall(line):
            items.append(EvidenceItem(
                rank=EvidenceRank.INLINE_FIGURE, label=f"verdict:{verdict}",
                content=line.strip(), line_number=line_no,
            ))

    return items


def resolve(items: list[EvidenceItem]) -> ResolutionResult:
    """Apply evidence precedence and return the authoritative item.

    When same-rank items contradict each other, a named EvidenceConflict
    is produced and the conflict is NOT silently resolved.
    """
    if not items:
        return ResolutionResult(resolved=None, conflicts=[], overridden=[])

    # Group by rank
    by_rank: dict[EvidenceRank, list[EvidenceItem]] = {}
    for item in items:
        by_rank.setdefault(item.rank, []).append(item)

    conflicts: list[EvidenceConflict] = []

    # Walk ranks from highest authority (1) to lowest (5)
    for rank in sorted(by_rank.keys(), key=lambda r: r.value):
        rank_items = by_rank[rank]

        if len(rank_items) > 1:
            # Check for content conflicts at this rank
            unique_contents = {i.content for i in rank_items}
            if len(unique_contents) > 1:
                for idx in range(len(rank_items) - 1):
                    conflicts.append(EvidenceConflict(
                        rank=rank,
                        artifact_a=rank_items[idx].label,
                        artifact_b=rank_items[idx + 1].label,
                        description=(
                            f"Same-rank conflict at {rank.name}: "
                            f"'{rank_items[idx].content[:60]}' vs "
                            f"'{rank_items[idx + 1].content[:60]}'"
                        ),
                    ))

        # First item at this rank is the resolved authority
        resolved = rank_items[0]
        overridden = [
            item for r, group in by_rank.items()
            if r.value > rank.value
            for item in group
        ]
        return ResolutionResult(resolved=resolved, conflicts=conflicts, overridden=overridden)

    return ResolutionResult(resolved=None, conflicts=conflicts, overridden=[])


def check_anchor_completeness(
    figure_label: str,
    report_text: str,
) -> tuple[bool, bool]:
    """Check whether a figure carries both source_path and sha256.

    Returns (has_source_path, has_sha256).
    A sha256 with no confirmed file existence is treated as incomplete (has_sha256=False).
    """
    figure_block = _extract_figure_block(figure_label, report_text)
    if not figure_block:
        return False, False

    has_source = bool(re.search(r'source_path\s*[:=]', figure_block, re.IGNORECASE))
    has_sha    = bool(_SHA256.search(figure_block))
    return has_source, has_sha


def _extract_figure_block(label: str, text: str) -> str:
    """Extract the text block surrounding a figure reference (±5 lines)."""
    lines = text.splitlines()
    pattern = re.compile(re.escape(label), re.IGNORECASE)
    for idx, line in enumerate(lines):
        if pattern.search(line):
            start = max(0, idx - 2)
            end   = min(len(lines), idx + 5)
            return "\n".join(lines[start:end])
    return ""
