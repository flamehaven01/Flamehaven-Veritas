"""VERITAS MICA Session Store — extracted from MICA v0.2.3 (native, zero deps).

Source: D:\\Sanctum\\Flamehaven\\STRUCTURA\\AI TOOL\\3. 설계 모달\\
        Flamehaven MICA - Memory Invocation & Context Archive for AI\\0.2.3

Extracted algorithms:
  - detect_state()    from tools/mica_runtime.py:88-90
  - resolve_paths()   from tools/mica_runtime.py:93-111
  - count_invariants() from tools/mica_runtime.py:128-137
  - MICAStore lifecycle: start / show / log_di_violation / close
"""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ── Session state constants ────────────────────────────────────────────────────
STATE_INVOCATION = "INVOCATION_MODE"
STATE_LEGACY = "LEGACY_MODE"
STATE_INACTIVE = "INACTIVE"

STATUS_CLOSED = "CLOSED"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_INACTIVE = "INACTIVE"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _minimal_yaml_parse(text: str) -> dict[str, Any]:
    """Minimal YAML reader for key: value lines and - list items. No external deps."""
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*:", line):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip("\"'")
            result[key] = val or []
            current_key = key
        elif line.lstrip().startswith("- ") and current_key is not None:
            item = line.lstrip()[2:].strip().strip("\"'")
            if isinstance(result.get(current_key), list):
                result[current_key].append(item)
    return result


def _load_yaml(path: pathlib.Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import]

        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except ImportError:
        return _minimal_yaml_parse(text)


