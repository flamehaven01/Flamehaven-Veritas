"""VERITAS Reviewer — peer-review simulation engine (Phase 3, v3.2.0)."""

from .consensus import ConsensusResult, CrossValidator, check_consensus
from .dr3 import DR3Protocol, DR3Resolution
from .engine import PersonaReview, ReviewSimEngine, ReviewSimResult
from .persona import BALANCED, LENIENT, STRICT, PersonaConfig, calibrate_omega

__all__ = [
    "PersonaConfig",
    "calibrate_omega",
    "STRICT",
    "BALANCED",
    "LENIENT",
    "ConsensusResult",
    "CrossValidator",
    "check_consensus",
    "DR3Protocol",
    "DR3Resolution",
    "PersonaReview",
    "ReviewSimEngine",
    "ReviewSimResult",
]
