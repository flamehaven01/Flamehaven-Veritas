"""VERITAS — AI Critique Experimental Report Analysis Framework — STEP 0-5 Analysis Pipeline.

Each step follows the OUTPUT CONTRACT strictly:
  STEP 0 : max 2 lines
  STEP 1-4: 1 paragraph, max 4 sentences
  STEP 5  : exactly 2 sentences
"""

from __future__ import annotations

import re

from .types import (
    ExperimentClass,
    HoldDisposition,
    HoldEvent,
    StepFinding,
    StepResult,
    TraceabilityClass,
)

# ── STEP 0 ────────────────────────────────────────────────────────────────────

_EXP_PATTERNS: list[tuple[re.Pattern, ExperimentClass]] = [
    (
        re.compile(r"\b(reproduc|parity|identity.verif|baseline.repro)", re.I),
        ExperimentClass.PARITY,
    ),
    (re.compile(r"\b(root.cause|RCA|failure.analysis|patch.verif)", re.I), ExperimentClass.RCA),
    (re.compile(r"\b(ablat|turn.off|turn.on|component.removed)", re.I), ExperimentClass.ABLATION),
    (
        re.compile(r"\b(multi.axis|cross.cycle|EXP-\d{3}.*EXP-\d{3})", re.I),
        ExperimentClass.MULTIAXIS,
    ),
    (re.compile(r"\b(extend|new.component|added.signal|augment)", re.I), ExperimentClass.EXTENSION),
]


def step0_classify(text: str) -> tuple[ExperimentClass, ExperimentClass | None, str]:
    matched: list[ExperimentClass] = []
    for pattern, cls in _EXP_PATTERNS:
        if pattern.search(text):
            matched.append(cls)
    if not matched:
        return (
            ExperimentClass.EXTENSION,
            None,
            "No explicit class markers found; defaulting to EXTENSION.",
        )
    primary = matched[0]
    secondary = matched[1] if len(matched) > 1 else None
    reason = f"Deciding keyword pattern matched for {primary.value}."
    return primary, secondary, reason


# ── STEP 1 — Claim Integrity (40%) ────────────────────────────────────────────

_SCOPE_VIOLATION = re.compile(
    r"\b(therefore|proves|demonstrates|confirms|definitively|it is clear that|"
    r"physical yield|real.world improvement|superior|outperforms)\b",
    re.I,
)
_HOLD_RE = re.compile(r"\bHOLD\b")
_PASS_RE = re.compile(r"\bPASS(?:_\w+)?\b")
_BLOCK_RE = re.compile(r"\bBLOCK(?:_\w+)?\b")
_NUMBER_RE = re.compile(r"\d+\.?\d*\s*(%|ms|s\b|fps|score|accuracy)")


def _extract_central_claim(text: str) -> str:
    for marker in ("abstract", "objective", "aim", "purpose", "we report", "we present"):
        idx = text.lower().find(marker)
        if idx != -1:
            return text[idx : idx + 200].replace("\n", " ").strip()
    return text[:200].replace("\n", " ").strip()


def _find_scope_violations(text: str) -> list[str]:
    return [m.group(0) for m in _SCOPE_VIOLATION.finditer(text)]


def _find_hold_events(text: str) -> list[HoldEvent]:
    events: list[HoldEvent] = []
    for i, m in enumerate(_HOLD_RE.finditer(text)):
        surrounding = text[max(0, m.start() - 120) : m.end() + 200]
        cause_stated = bool(re.search(r"(because|due to|caused by|reason)", surrounding, re.I))
        disposition_str = surrounding.lower()
        if "isolated" in disposition_str:
            disp = HoldDisposition.ISOLATED
        elif "patch" in disposition_str:
            disp = HoldDisposition.PATCHED
        elif "carry" in disposition_str or "forward" in disposition_str:
            disp = HoldDisposition.CARRIED_FORWARD
        else:
            disp = HoldDisposition.UNDOCUMENTED
        not_failure_claim = bool(re.search(r"not\s+a\s+fail", surrounding, re.I))
        data_support = bool(_NUMBER_RE.search(surrounding))
        events.append(
            HoldEvent(
                event_id=f"HOLD-{i + 1:02d}",
                cause_stated=cause_stated,
                disposition=disp,
                characterization="not a failure" if not_failure_claim else "",
                traceable_to_data=data_support,
            )
        )
    return events


