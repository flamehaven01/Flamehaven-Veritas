"""VERITAS CR-EP Governance Gate — extracted from CR-EP v2.7.2 (native, zero deps).

Source: D:\\Sanctum\\CR-EP v 2.7.2\\src\\cr_ep\\cli.py

Extracted algorithms:
  - detect_state()       state machine from artifact presence (lines 323-345)
  - check_violations()   guard conditions (lines 250-265)
  - bootstrap()          .cr-ep/ init with profile selection (lines 179-250)
  - append_event()       enforcement_log.jsonl append (change_event.schema.json)
  - validate_artifacts() required-field validation (lines 281-320)

State order: INIT → CONTEXT_RESOLVED → WHY_VALIDATED →
             SCOPE_DECLARED → EXECUTING → REVIEW_REQUIRED →
             APPROVAL_PENDING → CLOSED
"""

from __future__ import annotations

import contextlib
import json
import pathlib
import uuid
from datetime import datetime, timezone
from typing import Any

# ── State constants ────────────────────────────────────────────────────────────

STATE_ORDER = [
    "INIT",
    "CONTEXT_RESOLVED",
    "WHY_VALIDATED",
    "SCOPE_DECLARED",
    "EXECUTING",
    "REVIEW_REQUIRED",
    "APPROVAL_PENDING",
    "CLOSED",
]


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _session_id() -> str:
    return f"veritas-{uuid.uuid4().hex[:8]}"


def _write_json(path: pathlib.Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except Exception:
        return {}


# ── State machine ──────────────────────────────────────────────────────────────


def detect_state(root: pathlib.Path) -> str:
    """Infer current CR-EP state from artifact presence.

    Mirrors cr_ep/cli.py detect_state() (lines 323-345).
    Returns one of STATE_ORDER values.
    """
    crep = root / ".cr-ep"
    if not crep.exists() or not (crep / "session.json").exists():
        return "INIT"
    if not (crep / "why_gate.json").exists():
        return "CONTEXT_RESOLVED"
    if not (crep / "scope_declaration.json").exists():
        return "WHY_VALIDATED"
    if not (crep / "review_contract.json").exists():
        return "EXECUTING"
    review_data = _load_json(crep / "review_contract.json")
    approval = crep / "approval_bridge.json"
    if review_data.get("approval_required"):
        if approval.exists():
            ap_data = _load_json(approval)
            if ap_data.get("approval_status") in {"approved", "not_required"}:
                return "CLOSED"
            return "APPROVAL_PENDING"
        return "REVIEW_REQUIRED"
    return "CLOSED"


def check_violations(root: pathlib.Path) -> list[str]:
    """Return illegal state transitions (guard conditions).

    Mirrors cr_ep/cli.py check_state() (lines 250-265).
    """
    crep = root / ".cr-ep"
    errors: list[str] = []
    if (crep / "scope_declaration.json").exists() and not (crep / "why_gate.json").exists():
        errors.append("Illegal: scope_declaration.json exists before why_gate.json")
    if (crep / "approval_bridge.json").exists() and not (crep / "review_contract.json").exists():
        errors.append("Illegal: approval_bridge.json exists before review_contract.json")
    return errors


# ── Bootstrap ──────────────────────────────────────────────────────────────────

_PROFILE_FILES: dict[str, list[str]] = {
    "nano": ["session.json"],
    "lite": ["session.json"],
    "standard": [
        "session.json",
        "why_gate.json",
        "scope_declaration.json",
        "review_contract.json",
    ],
    "full": [
        "session.json",
        "why_gate.json",
        "scope_declaration.json",
        "review_contract.json",
        "approval_bridge.json",
    ],
}


def bootstrap(root: pathlib.Path, profile: str = "standard") -> str:
    """Initialize .cr-ep/ governance directory. Returns initial state string.

    Mirrors cr_ep/cli.py bootstrap() (lines 179-250).
    """
    crep = root / ".cr-ep"
    crep.mkdir(parents=True, exist_ok=True)
    (crep / "tmp").mkdir(exist_ok=True)

    sid = _session_id()
    now = _now_utc()

    payloads: dict[str, dict[str, Any]] = {
        "session.json": {
            "cr_ep_version": "2.7.2",
            "session_id": sid,
            "mode": profile,
            "trust_tier": "HUMAN",
            "working_path": str(root),
            "started_at_utc": now,
            "dm1_metric": "files",
            "dt3_review_threshold": 5,
            "mode_upgrade_history": [],
        },
        "why_gate.json": {
            "wq_1": "warn",
            "wq_2": "warn",
            "wq_3": "warn",
            "q3_scaffold_used": False,
            "q3_results": {"q3a": "fail", "q3b": "fail", "q3c": "fail", "q3d": "fail"},
            "declared_why": "fill before governed execution",
        },
        "scope_declaration.json": {
            "depends_on_why_gate": True,
            "why_gate_snapshot_wq1": "warn",
            "generated_after_utc": now,
            "planned_files": 0,
            "planned_touchpoints": [],
            "sd0_confirmed": False,
            "actual_files": 0,
            "actual_score": 0.0,
            "overshoot_ratio": 0.0,
            "overshoot_formula": "actual / planned",
            "overshoot_interpretation": "<= 1.0 within scope; > 1.0 overshoot",
            "dm1_triggered": False,
        },
        "review_contract.json": {
            "declared_why": "fill before review",
            "risk_score": 0.0,
            "scope_variance": 0.0,
            "drift_events": [],
            "hard_line_conflicts": [],
            "required_revalidation": [],
            "approval_required": False,
            "artifact_consistency": "unknown",
        },
        "approval_bridge.json": {
            "approval_required": False,
            "reason": "",
            "required_approvers": [],
            "approval_status": "not_required",
            "expiry_utc": "",
        },
    }

    for name in _PROFILE_FILES.get(profile, _PROFILE_FILES["standard"]):
        p = crep / name
        if not p.exists():
            _write_json(p, payloads[name])

    log_path = crep / "enforcement_log.jsonl"
    if not log_path.exists():
        log_path.write_text("", encoding="utf-8")

    append_event(root, "PROJECT_KICKOFF", f"Bootstrap profile={profile}")
    return detect_state(root)


# ── Enforcement log ────────────────────────────────────────────────────────────


def append_event(
    root: pathlib.Path,
    event_type: str,
    reason: str = "",
    evidence: list[str] | None = None,
) -> None:
    """Append JSON event to .cr-ep/enforcement_log.jsonl (append-only).

    Schema from change_event.schema.json required fields:
      event_type, ts_utc, session_id, reason
    """
    crep = root / ".cr-ep"
    crep.mkdir(exist_ok=True)
    log_path = crep / "enforcement_log.jsonl"
    session_id = _load_json(crep / "session.json").get("session_id", "unknown")
    ev = {
        "event_type": event_type,
        "ts_utc": _now_utc(),
        "session_id": session_id,
        "reason": reason,
        "evidence_paths": evidence or [],
    }
    with log_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(ev) + "\n")


