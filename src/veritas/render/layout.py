"""A4 report layout constants and style factory.

Shared by pdf_renderer and docx_renderer.
All reportlab/docx imports are deferred — this module is importable
even when neither optional dependency is installed.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Page geometry  (reportlab points; 1 cm = 28.35 pt)
# ---------------------------------------------------------------------------
CM           = 28.35
MARGIN       = 2.5 * CM      # left / right body margin  (70.88 pt)
MARGIN_TOP   = 2.0 * CM      # top body margin            (56.70 pt)
MARGIN_BOT   = 2.5 * CM      # bottom body margin         (70.88 pt)
HDR_BAR_H    = 1.0 * CM      # running-header bar height  (28.35 pt)

# ---------------------------------------------------------------------------
# Color palette — hex strings, keyed by semantic role
# ---------------------------------------------------------------------------
HEX: dict[str, str] = {
    "primary":   "#16213e",   # deep navy  — title bg, section bars
    "secondary": "#0f3460",   # mid navy   — sub-bars, table headers
    "accent":    "#e94560",   # red-pink   — BLOCKED / critical alerts
    "light":     "#f0f4f8",   # pale grey  — alternating row fills
    "border":    "#dee2e6",   # silver     — grid lines / rules
    "text":      "#212529",   # near-black — body text
    "subtext":   "#6c757d",   # medium grey — meta / footer copy
    "traceable": "#2d6a4f",   # forest green
    "partial":   "#9c6644",   # amber-brown
    "not_trace": "#c1121f",   # crimson
}

# ---------------------------------------------------------------------------
# DOCX column widths (EMU; 1 cm = 360000 EMU)
# ---------------------------------------------------------------------------
DOCX_COL_KEY = int(4.5  * 360_000)   # key column  4.5 cm
DOCX_COL_VAL = int(12.0 * 360_000)   # value column 12 cm


def make_rl_colors() -> dict:
    """Convert HEX palette to reportlab HexColor objects (lazy import)."""
    from reportlab.lib import colors
    return {k: colors.HexColor(v) for k, v in HEX.items()}


def build_pdf_styles() -> dict:
    """Return named ParagraphStyle dict for A4 PDF report."""
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib import colors

    base = getSampleStyleSheet()
    C    = {k: colors.HexColor(v) for k, v in HEX.items()}

    def _s(name: str, parent: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base[parent], **kw)

    return {
        "doc_title":  _s("DocTitle", "Title",
            fontSize=21, leading=25, spaceAfter=2,
            textColor=colors.white, alignment=TA_LEFT,
            fontName="Helvetica-Bold"),
        "doc_sub":    _s("DocSub", "Normal",
            fontSize=9,  spaceAfter=0,
            textColor=colors.HexColor("#a8b2d8")),
        "sec_hdr":    _s("SecHdr", "Normal",
            fontSize=10, leading=13,
            textColor=colors.white, fontName="Helvetica-Bold"),
        "body":       _s("Body", "Normal",
            fontSize=9,  leading=13, spaceAfter=4, textColor=C["text"]),
        "cover_key":  _s("CvrKey", "Normal",
            fontSize=8.5, leading=11,
            textColor=colors.white, fontName="Helvetica-Bold"),
        "cover_val":  _s("CvrVal", "Normal",
            fontSize=8.5, leading=11, textColor=C["text"]),
        "tbl_hdr":    _s("TblHdr", "Normal",
            fontSize=8, leading=10,
            textColor=colors.white, fontName="Helvetica-Bold"),
        "tbl_cell":   _s("TblCell", "Normal",
            fontSize=8, leading=10, textColor=C["text"]),
        "finding":    _s("Finding", "Normal",
            fontSize=8, leading=11, textColor=C["text"]),
        "meta":       _s("Meta", "Normal",
            fontSize=7, textColor=C["subtext"]),
    }