def step1_claim_integrity(text: str) -> tuple[StepResult, list[HoldEvent]]:
    claim = _extract_central_claim(text)
    viols = _find_scope_violations(text)
    holds = _find_hold_events(text)
    verdicts = _PASS_RE.findall(text) + _BLOCK_RE.findall(text)
    has_numbers_near_verdicts = bool(_NUMBER_RE.search(text))

    findings: list[StepFinding] = []

    # 1.1 Central claim
    tc_claim = TraceabilityClass.TRACEABLE if bool(claim) else TraceabilityClass.NOT_TRACEABLE
    findings.append(StepFinding("1.1", f"Central claim identified: '{claim[:80]}...'", tc_claim))

    # 1.2 Scope boundary
    if viols:
        quote = next((v for v in viols), None)
        findings.append(
            StepFinding(
                "1.2",
                f"Scope boundary violation: {len(viols)} overreaching term(s) detected.",
                TraceabilityClass.NOT_TRACEABLE,
                verbatim_quote=quote,
            )
        )
    else:
        findings.append(
            StepFinding("1.2", "No scope boundary violation detected.", TraceabilityClass.TRACEABLE)
        )

    # 1.3 Verdict legitimacy
    tc_verdict = (
        TraceabilityClass.TRACEABLE
        if (verdicts and has_numbers_near_verdicts)
        else (
            TraceabilityClass.PARTIALLY_TRACEABLE if verdicts else TraceabilityClass.NOT_TRACEABLE
        )
    )
    findings.append(StepFinding("1.3", f"{len(verdicts)} verdict label(s) found.", tc_verdict))

    # 1.4 HOLD handling
    for h in holds:
        tc_hold = TraceabilityClass.TRACEABLE if h.cause_stated else TraceabilityClass.NOT_TRACEABLE
        findings.append(
            StepFinding(
                "1.4", f"{h.event_id}: disposition={h.disposition.value}", tc_hold, hold_event=h
            )
        )

    viol_sentence = (
        f"Scope boundary overreach at '{viols[0]}' is the most vulnerable claim."
        if viols
        else "Verdict legitimacy is the most vulnerable point when numeric traceability is absent."
    )

    scope_part = f" Scope boundary {'is violated by overreaching language' if viols else 'holds'}."
    verdict_part = f" Verdict labels are {tc_verdict.value} to measured values."
    hold_part = (
        f" {len(holds)} HOLD event(s) detected; {sum(1 for h in holds if not h.cause_stated)} lack stated cause."
        if holds
        else ""
    )

    prose = (
        f"The central claim is {tc_claim.value} from the report body.{scope_part}"
        f"{verdict_part}{hold_part}"
    )

    result = StepResult(
        step_id="1",
        weight=0.40,
        prose=prose,
        findings=findings,
        vulnerable_claim=viol_sentence,
    )
    return result, holds


# ── STEP 2 — Traceability Audit (30%) ─────────────────────────────────────────

_SOURCE_PATH_RE = re.compile(r"source_path\s*[:=]\s*\S+", re.I)
_SHA256_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")
_FIGURE_RE = re.compile(r"(Figure\s*\d+|Table\s*\d+)", re.I)
_CROSS_CYCLE_RE = re.compile(r"EXP-(\d{3})", re.I)