def read_log(root: pathlib.Path) -> list[dict[str, Any]]:
    """Parse enforcement_log.jsonl and return list of event dicts."""
    log_path = root / ".cr-ep" / "enforcement_log.jsonl"
    if not log_path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            with contextlib.suppress(json.JSONDecodeError):
                items.append(json.loads(stripped))
    return items


# ── Validation ─────────────────────────────────────────────────────────────────

_REQUIRED_FIELDS: dict[str, list[str]] = {
    "session.json": ["cr_ep_version", "session_id", "mode", "trust_tier"],
    "why_gate.json": ["wq_1", "wq_2", "wq_3", "declared_why"],
    "scope_declaration.json": ["planned_files", "sd0_confirmed", "overshoot_ratio"],
    "review_contract.json": ["risk_score", "approval_required"],
}


def validate_artifacts(root: pathlib.Path) -> list[str]:
    """Validate .cr-ep/ artifacts. Returns list of error strings (empty = valid).

    Mirrors cr_ep/cli.py validate_artifacts() (lines 281-320).
    """
    crep = root / ".cr-ep"
    if not crep.exists():
        return ["Missing .cr-ep directory"]
    errors: list[str] = []
    for filename, required in _REQUIRED_FIELDS.items():
        p = crep / filename
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{filename}: invalid JSON ({exc})")
            continue
        for field_name in required:
            if field_name not in data:
                errors.append(f"{filename}: missing field '{field_name}'")
    errors.extend(check_violations(root))
    return errors
