"""SciExp SPAR runtime — wires Layer A/B/C + registry for the sciexp domain."""

from __future__ import annotations

from spar_framework.engine import ReviewRuntime

from .layer_a import build_layer_a
from .layer_b import build_layer_b
from .layer_c import build_layer_c
from .registry_seed import sciexp_registry_snapshots


def get_review_runtime() -> ReviewRuntime:
    """Return a ReviewRuntime configured for the sciexp (experimental report) domain."""
    snaps = sciexp_registry_snapshots()
    return ReviewRuntime(
        build_layer_a=build_layer_a,
        build_layer_b=build_layer_b,
        build_layer_c=build_layer_c,
        build_model_registry_snapshot=lambda: snaps["model_registry_snapshot"],
        build_gap_registry_snapshot=lambda: snaps["gap_registry_snapshot"],
        slop_check=None,
    )
