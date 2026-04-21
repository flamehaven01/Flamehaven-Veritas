"""PRECHECK — Artifact Sufficiency Gate.

Executes before STEP 0. Determines which SciExpMode applies and
names all missing artifacts precisely.

Protocol rules:
- FULL     -> all 6 artifact classes present
- PARTIAL  -> primary claim evaluable; at least one secondary element missing
- LIMITED  -> at least one primary-claim artifact missing; one central claim evaluable
- BLOCKED  -> report body absent or no evaluable claim at all

The engine never infers missing artifacts. Absent = absent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .types import PrecheckResult, SciExpMode

# ---------------------------------------------------------------------------
# Artifact presence heuristics
# ---------------------------------------------------------------------------

_HASH_PATTERN = re.compile(r"\b[0-9a-fA-F]{64}\b")  # SHA-256 hex
_SOURCE_PATH = re.compile(r"source_path\s*[:=]|src_path\s*[:=]", re.IGNORECASE)
_VERDICT_LABEL = re.compile(r"\b(PASS|BLOCK|HOLD)\b")
_DEVIATION_LOG = re.compile(r"deviation[_\s]log|HOLD\s+event|rerun|path\s+change", re.IGNORECASE)
_PRIOR_CYCLE = re.compile(r"EXP-\d{3}|prior[_\s]cycle|previous[_\s]cycle", re.IGNORECASE)
_MANIFEST = re.compile(r"manifest|hash[_\s]manifest|sha256[_\s]manifest", re.IGNORECASE)
_CROSS_CYCLE = re.compile(
    r"(compare|comparison|cross[_\s]cycle|EXP-\d{3}.*EXP-\d{3})",
    re.IGNORECASE,
)


@dataclass
class _ArtifactFlags:
    has_report_body: bool
    has_verdict_figures: bool
    has_source_anchors: bool
    has_hash_manifest: bool
    has_deviation_log: bool
    has_prior_cycle_ref: bool
    cross_cycle_claimed: bool
    hold_language_found: bool


def _scan(text: str) -> _ArtifactFlags:
    return _ArtifactFlags(
        has_report_body=len(text.strip()) > 200,
        has_verdict_figures=bool(_VERDICT_LABEL.search(text)),
        has_source_anchors=bool(_SOURCE_PATH.search(text)),
        has_hash_manifest=bool(_HASH_PATTERN.search(text) or _MANIFEST.search(text)),
        has_deviation_log=bool(_DEVIATION_LOG.search(text)),
        has_prior_cycle_ref=bool(_PRIOR_CYCLE.search(text)),
        cross_cycle_claimed=bool(_CROSS_CYCLE.search(text)),
        hold_language_found=bool(re.search(r"\bHOLD\b|rerun|path\s+change", text, re.IGNORECASE)),
    )


# ---------------------------------------------------------------------------
# Mode determination
# ---------------------------------------------------------------------------


def _classify_mode(missing: list[str]) -> SciExpMode:
    """Determine PRECHECK mode from the missing-artifact list."""
    if not missing:
        return SciExpMode.FULL
    if "verdict_bearing_figures" in missing:
        # Primary claim artifact absent — body present → LIMITED
        return SciExpMode.LIMITED
    # Primary claim evaluable; only secondary elements missing
    return SciExpMode.PARTIAL


def run(report_text: str) -> PrecheckResult:
    """Execute the PRECHECK gate.

    Returns PrecheckResult with mode and list of missing artifact names.
    Does NOT repair or infer missing evidence.
    """
    f = _scan(report_text)
    missing: list[str] = []

    # Primary-claim blockers
    if not f.has_report_body:
        return PrecheckResult(
            mode=SciExpMode.BLOCKED,
            missing_artifacts=["report_body"],
        )

    if not f.has_verdict_figures:
        missing.append("verdict_bearing_figures")

    # Secondary traceability elements
    if not f.has_source_anchors:
        missing.append("source_path_anchors")

    if not f.has_hash_manifest:
        missing.append("sha256_hash_manifest")

    if f.hold_language_found and not f.has_deviation_log:
        missing.append("deviation_log")

    if f.cross_cycle_claimed and not f.has_prior_cycle_ref:
        missing.append("prior_cycle_reference_material")

    return PrecheckResult(mode=_classify_mode(missing), missing_artifacts=missing)