def _load_json_file(path: pathlib.Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except Exception:
        return {}


# ── Core state detection (adapted from mica_runtime.py) ───────────────────────


def _find_mica_yaml(root: pathlib.Path) -> pathlib.Path | None:
    for name in ("mica.yaml", "memory/mica.yaml", ".mica/mica.yaml"):
        p = root / name
        if p.exists():
            return p
    return None


def _find_legacy_archive(root: pathlib.Path) -> pathlib.Path | None:
    for p in root.rglob("*.mica.*.json"):
        return p
    return None


def detect_state(
    root: pathlib.Path,
) -> tuple[str, pathlib.Path | None, pathlib.Path | None]:
    """Return (state, mica_yaml_path, legacy_archive_path).

    States:
      INVOCATION_MODE  — mica.yaml found, active session
      LEGACY_MODE      — legacy .mica.*.json archive only
      INACTIVE         — no MICA artifacts present
    """
    mica_yaml = _find_mica_yaml(root)
    if mica_yaml:
        return (STATE_INVOCATION, mica_yaml, None)
    archive = _find_legacy_archive(root)
    if archive:
        return (STATE_LEGACY, None, archive)
    return (STATE_INACTIVE, None, None)


def resolve_paths(
    root: pathlib.Path,
    mica_yaml_path: pathlib.Path,
) -> tuple[dict[str, Any], pathlib.Path | None, pathlib.Path | None]:
    """Parse mica.yaml layers and return (yaml_dict, archive_path, playbook_path)."""
    yd = _load_yaml(mica_yaml_path)
    raw_layers = yd.get("layers", [])
    layers: list[Any] = raw_layers if isinstance(raw_layers, list) else []
    archive_path: pathlib.Path | None = None
    playbook_path: pathlib.Path | None = None
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        rel = layer.get("path")
        if not isinstance(rel, str):
            continue
        if layer.get("name") == "archive":
            archive_path = root / rel
        elif layer.get("name") == "playbook":
            playbook_path = root / rel
    return yd, archive_path, playbook_path


def count_invariants(
    archive: dict[str, Any],
) -> tuple[int, int, list[dict[str, Any]]]:
    """Return (critical_count, high_count, all_di_list).

    Extracted verbatim from mica_runtime.py:128-137.
    """
    dis = archive.get("design_invariants", [])
    if not isinstance(dis, list):
        return (0, 0, [])
    normalized = [d for d in dis if isinstance(d, dict)]
    crit = sum(1 for d in normalized if d.get("severity") == "critical")
    high = sum(1 for d in normalized if d.get("severity") == "high")
    return crit, high, normalized


# ── Session data types ─────────────────────────────────────────────────────────


@dataclass
class DIViolation:
    """A DI violation recorded from a critique run."""

    origin_episode: str
    lesson_ref: str
    triggered_at: str = field(default_factory=_now_iso)
    severity: str = "high"

    def as_dict(self) -> dict[str, Any]:
        return {
            "origin_episode": self.origin_episode,
            "lesson_ref": self.lesson_ref,
            "last_triggered": self.triggered_at,
            "violation_count": 1,
            "severity": self.severity,
        }


@dataclass
class SessionStatus:
    """Snapshot of the current MICA session state."""

    state: str
    contract: str
    mica_yaml: pathlib.Path | None
    critical_di: int
    high_di: int
    di_list: list[dict[str, Any]]

    def render(self) -> str:
        lines = [
            f"MICA state    : {self.state}",
            f"Contract      : {self.contract}",
            f"MICA yaml     : {self.mica_yaml or '(none)'}",
            f"DI critical   : {self.critical_di}",
            f"DI high       : {self.high_di}",
        ]
        return "\n".join(lines)


# ── MICAStore — lifecycle management ──────────────────────────────────────────

_MICA_YAML_TEMPLATE = """\
mica_spec: "0.2.3"
name: veritas-session
mode: memory_injection
description: "VERITAS critique session DI tracking"
layers:
  - name: archive
    path: memory/archive.mica.latest.json
  - name: playbook
    path: memory/playbook.md
"""


class MICAStore:
    """VERITAS MICA session manager (native extraction of MICA v0.2.3 lifecycle).

    Usage::

        store = MICAStore(project_root)
        store.start()
        status = store.show()
        store.log_di_violation(DIViolation(origin_episode="...", lesson_ref="..."))
        store.close()
    """

    def __init__(self, project_root: pathlib.Path | None = None) -> None:
        self.root = (project_root or pathlib.Path(".")).resolve()
        self._mem = self.root / "memory"

    @property
    def _yaml_path(self) -> pathlib.Path:
        return self._mem / "mica.yaml"

    @property
    def _archive_path(self) -> pathlib.Path:
        return self._mem / "archive.mica.latest.json"

    @property
    def _playbook_path(self) -> pathlib.Path:
        return self._mem / "playbook.md"

    def start(self) -> str:
        """Initialize MICA session files. Returns resulting state string."""
        self._mem.mkdir(parents=True, exist_ok=True)
        if not self._yaml_path.exists():
            self._yaml_path.write_text(_MICA_YAML_TEMPLATE, encoding="utf-8")
        if not self._archive_path.exists():
            self._archive_path.write_text(
                json.dumps(
                    {
                        "mica_spec": "0.2.3",
                        "session_started": _now_iso(),
                        "session_closed": None,
                        "design_invariants": [],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        if not self._playbook_path.exists():
            self._playbook_path.write_text(
                "# VERITAS MICA Playbook\n\nDI violations are tracked here.\n",
                encoding="utf-8",
            )
        return STATE_INVOCATION

    def show(self) -> SessionStatus:
        """Inspect current MICA state and DI counts."""
        state, mica_yaml, _ = detect_state(self.root)
        crit, high, dis = 0, 0, []  # type: ignore[var-annotated]
        if state == STATE_INVOCATION and mica_yaml is not None:
            _, archive_path, _ = resolve_paths(self.root, mica_yaml)
            if archive_path is not None and archive_path.exists():
                archive = _load_json_file(archive_path)
                crit, high, dis = count_invariants(archive)
        contract = self._compute_contract(state)
        return SessionStatus(
            state=state,
            contract=contract,
            mica_yaml=mica_yaml,
            critical_di=crit,
            high_di=high,
            di_list=dis,
        )

    def log_di_violation(self, violation: DIViolation) -> None:
        """Append a DI violation to the archive."""
        if not self._archive_path.exists():
            self.start()
        archive = _load_json_file(self._archive_path)
        dis: list[dict[str, Any]] = archive.get("design_invariants", [])
        dis.append(violation.as_dict())
        archive["design_invariants"] = dis
        self._archive_path.write_text(json.dumps(archive, indent=2), encoding="utf-8")

    def close(self) -> None:
        """Mark session as closed (writes close timestamp to archive)."""
        if self._archive_path.exists():
            archive = _load_json_file(self._archive_path)
            archive["session_closed"] = _now_iso()
            self._archive_path.write_text(json.dumps(archive, indent=2), encoding="utf-8")

    def _compute_contract(self, state: str) -> str:
        if state == STATE_INACTIVE:
            return STATUS_INACTIVE
        if not self._yaml_path.exists() or not self._archive_path.exists():
            return STATUS_INCOMPLETE
        return STATUS_CLOSED
