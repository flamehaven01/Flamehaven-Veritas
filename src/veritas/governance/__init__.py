"""VERITAS governance module — CR-EP v2.7.2 native state machine."""

from .cr_ep_gate import (
    append_event,
    bootstrap,
    detect_state,
    read_log,
    validate_artifacts,
)

__all__ = [
    "bootstrap",
    "detect_state",
    "append_event",
    "read_log",
    "validate_artifacts",
]
