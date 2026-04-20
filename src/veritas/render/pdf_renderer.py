"""PDF renderer — A4 professional report format (reportlab).

Public API
----------
render_pdf(report, output_path, template_id="bmj") -> Path
PdfRenderer().render(report, output_path, template="bmj") -> Path
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from ..templates.base import BaseTemplate


class PdfRenderer:
    """Thin class wrapper for CLI compatibility."""
    def render(self, report, output_path, template: str = "bmj") -> Path:
        return render_pdf(report, output_path, template_id=template)


def render_pdf(report, output_path: str | Path, template_id: str = "bmj") -> Path:
    """Render CritiqueReport to a professional A4 .pdf file. Returns path."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors as rl
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, KeepTogether, PageBreak,
        )
    except ImportError as exc:
        raise ImportError("reportlab required: pip install reportlab") from exc

    from .layout import MARGIN, MARGIN_TOP, MARGIN_BOT, HDR_BAR_H, CM
    from .layout import make_rl_colors, build_pdf_styles

    tmpl = BaseTemplate.all_templates().get(template_id)
    if tmpl is None:
        raise ValueError(f"Unknown template: {template_id!r}")

    sections = tmpl.build(report)
    path     = Path(output_path)
    C        = make_rl_colors()
    S        = build_pdf_styles()

    # page callback (header + footer on every page) -------------------------
    def _draw_page(canvas, doc):
        canvas.saveState()
        w, h = A4
        # footer rule
        canvas.setStrokeColor(C["border"]); canvas.setLineWidth(0.5)
        canvas.line(MARGIN, MARGIN_BOT - 0.35 * CM, w - MARGIN, MARGIN_BOT - 0.35 * CM)
        canvas.setFont("Helvetica", 6.5); canvas.setFillColor(C["subtext"])
        canvas.drawString(MARGIN, MARGIN_BOT - 0.65 * CM,
            "VERITAS — AI Critique Experimental Report Analysis Framework  |  Confidential — Research Review Only")
        canvas.drawRightString(w - MARGIN, MARGIN_BOT - 0.65 * CM, f"Page {doc.page}")
        # running header (skip cover = page 1)
        if doc.page > 1:
            y0 = h - MARGIN_TOP - HDR_BAR_H
            canvas.setFillColor(C["primary"])
            canvas.rect(MARGIN, y0, w - 2 * MARGIN, HDR_BAR_H, fill=1, stroke=0)
            canvas.setFont("Helvetica-Bold", 7.5)
            canvas.setFillColor(rl.white)
            canvas.drawString(MARGIN + 6, y0 + 3,
                f"VERITAS — AI Critique Experimental Report Analysis Framework  |  {tmpl.DISPLAY_NAME}")
            canvas.setFont("Helvetica", 7.5)
            canvas.drawRightString(w - MARGIN - 6, y0 + 3,
                f"Round {report.round_number}  |  Omega {report.omega_score:.4f}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN_TOP + HDR_BAR_H + 0.5 * CM,
        bottomMargin=MARGIN_BOT + 0.1 * CM,
        title=f"VERITAS — AI Critique Experimental Report Analysis Framework — Round {report.round_number}",
        author="VERITAS Engine",
    )
    W = doc.width

    # cover -----------------------------------------------------------------
    omega_str = (
        f"{report.omega_score:.4f}"
        + (f"  (hybrid {report.hybrid_omega:.4f})" if report.hybrid_omega is not None else "")
    )
    cover_meta: list[tuple[str, str]] = [
        ("PRECHECK MODE",    report.precheck.mode.value),
        ("CRITIQUE ROUND",   str(report.round_number)),
        ("OMEGA SCORE",      omega_str),
        ("NOT TRACEABLE",    f"{report.not_traceable_count()} finding(s)"),
        ("PARTIALLY TRACE.", f"{report.partially_traceable_count()} finding(s)"),
        ("GENERATED",        date.today().isoformat()),
    ]
    if report.experiment_class:
        cover_meta.insert(2, ("EXPERIMENT CLASS", report.experiment_class.value))

    story: list[Any] = _build_cover(tmpl.DISPLAY_NAME, cover_meta, S, W, C, rl)
    story.append(PageBreak())

    # body sections ---------------------------------------------------------
    _SKIP = {"Cover Page", "Title Page"}
    for sec in sections:
        if sec.title in _SKIP:
            continue
        block: list[Any] = [Spacer(1, 0.2 * CM), _sec_hdr(sec.title, S, W, C)]
        for para in sec.body.split("\n\n"):
            t = para.strip()
            if t:
                block.append(Paragraph(_md_inline(t), S["body"]))
        if sec.findings:
            block.append(Spacer(1, 0.1 * CM))
            block.append(_findings_table(sec.findings, S, W, C, rl))
        story.append(KeepTogether(block))
        story.append(Spacer(1, 0.25 * CM))

    # score appendix --------------------------------------------------------
    if report.irf_scores:
        sc = report.irf_scores
        dims = [
            ("M",         f"{sc.M:.3f}",         "Methodic Doubt — uncertainty acknowledgment"),
            ("A",         f"{sc.A:.3f}",         "Axiom — foundational grounding"),
            ("D",         f"{sc.D:.3f}",         "Deduction — logical rigor"),
            ("I",         f"{sc.I:.3f}",         "Induction — empirical support"),
            ("F",         f"{sc.F:.3f}",         "Falsification — testability / reproducibility"),
            ("P",         f"{sc.P:.3f}",         "Paradigm — peer-review alignment"),
            ("COMPOSITE", f"{sc.composite:.3f}", "PASS" if sc.passed else "WARN"),
        ]
        story += _dim_table("IRF-Calc 6D Score (LOGOS)", dims, S, W, C, rl)

    if report.hsta_scores:
        h = report.hsta_scores
        dims = [
            ("N",         f"{h.N:.3f}",         "Novelty — semantic uniqueness of findings"),
            ("C",         f"{h.C:.3f}",         "Consistency — cross-reference agreement"),
            ("T",         f"{h.T:.3f}",         "Temporality — citation/date recency"),
            ("R",         f"{h.R:.3f}",         "Reproducibility — method detail completeness"),
            ("COMPOSITE", f"{h.composite:.3f}", "Arithmetic mean (N + C + T + R) / 4"),
        ]
        story += _dim_table("HSTA 4D Score (BioMedical-Paper-Harvester)", dims, S, W, C, rl)

    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return path


