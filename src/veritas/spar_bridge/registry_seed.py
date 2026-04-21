"""SciExp model maturity registry seed.

Snapshot of known sciexp domain component states.
Travels with every SPAR ReviewResult for auditability.
"""

from __future__ import annotations


def sciexp_registry_snapshots() -> dict:
    return {
        "model_registry_snapshot": {
            "domain": "sciexp",
            "total_models": 6,
            "components": [
                {
                    "id": "veritas_pipeline",
                    "name": "VERITAS 6-Step Critique Pipeline",
                    "state": "genuine",
                    "version": "2.2.0",
                    "description": "Classify → Claim Integrity → Traceability → Series → Publication → Fix",
                },
                {
                    "id": "logos_irf",
                    "name": "LOGOS IRF-Calc 6D",
                    "state": "environment_conditional",
                    "version": "1.x",
                    "description": "6D reasoning scorer (M/A/D/I/F/P). Optional — degrades to None if unavailable.",
                },
                {
                    "id": "hsta_4d",
                    "name": "HSTA 4D Bibliometric Engine",
                    "state": "approximate",
                    "version": "1.0",
                    "description": "Heuristic N/C/T/R scoring from text patterns. Not peer-reviewed.",
                },
                {
                    "id": "bibliography_analyzer",
                    "name": "BibliographyAnalyzer",
                    "state": "approximate",
                    "version": "1.0",
                    "description": "Pattern-based reference extraction. Quality score is heuristic.",
                },
                {
                    "id": "reproducibility_checklist",
                    "name": "ReproducibilityChecklistExtractor",
                    "state": "approximate",
                    "version": "1.0",
                    "description": "ARRIVE/CONSORT keyword-based checklist. Not a formal audit.",
                },
                {
                    "id": "spar_sciexp_adapter",
                    "name": "spar_domain_sciexp Adapter",
                    "state": "genuine",
                    "version": "1.0",
                    "description": "SPAR Layer A/B/C claim-aware review for experimental reports.",
                },
            ],
        },
        "gap_registry_snapshot": {
            "domain": "sciexp",
            "open_gaps": [
                {
                    "gap_id": "G1",
                    "description": "LOGOS IRF server integration not yet available. IRF runs local only.",
                    "state": "gapped",
                },
                {
                    "gap_id": "G2",
                    "description": "HSTA 4D uses keyword heuristics, not learned embeddings. Known approximation.",
                    "state": "approximate",
                },
                {
                    "gap_id": "G3",
                    "description": "No LEDA injection support in sciexp adapter yet (physics adapter has B4/C9).",
                    "state": "gapped",
                },
            ],
        },
    }
