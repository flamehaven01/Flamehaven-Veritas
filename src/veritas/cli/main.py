"""sciexp CLI — VERITAS — AI Critique Experimental Report Analysis Framework command-line interface.

Usage:
  sciexp critique <file>                      analyse a document
  sciexp critique --text "..."               analyse inline text
  sciexp critique --round 2 --prev r1.json   multi-round with drift tracking
  sciexp batch "*.pdf" --output-dir results/ batch critique multiple files
  sciexp precheck <file>                      quick precheck only
  sciexp info                                 engine + MICA status
  sciexp playbook                             print MICA playbook for AI agent loading
"""

from __future__ import annotations

import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib.metadata import version as _pkg_version

import click

# ---------------------------------------------------------------------------
# Version helper
# ---------------------------------------------------------------------------
_VERSION = "unknown"
for _pkg_name in ("flamehaven-veritas", "veritas"):
    try:
        _VERSION = _pkg_version(_pkg_name)
        break
    except Exception:
        pass
if _VERSION == "unknown":
    _VERSION = "2.3.0"


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


def _save_round_summary(
    report, source_file: str | None, out_file: str | None, round_num: int, quiet: bool
) -> None:
    """Persist round summary JSON for next-round --prev reload."""
    if out_file:
        stem = pathlib.Path(out_file).stem
        base_dir = pathlib.Path(out_file).parent
    elif source_file:
        stem = pathlib.Path(source_file).stem
        base_dir = pathlib.Path(source_file).parent
    else:
        stem = "report"
        base_dir = pathlib.Path(".")
    json_path = base_dir / f"{stem}_r{round_num}.json"
    json_path.write_text(json.dumps(report.to_round_summary(), indent=2), encoding="utf-8")
    if not quiet:
        click.echo(f"[+] Round summary saved to {json_path}")


def _emit_report(report, fmt: str, out: str | None, template: str) -> None:
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
@click.option(
    "--prev",
    default=None,
    metavar="JSON",
    help="Previous round summary JSON (enables drift tracking).",
)
@click.option(
    "--save-round",
    is_flag=True,
    help="Auto-save round summary JSON to <stem>_r<N>.json alongside output.",
)
@click.option("--out", "-o", default=None, help="Output file path. Defaults to stdout for md.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress messages.")
def critique(file, text, stdin, fmt, template, round_num, prev, save_round, out, quiet):
    """Analyse a document and emit a structured critique report.

    Examples:\n
      sciexp critique paper.pdf\n
      sciexp critique paper.md --format pdf --out report.pdf\n
      sciexp critique paper.md --format tex --out report.tex\n
      sciexp critique --text "Abstract: ..." --template ku\n
      sciexp critique paper.pdf --round 2 --prev paper_r1.json --save-round\n
      cat paper.txt | sciexp critique --stdin
    """
    # --format docx/pdf/tex requires --out
    if fmt in ("pdf", "docx", "tex") and not out:
        raise click.ClickException(f"--out <path> required when --format {fmt}.")

    if not quiet:
        click.echo(f"[>] VERITAS v{_VERSION} | fmt={fmt} tpl={template} round={round_num}")

    raw = _read_input(file, text, stdin)

    # Load previous round for drift tracking
    prev_report = None
    if prev:
        prev_path = pathlib.Path(prev)
        if not prev_path.exists():
            raise click.ClickException(f"Previous round file not found: {prev}")
        try:
            from ..types import CritiqueReport

            data = json.loads(prev_path.read_text(encoding="utf-8"))
            prev_report = CritiqueReport.from_round_summary(data)
            if not quiet:
                click.echo(f"[>] Loaded prev round R{prev_report.round_number} from {prev}")
        except Exception as exc:
            raise click.ClickException(f"Failed to parse previous round JSON: {exc}") from exc

    engine = _load_engine()
    report = engine.critique(raw, round_number=round_num, prev_report=prev_report)
    _emit_report(report, fmt, out, template)

    # Auto-save round summary JSON
    if save_round:
        _save_round_summary(report, file, out, round_num, quiet)


# ---------------------------------------------------------------------------
# batch
# ---------------------------------------------------------------------------
@main.command()
@click.argument("pattern")
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["md", "pdf", "docx", "tex"], case_sensitive=False),
    default="md",
    show_default=True,
    help="Output format for each report.",
)
@click.option(
    "--jobs",
    "-j",
    type=int,
    default=4,
    show_default=True,
    help="Number of parallel workers.",
)
@click.option(
    "--output-dir",
    "-d",
    default=".",
    show_default=True,
    help="Directory for output files and summary index.",
)
@click.option("--quiet", "-q", is_flag=True, help="Suppress per-file progress messages.")
def batch(pattern, fmt, jobs, output_dir, quiet):
    """Batch critique all files matching PATTERN in parallel.

    Emits one report per file in OUTPUT_DIR plus a summary_index.json.

    Examples:\n
      veritas batch "*.pdf" --output-dir results/\n
      veritas batch "papers/*.md" --jobs 8 --format pdf\n
      veritas batch "reports/**/*.txt" -j 2 -d out/
    """
    import glob as _glob

    out_path = pathlib.Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    files = sorted(_glob.glob(pattern, recursive=True))
    if not files:
        raise click.ClickException(f"No files matched pattern: {pattern!r}")

    if not quiet:
        click.echo(f"[>] Batch critique: {len(files)} file(s), {jobs} worker(s), fmt={fmt}")

    engine = _load_engine()

    def _process_one(fp: str) -> dict:
        p = pathlib.Path(fp)
        try:
            report = engine.critique_from_file(fp)
            stem = p.stem
            ext = {"md": ".md", "pdf": ".pdf", "docx": ".docx", "tex": ".tex"}[fmt]
            dest = out_path / f"{stem}{ext}"
            _emit_report(report, fmt, str(dest), "bmj")
            return {
                "file": fp,
                "status": "ok",
                "omega": report.omega_score,
                "hybrid_omega": report.hybrid_omega,
                "round": report.round_number,
                "output": str(dest),
            }
        except Exception as exc:
            return {"file": fp, "status": "error", "error": str(exc)}

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(_process_one, f): f for f in files}
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            if not quiet:
                status = res["status"]
                omega = f"omega={res['omega']:.4f}" if status == "ok" else res.get("error", "")
                icon = "[+]" if status == "ok" else "[-]"
                click.echo(f"  {icon} {res['file']} {omega}")

    # Emit summary index
    results.sort(key=lambda r: r["file"])
    index_path = out_path / "summary_index.json"
    index_path.write_text(
        json.dumps({"files": results, "total": len(results)}, indent=2), encoding="utf-8"
    )
    ok_count = sum(1 for r in results if r["status"] == "ok")
    click.echo(f"[+] Batch complete: {ok_count}/{len(results)} succeeded -> {index_path}")


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