# ---------------------------------------------------------------------------
# Flowable builders
# ---------------------------------------------------------------------------

def _build_cover(display_name: str, meta_rows, S, W, C, rl) -> list:
    from reportlab.platypus import Table, TableStyle, Spacer, Paragraph

    title_t = Table(
        [[Paragraph("VERITAS — AI Critique Experimental Report Analysis Framework", S["doc_title"])],
         [Paragraph(display_name,             S["doc_sub"])]],
        colWidths=[W],
    )
    title_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C["primary"]),
        ("TOPPADDING",    (0, 0), (-1,  0), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
    ]))

    kw, vw = W * 0.36, W * 0.64
    meta_data = [
        [Paragraph(k, S["cover_key"]), Paragraph(v, S["cover_val"])]
        for k, v in meta_rows
    ]
    meta_t = Table(meta_data, colWidths=[kw, vw])
    meta_t.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (0, -1), C["secondary"]),
        ("ROWBACKGROUNDS", (1, 0), (1, -1), [C["light"], rl.white]),
        ("GRID",           (0, 0), (-1, -1), 0.5, C["border"]),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 8),
    ]))

    return [title_t, Spacer(1, 0.3 * 28.35), meta_t]


def _sec_hdr(title: str, S, W, C):
    from reportlab.platypus import Table, TableStyle, Paragraph

    t = Table([[Paragraph(_esc(title), S["sec_hdr"])]], colWidths=[W])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C["secondary"]),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
    ]))
    return t


def _findings_table(findings: list[str], S, W, C, rl):
    from reportlab.platypus import Table, TableStyle, Paragraph

    _badge = {
        "TRACEABLE":           "[+] TRACEABLE",
        "PARTIALLY TRACEABLE": "[~] PARTIAL",
        "NOT TRACEABLE":       "[-] NOT TRACE.",
    }
    _tc_col = {
        "TRACEABLE":           C["traceable"],
        "PARTIALLY TRACEABLE": C["partial"],
        "NOT TRACEABLE":       C["not_trace"],
    }
    pat = re.compile(r'^\[([^\]]+)\]\s+\[([^\]]+)\]\s+(.+)$')
    col_w = [W * 0.14, W * 0.18, W * 0.68]

    rows, tc_colors = [], []
    for raw in findings:
        m = pat.match(raw.strip())
        code, tc, desc = (m.group(1), m.group(2), m.group(3)) if m else ("", "", raw)
        rows.append([
            Paragraph(_esc(code), S["tbl_cell"]),
            Paragraph(_badge.get(tc.upper(), tc), S["tbl_cell"]),
            Paragraph(_esc(desc), S["finding"]),
        ])
        tc_colors.append(_tc_col.get(tc.upper(), C["text"]))

    hdr = [[Paragraph(h, S["tbl_hdr"]) for h in ("CODE", "TRACEABILITY", "DESCRIPTION")]]
    t = Table(hdr + rows, colWidths=col_w, repeatRows=1)

    cmds = [("BACKGROUND", (0, 0), (-1, 0), C["primary"])]
    for i, rc in enumerate(tc_colors, start=1):
        cmds.append(("BACKGROUND", (0, i), (-1, i), C["light"] if i % 2 == 0 else rl.white))
        cmds.append(("TEXTCOLOR",  (1, i), (1, i), rc))
        cmds.append(("FONTNAME",   (1, i), (1, i), "Helvetica-Bold"))
    t.setStyle(TableStyle(cmds + [
        ("GRID",          (0, 0), (-1, -1), 0.4, C["border"]),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _dim_table(title: str, dims: list[tuple[str, str, str]], S, W, C, rl) -> list:
    """Score dimension table (used for IRF-6D and HSTA-4D)."""
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

    col_w = [W * 0.12, W * 0.14, W * 0.74]
    data = []
    for d, v, m in dims:
        is_composite = d == "COMPOSITE"
        ps = S["tbl_hdr"] if is_composite else S["tbl_cell"]
        data.append([Paragraph(_esc(d), ps), Paragraph(v, ps), Paragraph(_esc(m), ps)])

    hdr = [[Paragraph(h, S["tbl_hdr"]) for h in ("DIM", "SCORE", "MEANING")]]
    t = Table(hdr + data, colWidths=col_w, repeatRows=1)

    bgs = [("BACKGROUND", (0, 0), (-1, 0), C["primary"])]
    for i in range(1, len(data) + 1):
        bgs.append(("BACKGROUND", (0, i), (-1, i), C["light"] if i % 2 == 0 else rl.white))
    bgs.append(("BACKGROUND", (0, len(data)), (-1, len(data)), C["secondary"]))

    t.setStyle(TableStyle(bgs + [
        ("GRID",          (0, 0), (-1, -1), 0.4, C["border"]),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))

    return [Spacer(1, 0.25 * 28.35), _sec_hdr(title, S, W, C), t, Spacer(1, 0.2 * 28.35)]


# ---------------------------------------------------------------------------
# Inline text helpers
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _md_inline(text: str) -> str:
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', _esc(text))
