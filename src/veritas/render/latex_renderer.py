"""LaTeX renderer — generates a standalone .tex file from CritiqueReport.

Design references:
  - latex-scientific-paper-templates/cls/labreport.cls
      (natbib author-year, color palette, fancyhdr, modular style)
  - latex-scientific-paper-templates/build/build_xelatex.sh
      (XeLaTeX + biber pipeline)
  - Markdown-Templates/latex-pdf/
      (Pandoc-compatible front-matter, print vs e-reader layouts)
  - Markdown-Templates/bibliography/assets/citation-style.csl
      (Harvard Anglia Ruskin author-date)

The generated .tex is self-contained (no external .cls).
Compile with: xelatex report.tex  (requires XeLaTeX + texlive-xetex)
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..types import CritiqueReport

# ---------------------------------------------------------------------------
# LaTeX escape map (safe for XeLaTeX / LuaLaTeX with Unicode)
# ---------------------------------------------------------------------------
_ESC = str.maketrans({
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
})


def _e(s: str) -> str:
    return str(s).translate(_ESC)


# ---------------------------------------------------------------------------
# Preamble  (labreport-inspired: natbib + color palette + fancyhdr)
# ---------------------------------------------------------------------------
_PREAMBLE = r"""
\documentclass[a4paper,11pt]{article}
\usepackage[a4paper,left=2.5cm,right=2.5cm,top=2.0cm,bottom=2.5cm]{geometry}
\usepackage{fontspec}
\usepackage[hidelinks,colorlinks=false]{hyperref}
\usepackage{xcolor}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{tabularx}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage{parskip}
\usepackage{microtype}
\usepackage{natbib}
\usepackage{mdframed}
\bibliographystyle{apalike}
%% --- Color palette (labreport.cls inspired) ---
\definecolor{navyblue}{RGB}{22,33,62}
\definecolor{royalblue}{RGB}{15,76,117}
\definecolor{accentred}{RGB}{231,76,60}
\definecolor{secgray}{RGB}{241,241,241}
\definecolor{traceable}{RGB}{39,174,96}
\definecolor{partial}{RGB}{230,162,0}
\definecolor{nottraceable}{RGB}{231,76,60}
%% --- Section headings (titlesec) ---
\titleformat{\section}
  {\large\bfseries\sffamily\color{navyblue}}{}{0em}{}
  [\color{navyblue}\rule{\textwidth}{0.4pt}]
\titleformat{\subsection}
  {\normalsize\bfseries\sffamily\color{royalblue}}{}{0em}{}
