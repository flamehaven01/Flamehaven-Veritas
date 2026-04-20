"""Hybrid omega fusion for VERITAS — AI Critique Experimental Report Analysis Framework.

Combines:
  sciexp_omega  — traceability-derived omega from pipeline (0-1)
  logos_omega   — LOGOS IRF composite score (0-1)

Formula (configurable weights, default 60/40):
  hybrid_omega = W_SCIEXP * sciexp_omega + W_LOGOS * logos_omega

F-dimension penalty: if IRF-F (Falsification) < F_WARN_THRESHOLD, a
risk flag is raised and a 0.05 penalty is applied to hybrid_omega.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..types import IRF6DScores

# Default fusion weights
W_SCIEXP: float = 0.60
W_LOGOS:  float = 0.40

# Falsification risk gate
F_WARN_THRESHOLD: float = 0.40


@dataclass
class FusionResult:
    sciexp_omega:  float
    logos_omega:   float
    hybrid_omega:  float
    f_risk:        bool     # True when Falsification dim < F_WARN_THRESHOLD
    f_risk_msg:    Optional[str]


class OmegaFusion:
    """Fuse SCI-EXP and LOGOS omega scores into a hybrid score.

    Usage::

        fusion = OmegaFusion()
        result = fusion.fuse(sciexp_omega=0.72, irf_scores=scores)
    """

    def __init__(
        self,
        w_sciexp: float = W_SCIEXP,
        w_logos:  float = W_LOGOS,
    ) -> None:
        total = w_sciexp + w_logos
        self.w_sciexp = w_sciexp / total
        self.w_logos  = w_logos  / total

    def fuse(
        self,
        sciexp_omega: float,
        irf_scores:   Optional[IRF6DScores],
    ) -> FusionResult:
        """Compute hybrid omega.

        When irf_scores is None (LOGOS unavailable), hybrid_omega == sciexp_omega.
        """
        if irf_scores is None:
            return FusionResult(
                sciexp_omega=sciexp_omega,
                logos_omega=sciexp_omega,
                hybrid_omega=round(sciexp_omega, 4),
                f_risk=False,
                f_risk_msg=None,
            )

        logos_omega  = irf_scores.composite
        raw_hybrid   = self.w_sciexp * sciexp_omega + self.w_logos * logos_omega
        f_risk       = irf_scores.F < F_WARN_THRESHOLD
        f_risk_msg: Optional[str] = None

        if f_risk:
            raw_hybrid   = max(0.0, raw_hybrid - 0.05)
            f_risk_msg   = (
                f"F-dimension (Falsification) = {irf_scores.F:.2f} < "
                f"{F_WARN_THRESHOLD:.2f}: reproducibility or testability "
                "evidence is insufficient. Apply 0.05 omega penalty."
            )

        return FusionResult(
            sciexp_omega=round(sciexp_omega, 4),
            logos_omega=round(logos_omega, 4),
            hybrid_omega=round(raw_hybrid, 4),
            f_risk=f_risk,
            f_risk_msg=f_risk_msg,
        )
