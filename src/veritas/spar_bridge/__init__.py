"""VERITAS spar_bridge — spar_domain_sciexp adapter.

Wires SPAR framework's claim-aware review kernel to VERITAS CritiqueReport output.
Three-layer review: A (anchor consistency) B (interpretation validity) C (maturity probes).

Usage::

    from veritas.spar_bridge.runtime import get_review_runtime
    from veritas.spar_bridge.subject_mapper import report_to_subject

    runtime = get_review_runtime()
    subject = report_to_subject(critique_report)

    from spar_framework.engine import run_review
    result = run_review(runtime=runtime, subject=subject, gate="ACCEPT")
"""