%% --- Header / Footer (fancyhdr — labreport pattern) ---
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\textsf{\textcolor{navyblue}{VERITAS — AI Critique Experimental Report Analysis Framework}}}
\fancyhead[R]{\small\textsf{\textcolor{navyblue}{\rightmark}}}
\fancyfoot[C]{\small\textcolor{gray}{\thepage}}
\renewcommand{\headrulewidth}{0.4pt}
%% --- Traceability macros ---
\newcommand{\traceable}[1]{\textcolor{traceable}{\textbf{#1}}}
\newcommand{\partialTC}[1]{\textcolor{partial}{\textbf{#1}}}
\newcommand{\notTC}[1]{\textcolor{nottraceable}{\textbf{#1}}}
"""


class LatexRenderer:
    """Render a CritiqueReport to a LaTeX (.tex) file.

    Usage::
        LatexRenderer().render(report, "out/report.tex", template="bmj")
    """

    def render(
        self,
        report: CritiqueReport,
        output_path: str,
        template: str = "bmj",
        compile_pdf: bool = False,
    ) -> Path:
        """Write .tex file; optionally compile with xelatex."""
        path    = Path(output_path)
        content = render_latex(report, template)
        path.write_text(content, encoding="utf-8")
        if compile_pdf:
            _compile(path)
        return path


def render_latex(report: CritiqueReport, template_id: str = "bmj") -> str:
    """Return full LaTeX source string for *report*."""
    from ..templates.base import BaseTemplate
    tmpl = BaseTemplate.all_templates().get(template_id)
    if tmpl is None:
        raise ValueError(f"Unknown template: {template_id!r}")

    sections  = tmpl.build(report)
    omega_str = f"{report.omega_score:.4f}"
    if report.hybrid_omega is not None:
        omega_str += f" (hybrid {report.hybrid_omega:.4f})"

    lines: list[str] = [
        r"\documentclass[a4paper,11pt]{article}", _PREAMBLE,
        r"\begin{document}",
        _cover(report, tmpl.DISPLAY_NAME, omega_str),
    ]

    for sec in sections:
        if sec.title.lower() in ("cover page", "title page"):
            continue
        lines.append(rf"\section{{{_e(sec.title)}}}")
        lines.append(_e(sec.body))
        if sec.findings:
            lines += _findings_block(sec.findings)
        lines.append("")

    # Optional intelligence sections
    if report.bibliography_stats:
        lines += _biblio_block(report.bibliography_stats)
    if report.reproducibility_checklist:
        lines += _repro_block(report.reproducibility_checklist)
    if report.irf_scores:
        lines += _irf_block(report.irf_scores)
    if report.hsta_scores:
        lines += _hsta_block(report.hsta_scores)

    lines.append(r"\end{document}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------

def _cover(report: CritiqueReport, display_name: str, omega: str) -> str:
    return "\n".join([
        r"\begin{titlepage}",
        r"  \color{navyblue}\rule{\textwidth}{4pt}\vspace{1em}",
        r"  {\Huge\bfseries\sffamily VERITAS}\\[0.4em]",
        r"  {\large\sffamily Experimental Report Analysis v2.1}\\[2em]",
        r"  \color{black}",
        r"  \begin{tabular}{ll}",
        rf"    \textbf{{Template}} & {_e(display_name)} \\",
        rf"    \textbf{{Round}}    & {_e(str(report.round_number))} \\",
        rf"    \textbf{{Omega}}    & {_e(omega)} \\",
        rf"    \textbf{{Precheck}} & {_e(report.precheck.mode.value)} \\",
        r"  \end{tabular}",
        r"  \vspace{2em}",
        r"  \color{navyblue}\rule{\textwidth}{2pt}",
        r"\end{titlepage}",
        r"\newpage",
    ])


def _findings_block(findings: list[str]) -> list[str]:
    _PAT = re.compile(r'^\[([^\]]+)\]\s+\[([^\]]+)\]\s+(.+)$')
    rows = []
    for raw in findings:
        m = _PAT.match(raw.strip())
        if not m:
            rows.append(rf"\item {_e(raw)}")
            continue
        code, tc, desc = m.group(1), m.group(2).upper(), m.group(3)
        tc_lower = tc.lower()
        if "not" in tc_lower:
            tc_tex = rf"\notTC{{{_e(tc)}}}"
        elif "partial" in tc_lower:
            tc_tex = rf"\partialTC{{{_e(tc)}}}"
        else:
            tc_tex = rf"\traceable{{{_e(tc)}}}"
        rows.append(rf"\item \textbf{{{_e(code)}}} {tc_tex} — {_e(desc)}")

    return [r"\begin{itemize}"] + rows + [r"\end{itemize}"]


def _biblio_block(stats) -> list[str]:
    fmt = ", ".join(stats.formats_detected) or "Unknown"
    self_c = "Yes" if stats.self_citation_detected else "No"
    yr_range = (
        f"{stats.oldest_year}--{stats.newest_year}"
        if stats.oldest_year else "N/A"
    )
    return [
        r"\section{Bibliography Analysis}",
        r"\begin{tabular}{ll}",
        rf"  \textbf{{Total references}} & {stats.total_refs} \\",
        rf"  \textbf{{Recent ratio ($\leq$5 yr)}} & {stats.recent_ratio:.1%} \\",
        rf"  \textbf{{Year range}} & {_e(yr_range)} \\",
        rf"  \textbf{{Citation format}} & {_e(fmt)} \\",
        rf"  \textbf{{Self-citation detected}} & {self_c} \\",
        rf"  \textbf{{Quality score}} & {stats.quality_score:.4f} \\",
        r"\end{tabular}", "",
    ]


def _repro_block(checklist) -> list[str]:
    lines = [
        r"\section{Reproducibility Checklist}",
        rf"\textit{{{_e(checklist.summary)}}}\\[0.5em]",
        r"\begin{tabular}{lll}",
        r"\toprule",
        r"\textbf{Code} & \textbf{Criterion} & \textbf{Status} \\",
        r"\midrule",
    ]
    for item in checklist.items:
        status = (
            r"\traceable{Yes}" if item.satisfied is True else
            r"\notTC{No}"      if item.satisfied is False else
            r"\textcolor{gray}{?}"
        )
        lines.append(
            rf"  {_e(item.code)} & {_e(item.criterion)} & {status} \\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    return lines


def _irf_block(irf) -> list[str]:
    verdict = r"\traceable{PASS}" if irf.passed else r"\partialTC{WARN}"
    return [
        r"\section{IRF-Calc 6D Score (LOGOS)}",
        r"\begin{tabular}{lrl}",
        r"\toprule",
        r"\textbf{DIM} & \textbf{Score} & \textbf{Meaning} \\",
        r"\midrule",
        rf"  M & {irf.M:.3f} & Methodic Doubt \\",
        rf"  A & {irf.A:.3f} & Axiom / Hypothesis \\",
        rf"  D & {irf.D:.3f} & Deduction \\",
        rf"  I & {irf.I:.3f} & Induction \\",
        rf"  F & {irf.F:.3f} & Falsification \\",
        rf"  P & {irf.P:.3f} & Paradigm \\",
        r"\midrule",
        rf"  \textbf{{Composite}} & {irf.composite:.3f} & {verdict} \\",
        r"\bottomrule",
        r"\end{tabular}", "",
    ]


def _hsta_block(hsta) -> list[str]:
    return [
        r"\section{HSTA 4D Score (BioMedical-Paper-Harvester)}",
        r"\begin{tabular}{lrl}",
        r"\toprule",
        r"\textbf{DIM} & \textbf{Score} & \textbf{Meaning} \\",
        r"\midrule",
        rf"  N & {hsta.N:.3f} & Novelty \\",
        rf"  C & {hsta.C:.3f} & Consistency \\",
        rf"  T & {hsta.T:.3f} & Temporality \\",
        rf"  R & {hsta.R:.3f} & Reproducibility \\",
        r"\midrule",
        rf"  \textbf{{Composite}} & {hsta.composite:.3f} & Arithmetic mean \\",
        r"\bottomrule",
        r"\end{tabular}", "",
    ]


# ---------------------------------------------------------------------------
# Optional compilation
# ---------------------------------------------------------------------------

def _compile(tex_path: Path) -> None:
    """Run xelatex twice (for cross-refs). Raises RuntimeError on failure."""
    cmd = ["xelatex", "-interaction=nonstopmode", str(tex_path.name)]
    cwd = str(tex_path.parent)
    for _ in range(2):
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"xelatex failed:\n{result.stdout[-2000:]}\n{result.stderr[-500:]}"
            )
