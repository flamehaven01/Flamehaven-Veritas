"""DomainRuleset — the atomic unit of LOGOS IRF domain extension.

A frozen dataclass carrying the six IRF-6D marker banks and scoring
thresholds for a specific academic discipline.

Instantiate directly or subclass for typed marker sets::

    from veritas.logos.domain.base import DomainRuleset

    MY_DOMAIN = DomainRuleset(
        domain_key="physics",
        name="Experimental Physics",
        m_markers=("uncertainty", "error bar", "systematic error", ...),
        ...
    )

All marker strings are matched case-insensitively against lower-cased text.
Tuples are used (not lists) for hashability — DomainRuleset is frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DomainRuleset:
    """Immutable IRF-6D scoring ruleset for a single academic domain.

    Attributes:
        domain_key           Short identifier used in CLI / API (e.g. ``"cs"``).
        name                 Human-readable domain name.
        m_markers            Methodic Doubt marker strings.
        a_markers            Axiom / Hypothesis marker strings.
        d_markers            Deduction / Inference marker strings.
        i_markers            Induction / Empirical support marker strings.
        f_markers            Falsification / Reproducibility marker strings.
        p_markers            Paradigm / Prior-work marker strings.
        composite_threshold  Minimum composite score to pass (default 0.65).
        component_min        Minimum per-dimension score (default 0.30).
        saturate_at          Dict mapping dimension key to saturation count.
                             Missing keys default to 4.
    """

    domain_key: str
    name: str
    m_markers: tuple[str, ...]
    a_markers: tuple[str, ...]
    d_markers: tuple[str, ...]
    i_markers: tuple[str, ...]
    f_markers: tuple[str, ...]
    p_markers: tuple[str, ...]
    composite_threshold: float = 0.65
    component_min: float = 0.30
    saturate_at: dict = field(
        default_factory=lambda: {"M": 4, "A": 4, "D": 4, "I": 5, "F": 5, "P": 4},
        compare=False,
        hash=False,
    )

    def markers_for(self, dim: str) -> tuple[str, ...]:
        """Return marker tuple for dimension key (M/A/D/I/F/P).

        Raises KeyError for unknown dimension.
        """
        _map = {
            "M": self.m_markers,
            "A": self.a_markers,
            "D": self.d_markers,
            "I": self.i_markers,
            "F": self.f_markers,
            "P": self.p_markers,
        }
        if dim not in _map:
            raise KeyError(f"Unknown IRF dimension '{dim}'. Valid: M A D I F P")
        return _map[dim]

    def saturation(self, dim: str) -> int:
        """Return saturation count for dimension. Defaults to 4 if not set."""
        return self.saturate_at.get(dim, 4)
