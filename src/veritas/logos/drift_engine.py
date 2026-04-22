"""VERITAS DriftEngine -- round-to-round IRF score divergence tracker (v2.3.0).

Algorithms extracted from Flamehaven-LOGOS bridge/drift_controller.py
and bridge/omega_scorer.py, rewritten as VERITAS-native code with zero
external dependencies (stdlib only: math).

VERITAS adaptation: instead of IRF vs AATS path divergence, we measure
how much the IRF-6D score vector changes between consecutive critique rounds.
High round-to-round JSD indicates either a substantially revised report
(expected) or scoring instability (flag for review).

Thresholds (from SIDRCE CORE_ALGORITHMS.md / LOGOS DriftController defaults):
  JSD_MAX  = 0.06  -- CRITICAL: omega penalty collapses to 0
  JSD_WARN = 0.04  -- WARNING: close monitoring required
  L2_MAX   = 0.20  -- CRITICAL (6D normalized L2)
  L2_WARN  = 0.10  -- WARNING

Omega penalty formula (SIDRCE-gate, from LOGOS omega_scorer.py):
  penalized = omega * max(0, 1 - jsd / JSD_MAX)
  jsd=0.00 -> factor=1.00 (no change)
  jsd=0.03 -> factor=0.50 (WARNING midpoint)
  jsd=0.06 -> factor=0.00 (CRITICAL: omega collapses)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from ..types import IRF6DScores

# Thresholds — mirror LOGOS DriftController defaults
JSD_MAX: float = 0.06
JSD_WARN: float = 0.04
L2_MAX: float = 0.20
L2_WARN: float = 0.10


class DriftLevel(Enum):
    """Round-to-round IRF drift severity."""

    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class DriftMetrics:
    """Drift metrics between two consecutive IRF-6D score vectors.

    All float fields are rounded to 6 decimal places.
    """

    jsd: float
    l2: float
    level: DriftLevel
    should_halt: bool
    remediation: str | None
    omega_penalty_factor: float
    delta_omega: float
    round_from: int
    round_to: int

    def as_dict(self) -> dict:
        return {
            "jsd": self.jsd,
            "l2": self.l2,
            "level": self.level.value,
            "should_halt": self.should_halt,
            "remediation": self.remediation,
            "omega_penalty_factor": self.omega_penalty_factor,
            "delta_omega": self.delta_omega,
            "round_from": self.round_from,
            "round_to": self.round_to,
        }


# ---------------------------------------------------------------------------
# Internal math helpers (zero external deps)
# ---------------------------------------------------------------------------


def _irf_vector(scores: IRF6DScores) -> tuple[float, ...]:
    return (scores.M, scores.A, scores.D, scores.I, scores.F, scores.P)


def _to_distribution(vec: tuple[float, ...], smoothing: float = 1e-3) -> list[float]:
    """Laplace-smooth and normalize to probability distribution."""
    raw = [max(0.0, v) + smoothing for v in vec]
    total = sum(raw)
    return [v / total for v in raw]


def _kl_divergence(p: list[float], q: list[float]) -> float:
    """KL(p || q) in nats; skips zero-probability terms."""
    return sum(p[i] * math.log(p[i] / q[i]) for i in range(len(p)) if p[i] > 0.0 and q[i] > 0.0)


def _jsd(p: list[float], q: list[float]) -> float:
    """Jensen-Shannon divergence as a metric in [0, 1].

    Uses sqrt(JSD_base2) following scipy.spatial.distance.jensenshannon
    convention so that result is a proper distance metric.
    """
    m = [0.5 * (p[i] + q[i]) for i in range(len(p))]
    raw_nats = 0.5 * (_kl_divergence(p, m) + _kl_divergence(q, m))
    # Convert nats -> bits, take sqrt for metric form
    return min(1.0, math.sqrt(max(0.0, raw_nats) / math.log(2)))


def _normalized_l2(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """L2 distance normalized by sqrt(dim) for scale-invariant comparison."""
    n = len(a)
    if n == 0:
        return 0.0
    sq_sum = sum((a[i] - b[i]) ** 2 for i in range(n))
    return math.sqrt(sq_sum) / math.sqrt(n)


# ---------------------------------------------------------------------------
# DriftEngine
# ---------------------------------------------------------------------------


class DriftEngine:
    """Compute IRF score drift between consecutive VERITAS critique rounds.

    Zero external dependencies — uses pure Python stdlib math.

    Usage::

        engine = DriftEngine()
        metrics = engine.compute_round_drift(
            current_irf, prev_irf, round_from=1, round_to=2
        )
        penalized_omega = engine.apply_penalty(raw_omega, metrics.jsd)
    """

    def compute_round_drift(
        self,
        current: IRF6DScores,
        previous: IRF6DScores,
        round_from: int = 1,
        round_to: int = 2,
    ) -> DriftMetrics:
        """Compute drift metrics between two consecutive IRF6DScores.

        Args:
            current:    IRF scores from the current (new) critique round.
            previous:   IRF scores from the immediately prior round.
            round_from: Round number of the previous report.
            round_to:   Round number of the current report.

        Returns:
            DriftMetrics with JSD, L2, severity level, penalty factor, delta_omega.
        """
        vec_curr = _irf_vector(current)
        vec_prev = _irf_vector(previous)

        dist_curr = _to_distribution(vec_curr)
        dist_prev = _to_distribution(vec_prev)

        jsd = round(_jsd(dist_curr, dist_prev), 6)
        l2 = round(_normalized_l2(vec_curr, vec_prev), 6)

        if jsd >= JSD_MAX or l2 >= L2_MAX:
            level = DriftLevel.CRITICAL
            should_halt = True
            remediation: str | None = "halt_and_review"
        elif jsd >= JSD_WARN or l2 >= L2_WARN:
            level = DriftLevel.WARNING
            should_halt = False
            remediation = "monitor_closely"
        else:
            level = DriftLevel.NORMAL
            should_halt = False
            remediation = None

        omega_penalty_factor = round(max(0.0, 1.0 - jsd / JSD_MAX), 6)
        delta_omega = round(current.composite - previous.composite, 6)

        return DriftMetrics(
            jsd=jsd,
            l2=l2,
            level=level,
            should_halt=should_halt,
            remediation=remediation,
            omega_penalty_factor=omega_penalty_factor,
            delta_omega=delta_omega,
            round_from=round_from,
            round_to=round_to,
        )

    @staticmethod
    def apply_penalty(
        raw_omega: float,
        drift_jsd: float,
        jsd_gate: float = JSD_MAX,
    ) -> float:
        """Apply SIDRCE JSD-gate penalty to a raw omega score.

        Formula: omega * max(0, 1 - drift_jsd / jsd_gate)

        Args:
            raw_omega:  Unpenalized omega in [0, 1].
            drift_jsd:  JSD from compute_round_drift().
            jsd_gate:   Collapse threshold (default JSD_MAX=0.06).

        Returns:
            Penalized omega in [0, 1].
        """
        jsd_gate = max(1e-9, float(jsd_gate))
        factor = max(0.0, 1.0 - max(0.0, float(drift_jsd)) / jsd_gate)
        return round(max(0.0, min(1.0, float(raw_omega) * factor)), 6)
