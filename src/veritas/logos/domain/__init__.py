"""Domain plugin subsystem for VERITAS LOGOS IRF-6D scoring.

Built-in domains: biomedical (default), cs, math.
External plugins register via entry_points group 'veritas.domains'.

Usage::

    from veritas.logos.domain import get_domain, list_domain_keys
    ruleset = get_domain("cs")
    print(ruleset.name, ruleset.composite_threshold)
"""

from .base import DomainRuleset
from .registry import DomainRegistry, get_domain, list_domain_keys, register_domain

__all__ = [
    "DomainRuleset",
    "DomainRegistry",
    "get_domain",
    "list_domain_keys",
    "register_domain",
]