def step2_traceability(text: str, holds: list[HoldEvent]) -> StepResult:
    figures = _FIGURE_RE.findall(text)
    src_paths = _SOURCE_PATH_RE.findall(text)
    sha256s = _SHA256_RE.findall(text)
    cycles = set(_CROSS_CYCLE_RE.findall(text))

    figs_without_anchor = max(0, len(figures) - min(len(src_paths), len(sha256s)))
    undoc_holds = [h for h in holds if h.disposition == HoldDisposition.UNDOCUMENTED]
    cross_cycle_mixed = len(cycles) > 1

    findings: list[StepFinding] = []
    findings.append(
        StepFinding(
            "2.1",
            f"{len(figures)} figure(s); {figs_without_anchor} missing source_path or sha256.",
            TraceabilityClass.TRACEABLE
            if figs_without_anchor == 0
            else TraceabilityClass.PARTIALLY_TRACEABLE,
        )
    )
    findings.append(
        StepFinding(
            "2.2",
            f"{len(undoc_holds)} HOLD event(s) without stated cause in deviation log.",
            TraceabilityClass.TRACEABLE if not undoc_holds else TraceabilityClass.NOT_TRACEABLE,
        )
    )
    findings.append(
        StepFinding(
            "2.3",
            "Audit trace fields present without stated interpretation."
            if figs_without_anchor > 0
            else "No interpretation gap detected.",
            TraceabilityClass.PARTIALLY_TRACEABLE
            if figs_without_anchor > 0
            else TraceabilityClass.TRACEABLE,
        )
    )
    findings.append(
        StepFinding(
            "2.4",
            f"Cross-cycle comparison spans {len(cycles)} cycle(s)."
            + (" Mixed baselines risk." if cross_cycle_mixed else ""),
            TraceabilityClass.PARTIALLY_TRACEABLE
            if cross_cycle_mixed
            else TraceabilityClass.TRACEABLE,
        )
    )

    prose = (
        f"{figs_without_anchor} of {len(figures)} figure(s) lack both source_path and sha256, "
        f"making those figures {TraceabilityClass.PARTIALLY_TRACEABLE.value if figs_without_anchor else TraceabilityClass.TRACEABLE.value}. "
        f"{len(undoc_holds)} deviation log entry(ies) carry no stated cause. "
        + (
            f"Cross-cycle comparison mixes {len(cycles)} cycle anchors, which is invalid regardless of numeric stability."
            if cross_cycle_mixed
            else ""
        )
    )
    return StepResult(step_id="2", weight=0.30, prose=prose.strip(), findings=findings)


# ── STEP 3 — Series Continuity (20%) ──────────────────────────────────────────

_PRIOR_OPEN_RE = re.compile(r"(open question|carry forward|unresolved|TBD|TODO)", re.I)
_HANDOFF_RE = re.compile(r"(next.cycle|next.experiment|handoff|forward)", re.I)
_DRIFT_RE = re.compile(r"(stability.+superior|improvement.+system|metric.+proves)", re.I)
_PRIOR_CYCLE_RE = re.compile(r"EXP-\d{3}", re.I)


def step3_series_continuity(text: str) -> StepResult:
    has_prior = bool(_PRIOR_CYCLE_RE.search(text))
    open_qs = _PRIOR_OPEN_RE.findall(text)
    handoff = _HANDOFF_RE.search(text)
    drift = _DRIFT_RE.search(text)

    if not has_prior:
        prose = (
            "No prior cycle reference exists; cross-cycle continuity is NOT APPLICABLE. "
            "The report must still state its own forward handoff explicitly to avoid silent debt."
        )
        return StepResult(step_id="3", weight=0.20, prose=prose, not_applicable=True)

    findings: list[StepFinding] = []
    findings.append(
        StepFinding(
            "3.1",
            f"{len(open_qs)} open question(s) from prior cycle detected.",
            TraceabilityClass.TRACEABLE if open_qs else TraceabilityClass.PARTIALLY_TRACEABLE,
        )
    )
    findings.append(
        StepFinding(
            "3.2",
            "Valid handoff scope stated." if handoff else "Handoff is a deferral, not a contract.",
            TraceabilityClass.TRACEABLE if handoff else TraceabilityClass.NOT_TRACEABLE,
        )
    )
    drift_quote = drift.group(0) if drift else None
    findings.append(
        StepFinding(
            "3.3",
            "Narrative drift detected." if drift else "Governing frame holds.",
            TraceabilityClass.NOT_TRACEABLE if drift else TraceabilityClass.TRACEABLE,
            verbatim_quote=drift_quote,
        )
    )

    prose = (
        f"Prior cycle reference found; {len(open_qs)} open item(s) identified. "
        + (
            "Handoff scope is explicitly stated."
            if handoff
            else "Handoff is a deferral — it names no opening question, out-of-scope items, or next-cycle constraints. "
        )
        + (
            f"Narrative drift detected at '{drift_quote}', reading stability as systemic superiority."
            if drift
            else "Governing frame is maintained."
        )
    )
    return StepResult(step_id="3", weight=0.20, prose=prose.strip(), findings=findings)


