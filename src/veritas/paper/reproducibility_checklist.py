"""Reproducibility checklist — ARRIVE/CONSORT-inspired automated criterion detection.

Criteria drawn from:
  ARRIVE 2.0    — Animal Research: Reporting of In Vivo Experiments
  CONSORT 2010  — Consolidated Standards of Reporting Trials
  STROBE        — Strengthening the Reporting of Observational Studies in Epidemiology
  TOP Guidelines — Transparency and Openness Promotion

Each criterion is detected by keyword regex signals in the document text.
Confidence is binary (satisfied / not satisfied) — no partial scores.
"""

from __future__ import annotations

import re

from ..types import ReproducibilityChecklist, ReproducibilityItem

# ---------------------------------------------------------------------------
# Criterion registry: code -> (regex_pattern, human_label)
# ---------------------------------------------------------------------------
_CRITERIA: dict[str, tuple[str, str]] = {
    "DATA": (
        r"(?:data\s+(?:are\s+)?(?:available|accessible|shared|deposited)|"
        r"data\s+availability|open\s+data|figshare|zenodo|dryad|osf\.io|"
        r"supporting\s+(?:information|data)|supplement)",
        "Raw data publicly available",
    ),
    "CODE": (
        r"(?:code\s+(?:is\s+)?(?:available|accessible|shared|deposited)|"
        r"github\.com|gitlab\.com|bitbucket|"
        r"source\s+code|analysis\s+code|scripts?\s+(?:are\s+)?available)",
        "Analysis code publicly available",
    ),
    "PREREG": (
        r"(?:pre-?registered?|clinicaltrials?\.gov|isrctn|prospero|"
        r"osf\.io/[a-z0-9]+|trial\s+registration\s+(?:number|id)|"
        r"registered\s+(?:on|at|with))",
        "Study preregistered (OSF / ClinicalTrials / PROSPERO)",
    ),
    "POWER": (
        r"(?:sample\s+size\s+(?:calculation|determination|justification)|"
        r"power\s+(?:analysis|calculation)|statistical\s+power|"
        r"1\s*[-\u2212]\s*beta|effect\s+size|cohen[\u2019's]?\s*d\s*=)",
        "Sample size / power calculation reported",
    ),
    "STATS": (
        r"(?:statistical(?:ly)?\s+(?:significant|methods?|analysis|test(?:ing)?)|"
        r"p[\s\-]?value|confidence\s+interval|odds\s+ratio|hazard\s+ratio|"
        r"[Pp]\s*[<>=\u2264\u2265]\s*0\.\d+|ANOVA|[Tt]-test|"
        r"regression\s+(?:model|analysis)|chi[\s\-]?square)",
        "Statistical methods fully described",
    ),
    "BLIND": (
        r"(?:(?:double|single|triple)[\s\-]blind(?:ed)?|blind(?:ed|ing)|"
        r"mask(?:ed|ing)|observer[\s\-]blind|"
        r"allocation\s+concealment|assessor\s+blind)",
        "Blinding / masking procedure described",
    ),
    "EXCL": (
        r"(?:inclusion\s+criteria|exclusion\s+criteria|"
        r"eligibility\s+criteria|"
        r"(?:were|was|patients?)\s+(?:included|excluded|eligible))",
        "Inclusion / exclusion criteria stated",
    ),
    "CONF": (
        r"(?:conflict(?:s)?\s+of\s+interest|competing\s+interest|"
        r"no\s+(?:conflict|competing)|author\s+disclosures?|"
        r"potential\s+conflict|financial\s+disclosure)",
        "Conflicts of interest declared",
    ),
}


class ReproducibilityChecklistExtractor:
    """Auto-detect ARRIVE/CONSORT reproducibility criteria in document text.

    Usage::
        extractor = ReproducibilityChecklistExtractor()
        checklist = extractor.extract(text)
        print(checklist.score, checklist.summary)
    """

    def extract(self, text: str) -> ReproducibilityChecklist:
        """Return a checklist with each criterion auto-scored from *text*."""
        items: list[ReproducibilityItem] = []
        for code, (pattern, criterion) in _CRITERIA.items():
            rx = re.compile(pattern, re.IGNORECASE)
            match = rx.search(text)
            items.append(
                ReproducibilityItem(
                    code=code,
                    criterion=criterion,
                    satisfied=bool(match),
                    note=match.group(0)[:80] if match else "",
                )
            )
        return ReproducibilityChecklist(items=items)
