"""Fallback types for when spar-framework is not installed.

Used so that layer_a/b/c can be imported without spar-framework present.
The interface matches spar_framework.result_types.CheckResult exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    """Minimal CheckResult compatible with spar_framework.result_types.CheckResult."""

    check_id: str
    label: str
    status: str
    detail: str = ""
    meta: dict[str, object] = field(default_factory=dict)