# ── STEP 4 — Publication Readiness (10%) ──────────────────────────────────────

_HASH_FREE_RULE_RE = re.compile(r"(hash.free|without.sha|no.sha)", re.I)
_READER_MISREAD_RE = re.compile(r"(PASS|significant improvement|confirmed|validated)", re.I)


def step4_publication_readiness(text: str) -> StepResult:
    self_contradict = bool(_HASH_FREE_RULE_RE.search(text)) and not bool(_SHA256_RE.search(text))
    misread = _READER_MISREAD_RE.search(text)

    findings: list[StepFinding] = []
    findings.append(
        StepFinding(
            "4.1",
            "Internal rule violation: report prohibits hash-free figures but contains none."
            if self_contradict
            else "Internal rule compliance holds.",
            TraceabilityClass.NOT_TRACEABLE if self_contradict else TraceabilityClass.TRACEABLE,
        )
    )
    findings.append(
        StepFinding(
            "4.2",
            f"Misread risk at '{misread.group(0)}' — external reader may infer causal superiority."
            if misread
            else "No high-risk misread point identified.",
            TraceabilityClass.PARTIALLY_TRACEABLE if misread else TraceabilityClass.TRACEABLE,
            verbatim_quote=misread.group(0) if misread else None,
        )
    )

    prose = (
        "Self-contradiction detected: the report defines a no-hash-free-figures rule but cites figures without sha256. "
        if self_contradict
        else "Internal rule compliance holds. "
    ) + (
        f"The highest misread risk is at '{misread.group(0)}', where an external reader is most likely to infer a causal claim the report does not intend."
        if misread
        else "No single high-risk misread point was identified."
    )
    return StepResult(step_id="4", weight=0.10, prose=prose.strip(), findings=findings)


# ── STEP 5 — Priority Fix ──────────────────────────────────────────────────────


def step5_priority_fix(
    step1: StepResult,
    step2: StepResult,
    step3: StepResult,
    step4: StepResult,
) -> tuple[str, str | None]:
    not_traceable = sum(
        1
        for s in [step1, step2, step3, step4]
        for f in s.findings
        if f.traceability == TraceabilityClass.NOT_TRACEABLE
    )
    # Rank by not_traceable count then weight
    ranked = sorted(
        [(step1, 0.40), (step2, 0.30), (step3, 0.20), (step4, 0.10)],
        key=lambda x: (
            -sum(1 for f in x[0].findings if f.traceability == TraceabilityClass.NOT_TRACEABLE),
            -x[1],
        ),
    )
    worst = ranked[0][0]
    second = ranked[1][0]

    fix = (
        f"The priority fix is resolving the NOT TRACEABLE findings in STEP {worst.step_id}: "
        f"{worst.findings[0].description if worst.findings else 'untraced claims'}. "
        f"This takes priority because it carries the highest not-traceable count and blocks every downstream step from producing a valid verdict."
    )
    next_l = (
        f"Once STEP {worst.step_id} is resolved, STEP {second.step_id} findings are likely to surface as the next open liability."
        if not_traceable > 1
        else None
    )
    return fix, next_l
