"""Statistical validity scorer for VERITAS v3.3.

Analyses academic text for the presence and quality of statistical reporting:
  - p-values (word vs numeric format)
  - Effect size reporting
  - Confidence interval reporting
  - Statistical power / sample size justification
  - Sample size statement

Score weights (sum to 1.0):
  p_numeric   : 0.30
  effect_size : 0.25
  ci          : 0.20
  power       : 0.15
  sample_size : 0.10

If a ``SectionMap`` is provided, analysis focuses on METHODS + RESULTS
sections to reduce false positives from abstract over-claims.
"""

from __future__ import annotations

import re

from ..types import SectionMap, StatValidity

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Numeric p-value:  "p = 0.032", "p<0.05", "p=.001", "(p < .001)"
_P_NUMERIC = re.compile(
    r"\bp\s*[=<>]\s*\.?\d+(?:\.\d+)?(?:\s*[eE][+-]?\d+)?",
    re.I,
)

# Word-only significance: "significant", "non-significant", "marginal"
_P_WORD = re.compile(
    r"\b(?:significant(?:ly)?|non[- ]significant|marginal(?:ly)?|"
    r"p[- ]value\s+was\b|statistically\s+significant)\b",
    re.I,
)

# Effect size: Cohen's d, η², r, OR, RR, SMD, Hedges' g, partial eta, f²
_EFFECT_SIZE = re.compile(
    r"\b(?:effect\s+size|cohen['']?s?\s+[dD]|eta(?:\s+squared)?|"
    r"partial\s+eta|cohen['']?s?\s+[fF]\s*[²2]?|hedges['']?\s*[gG]|"
    r"odds\s+ratio|relative\s+risk|risk\s+ratio|"
    r"standardi[sz]ed\s+mean\s+diff|SMD|"
    r"r\s*=\s*[-+]?0\.\d+|R\s*²\s*=|"
    r"β\s*=|beta\s*=\s*[-+]?0\.\d+)\b",
    re.I,
)

# Confidence interval: "95% CI", "(CI: 1.2–3.4)", "[1.2, 3.4]" near "CI"
_CI = re.compile(
    r"\b(?:\d{2}%\s*CI|confidence\s+interval|CI\s*[:,]?\s*\[?\s*[-+]?\d)",
    re.I,
)

# Statistical power / power analysis
_POWER = re.compile(
    r"\b(?:statistical\s+power|power\s*=\s*0\.\d+|"
    r"power\s+analysis|power\s+calculation|"
    r"1\s*[-–]\s*β|beta\s+error|type\s+II\s+error|"
    r"adequately\s+powered)\b",
    re.I,
)

# Sample size statement
_SAMPLE_SIZE = re.compile(
    r"\b(?:n\s*=\s*\d+|N\s*=\s*\d+|"
    r"sample\s+size\s+of\s+\d+|"
    r"(?:enrolled|included|recruited|analysed|analyzed)\s+\d+\s+"
    r"(?:participants?|subjects?|patients?|samples?|observations?)|"
    r"\d+\s+(?:participants?|subjects?|patients?|samples?)\b)",
    re.I,
)

# Weights
_W_P_NUMERIC = 0.30
_W_EFFECT = 0.25
_W_CI = 0.20
_W_POWER = 0.15
_W_SAMPLE = 0.10


class StatValidator:
    """Score statistical reporting completeness in academic text.

    Usage::

        sv = StatValidator()
        validity = sv.validate(text, section_map=section_map)
        print(validity.score)
    """

    def validate(
        self,
        text: str,
        section_map: SectionMap | None = None,
    ) -> StatValidity:
        """Return a ``StatValidity`` for *text* (or focused sections if available)."""
        scan_text = self._select_text(text, section_map)
        return self._analyse(scan_text)

    # ------------------------------------------------------------------

    def _select_text(
        self, text: str, section_map: SectionMap | None
    ) -> str:
        """Focus on METHODS + RESULTS when section map is available."""
        if section_map is not None and section_map.coverage > 0.0:
            focused = section_map.combined("METHODS", "RESULTS")
            if len(focused) > 100:
                return focused
        return text

    def _analyse(self, text: str) -> StatValidity:
        p_numeric = bool(_P_NUMERIC.search(text))
        p_word = bool(_P_WORD.search(text))
        p_reported = p_numeric or p_word

        effect = bool(_EFFECT_SIZE.search(text))
        ci = bool(_CI.search(text))
        power = bool(_POWER.search(text))
        sample = bool(_SAMPLE_SIZE.search(text))

        score = (
            _W_P_NUMERIC * (1.0 if p_numeric else 0.0)
            + _W_EFFECT * (1.0 if effect else 0.0)
            + _W_CI * (1.0 if ci else 0.0)
            + _W_POWER * (1.0 if power else 0.0)
            + _W_SAMPLE * (1.0 if sample else 0.0)
        )

        issues: list[str] = []
        if not p_reported:
            issues.append("No significance testing reported")
        elif not p_numeric:
            issues.append(
                "Significance stated in words only — use numeric p-values (e.g. p=0.032)"
            )
        if not effect:
            issues.append("Effect size not reported")
        if not ci:
            issues.append("Confidence interval not reported")
        if not power:
            issues.append("Statistical power or power analysis not reported")
        if not sample:
            issues.append("Sample size not explicitly stated (n=...)")

        return StatValidity(
            p_value_reported=p_reported,
            p_value_numeric=p_numeric,
            effect_size_reported=effect,
            ci_reported=ci,
            power_reported=power,
            sample_size_stated=sample,
            score=round(score, 4),
            issues=issues,
        )
