"""SciExp SPAR runtime — wires Layer A/B/C + registry for the sciexp domain."""

from __future__ import annotations

from .layer_a import build_layer_a
from .layer_b import build_layer_b
from .layer_c import build_layer_c
from .registry_seed import sciexp_registry_snapshots

try:
    from spar_framework.engine import ReviewRuntime  # type: ignore[import]

    _SPAR_AVAILABLE = True
except ImportError:
    ReviewRuntime = None  # type: ignore[assignment,misc]
    _SPAR_AVAILABLE = False


def get_review_runtime():  # type: ignore[return]
    """Return a ReviewRuntime configured for the sciexp domain.

    Raises ImportError if spar-framework is not installed.
    """
    if not _SPAR_AVAILABLE:
        raise ImportError(
            "spar-framework is required for SPAR review. "
            "Install with: pip install 'flamehaven-veritas[spar]'"
        )
    snaps = sciexp_registry_snapshots()
    return ReviewRuntime(
        build_layer_a=build_layer_a,
        build_layer_b=build_layer_b,
        build_layer_c=build_layer_c,
        build_model_registry_snapshot=lambda: snaps["model_registry_snapshot"],
        build_gap_registry_snapshot=lambda: snaps["gap_registry_snapshot"],
        slop_check=None,
    )
