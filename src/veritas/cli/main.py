"""sciexp CLI — VERITAS — AI Critique Experimental Report Analysis Framework command-line interface.

Usage:
  sciexp critique <file>          analyse a document
  sciexp critique --text "..."    analyse inline text
  sciexp precheck <file>          quick precheck only
  sciexp info                     engine + MICA status
  sciexp playbook                 print MICA playbook for AI agent loading
"""

from __future__ import annotations

import pathlib
import sys
from importlib.metadata import version as _pkg_version

import click

# ---------------------------------------------------------------------------
# Version helper
# ---------------------------------------------------------------------------
_VERSION = "unknown"
try:
    _VERSION = _pkg_version("veritas")
except Exception:
    _VERSION = "2.1.0"


def _load_engine():
    """Lazy import — keeps startup fast for simple sub-commands."""
    from ..engine import SciExpCritiqueEngine

    return SciExpCritiqueEngine()


def _load_renderers():
    from ..renderers.md_renderer import MDRenderer

    return {"md": MDRenderer}


def _read_input(file: str | None, text: str | None, stdin: bool) -> str:
    """Resolve input priority: stdin > text > file."""
    if stdin:
        return sys.stdin.read()
    if text:
        return text
    if file:
        p = pathlib.Path(file)
        if not p.exists():
            raise click.ClickException(f"File not found: {file}")
        if p.suffix.lower() == ".pdf":
            try:
                import fitz  # PyMuPDF

                doc = fitz.open(str(p))
                return "\n".join(page.get_text() for page in doc)
            except ImportError as err:
                raise click.ClickException(
                    "PyMuPDF not installed. Install with: pip install PyMuPDF"
                ) from err
        if p.suffix.lower() in (".docx",):
            try:
                import docx

                doc = docx.Document(str(p))
                return "\n".join(p.text for p in doc.paragraphs)
            except ImportError as err:
                raise click.ClickException(
                    "python-docx not installed. Install with: pip install python-docx"
                ) from err
        return p.read_text(encoding="utf-8", errors="replace")
    raise click.ClickException("Provide a file, --text, or --stdin.")


def _emit_report(report, fmt: str, out: str | None, template: str) -> None:
    """Route report to the requested output format."""
    if fmt == "md":
        from .formatters import fmt_md

        md_text = fmt_md(report)
        if out:
            pathlib.Path(out).write_text(md_text, encoding="utf-8")
            click.echo(f"[+] Saved to {out}")
        else:
            click.echo(md_text)
        return

    if fmt == "docx":
        try:
            from ..render.docx_renderer import DocxRenderer
        except ImportError as exc:
            raise click.ClickException(f"DOCX renderer unavailable: {exc}") from exc
        DocxRenderer().render(report, out, template=template)
        click.echo(f"[+] DOCX saved to {out}")
        return

    # fmt == "pdf"
    if fmt == "pdf":
        try:
            from ..render.pdf_renderer import PdfRenderer
        except ImportError as exc:
            raise click.ClickException(f"PDF renderer unavailable: {exc}") from exc
        PdfRenderer().render(report, out, template=template)
        click.echo(f"[+] PDF saved to {out}")
        return

    # fmt == "tex"
    try:
        from ..render.latex_renderer import LatexRenderer
    except ImportError as exc:
        raise click.ClickException(f"LaTeX renderer unavailable: {exc}") from exc
    LatexRenderer().render(report, out or "report.tex", template=template)
    click.echo(f"[+] LaTeX saved to {out}")


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------
@click.group()
@click.version_option(_VERSION, prog_name="veritas")
def main():
    """VERITAS — AI Critique Experimental Report Analysis Framework — Experimental Report Analysis Engine."""


# ---------------------------------------------------------------------------
# critique
# ---------------------------------------------------------------------------
@main.command()
@click.argument("file", required=False, default=None)
@click.option("--text", "-t", default=None, help="Inline text to analyse.")
@click.option("--stdin", is_flag=True, help="Read input from stdin.")
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["md", "pdf", "docx", "tex"], case_sensitive=False),
    default="md",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--template",
    type=click.Choice(["bmj", "ku"], case_sensitive=False),
    default="bmj",
    show_default=True,
    help="Report template.",
)
@click.option(
    "--round", "round_num", type=int, default=1, show_default=True, help="Critique round."
)
@click.option("--out", "-o", default=None, help="Output file path. Defaults to stdout for md.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress messages.")
def critique(file, text, stdin, fmt, template, round_num, out, quiet):
    """Analyse a document and emit a structured critique report.

    Examples:\n
      sciexp critique paper.pdf\n
      sciexp critique paper.md --format pdf --out report.pdf\n
      sciexp critique paper.md --format tex --out report.tex\n
      sciexp critique --text "Abstract: ..." --template ku\n
      cat paper.txt | sciexp critique --stdin
    """
    # --format docx/pdf/tex requires --out
    if fmt in ("pdf", "docx", "tex") and not out:
        raise click.ClickException(f"--out <path> required when --format {fmt}.")

    if not quiet:
        click.echo(f"[>] VERITAS v{_VERSION} | fmt={fmt} tpl={template} round={round_num}")

    raw = _read_input(file, text, stdin)

    engine = _load_engine()
    report = engine.critique(raw, round_number=round_num)
    _emit_report(report, fmt, out, template)


# ---------------------------------------------------------------------------
# precheck
# ---------------------------------------------------------------------------
@main.command()
@click.argument("file", required=False, default=None)
@click.option("--text", "-t", default=None, help="Inline text.")
@click.option("--stdin", is_flag=True)
def precheck(file, text, stdin):
    """Run PRECHECK only — fast artifact validity scan."""
    raw = _read_input(file, text, stdin)
    from ..precheck import run as _precheck_run

    pc = _precheck_run(raw)
    click.echo(pc.render())


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------
@main.command()
def info():
    """Show engine version, LOGOS status, and MICA state."""
    click.echo(f"VERITAS v{_VERSION}")
    # LOGOS bridge
    try:
        from ..logos.logos_bridge import LogosBridge

        bridge = LogosBridge()
        click.echo(f"LOGOS bridge  : {bridge.source}")
    except Exception as exc:
        click.echo(f"LOGOS bridge  : unavailable ({exc})")
    # MICA
    _mica_root = pathlib.Path(__file__).parent.parent.parent.parent / "memory"
    mica_yaml = _mica_root / "mica.yaml"
    if mica_yaml.exists():
        click.echo(f"MICA contract : {mica_yaml}")
    else:
        click.echo("MICA contract : not found")


# ---------------------------------------------------------------------------
# playbook
# ---------------------------------------------------------------------------
@main.command()
def playbook():
    """Print the MICA playbook for loading into AI agent sessions."""
    _mica_root = pathlib.Path(__file__).parent.parent.parent.parent / "memory"
    pb = _mica_root / "playbook.md"
    if not pb.exists():
        raise click.ClickException(f"Playbook not found at {pb}")
    click.echo(pb.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
