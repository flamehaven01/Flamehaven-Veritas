"""DomainRegistry — registration, discovery, and retrieval of domain rulesets.

Built-in domains (biomedical, cs, math) are registered lazily on first access.
External packages register via Python entry_points group 'veritas.domains'::

    # In third-party package's pyproject.toml:
    [project.entry-points."veritas.domains"]
    physics = "my_veritas_physics:PHYSICS_RULESET"

Thread-safety: registry mutation happens only at import time or via
explicit register() calls. Reads are safe across threads.
"""

from __future__ import annotations

import importlib.metadata
import logging
from collections.abc import Iterator

from .base import DomainRuleset

_log = logging.getLogger(__name__)

_ENTRY_POINTS_GROUP = "veritas.domains"


class DomainRegistry:
    """Singleton registry for IRF domain rulesets.

    Use module-level helpers ``get_domain``, ``register_domain``,
    ``list_domain_keys`` instead of instantiating directly.
    """

    def __init__(self) -> None:
        self._store: dict[str, DomainRuleset] = {}
        self._built_ins_loaded = False

    def _ensure_built_ins(self) -> None:
        if self._built_ins_loaded:
            return
        self._built_ins_loaded = True
        from .biomedical import BIOMEDICAL
        from .cs import CS
        from .math import MATH

        for ruleset in (BIOMEDICAL, CS, MATH):
            self._store[ruleset.domain_key] = ruleset
        self._scan_entry_points()

    def _scan_entry_points(self) -> None:
        """Load external domain plugins via entry_points."""
        try:
            eps = importlib.metadata.entry_points(group=_ENTRY_POINTS_GROUP)
        except Exception:
            return
        for ep in eps:
            try:
                obj = ep.load()
                if isinstance(obj, DomainRuleset):
                    self._store[obj.domain_key] = obj
                    _log.debug("Loaded domain plugin '%s' from %s", obj.domain_key, ep.value)
                else:
                    _log.warning(
                        "Entry point '%s' did not return a DomainRuleset; skipped.", ep.name
                    )
            except Exception as exc:  # noqa: BLE001
                _log.warning("Failed to load domain plugin '%s': %s", ep.name, exc)

    def register(self, ruleset: DomainRuleset) -> None:
        """Register a domain ruleset. Overwrites existing key."""
        if not isinstance(ruleset, DomainRuleset):
            raise TypeError(f"Expected DomainRuleset, got {type(ruleset).__name__}")
        self._ensure_built_ins()
        self._store[ruleset.domain_key] = ruleset

    def get(self, key: str) -> DomainRuleset:
        """Return ruleset for key. Raises KeyError for unknown domain."""
        self._ensure_built_ins()
        key = key.lower().strip()
        if key not in self._store:
            valid = ", ".join(sorted(self._store))
            raise KeyError(f"Unknown domain '{key}'. Valid: {valid}")
        return self._store[key]

    def list_keys(self) -> list[str]:
        """Return sorted list of all registered domain keys."""
        self._ensure_built_ins()
        return sorted(self._store)

    def __iter__(self) -> Iterator[DomainRuleset]:
        self._ensure_built_ins()
        return iter(self._store.values())


# Module-level singleton
_registry = DomainRegistry()


def get_domain(key: str) -> DomainRuleset:
    """Return DomainRuleset for *key*. Raises KeyError for unknown domain."""
    return _registry.get(key)


def register_domain(ruleset: DomainRuleset) -> None:
    """Register a custom domain ruleset into the global registry."""
    _registry.register(ruleset)


def list_domain_keys() -> list[str]:
    """Return sorted list of all registered domain keys."""
    return _registry.list_keys()
