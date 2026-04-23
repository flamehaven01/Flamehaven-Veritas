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
    _VERSION = "3.2.0"


def _load_engine(domain: str = "biomedical"):
    """Lazy import — keeps startup fast for simple sub-commands."""
    from ..engine import SciExpCritiqueEngine
    from ..logos.domain.registry import list_domain_keys

    valid = list_domain_keys()
    if domain not in valid:
        import click

        raise click.ClickException(
            f"Unknown domain '{domain}'. Valid: {', '.join(valid)}"
        )
    return SciExpCritiqueEngine(domain=domain)


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
    type=click.Choice(["auto", "bmj", "ku"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Report template. 'auto' selects based on experiment class.",
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
@click.option("--rag", is_flag=True, help="Enable RAG context enrichment (BM25+cosine+RRF).")
@click.option(
    "--journal",
    default=None,
    metavar="KEY",
    help="Journal profile for calibrated scoring: nature, ieee, lancet, q1, q2, q3, default.",
)
@click.option(
    "--domain",
    default="biomedical",
    metavar="DOMAIN",
    show_default=True,
    help="IRF scoring domain: biomedical (default), cs, math, or any registered plugin domain.",
)
def critique(file, text, stdin, fmt, template, round_num, prev, save_round, out, quiet, rag, journal, domain):
    """Analyse a document and emit a structured critique report.

    Examples:\n
      sciexp critique paper.pdf\n
      sciexp critique paper.md --format pdf --out report.pdf\n
      sciexp critique paper.md --format tex --out report.tex\n
      sciexp critique --text "Abstract: ..." --template ku\n
      sciexp critique paper.pdf --round 2 --prev paper_r1.json --save-round\n
      sciexp critique paper.pdf --rag\n
      sciexp critique paper.pdf --journal nature\n
      cat paper.txt | sciexp critique --stdin
    """
    # --format docx/pdf/tex requires --out
    if fmt in ("pdf", "docx", "tex") and not out:
        raise click.ClickException(f"--out <path> required when --format {fmt}.")

    if not quiet:
        click.echo(f"[>] VERITAS v{_VERSION} | fmt={fmt} tpl={template} round={round_num}")

    raw = _read_input(file, text, stdin)

    # RAG context enrichment
    rag_context: str | None = None
    if rag:
        try:
            from ..rag.retriever import SciExpRetriever

            retriever = SciExpRetriever()
            retriever.index(raw)
            rag_context = retriever.build_context("hypothesis methodology results")
            if not quiet:
                click.echo(f"[>] RAG indexed {len(raw.split())} words")
        except Exception as exc:
            if not quiet:
                click.echo(f"[!] RAG unavailable: {exc}")

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

    engine = _load_engine(domain=domain)
    # Inject RAG context into raw text when available
    critique_input = f"{raw}\n\n[RAG CONTEXT]\n{rag_context}" if rag_context else raw
    report = engine.critique(critique_input, round_number=round_num, prev_report=prev_report)

    # Resolve auto template after classification is known
    if template == "auto":
        from ..templates.base import select_template

        template = select_template(report)

    _emit_report(report, fmt, out, template)

    # Journal calibration (optional)
    if journal:
        try:
            from ..journal.journal_scorer import JournalScorer

            scorer = JournalScorer()
            jresult = scorer.score(report, journal=journal)
            click.echo(
                f"\n[=] Journal [{jresult.journal_name}]"
                f"  calibrated_omega={jresult.calibrated_omega:.4f}"
                f"  verdict={jresult.verdict.value}"
                f"  (raw={jresult.raw_omega:.4f}, delta={jresult.omega_delta:+.4f})"
            )
        except KeyError as exc:
            raise click.ClickException(str(exc)) from exc

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
            from ..templates.base import select_template

            tpl = select_template(report)
            stem = p.stem
            ext = {"md": ".md", "pdf": ".pdf", "docx": ".docx", "tex": ".tex"}[fmt]
            dest = out_path / f"{stem}{ext}"
            _emit_report(report, fmt, str(dest), tpl)
            return {
                "file": fp,
                "status": "ok",
                "omega": report.omega_score,
                "hybrid_omega": report.hybrid_omega,
                "round": report.round_number,
                "template": tpl,
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
    """Show engine version, LOGOS status, MICA state, and CR-EP governance state."""
    click.echo(f"VERITAS v{_VERSION}")
    # LOGOS bridge
    try:
        from ..logos.logos_bridge import LogosBridge

        bridge = LogosBridge()
        click.echo(f"LOGOS bridge  : {bridge.source}")
    except Exception as exc:
        click.echo(f"LOGOS bridge  : unavailable ({exc})")
    # MICA session
    try:
        from ..session.mica_store import MICAStore

        store = MICAStore(pathlib.Path("."))
        status = store.show()
        click.echo(status.render())
    except Exception as exc:
        click.echo(f"MICA          : error ({exc})")
    # CR-EP governance
    try:
        from ..governance.cr_ep_gate import detect_state as _crep_state
        from ..governance.cr_ep_gate import validate_artifacts

        crep_state = _crep_state(pathlib.Path("."))
        click.echo(f"CR-EP state   : {crep_state}")
        errs = validate_artifacts(pathlib.Path("."))
        if errs:
            for e in errs:
                click.echo(f"  [!] {e}")
    except Exception as exc:
        click.echo(f"CR-EP         : unavailable ({exc})")


# ---------------------------------------------------------------------------
# session
# ---------------------------------------------------------------------------
@main.group()
def session():
    """MICA session management (start / show / close)."""


@session.command("start")
def session_start():
    """Initialize MICA session in current directory."""
    from ..session.mica_store import MICAStore

    store = MICAStore(pathlib.Path("."))
    state = store.start()
    click.echo(f"[+] MICA session started: {state}")


@session.command("show")
def session_show():
    """Show current MICA session status and DI violation counts."""
    from ..session.mica_store import MICAStore

    store = MICAStore(pathlib.Path("."))
    status = store.show()
    click.echo(status.render())
    if status.di_list:
        click.echo(f"\nDI violations ({len(status.di_list)} total):")
        for di in status.di_list[:10]:
            click.echo(f"  [{di.get('severity', '?')}] {di.get('origin_episode', '?')}")
        if len(status.di_list) > 10:
            click.echo(f"  ... and {len(status.di_list) - 10} more")


@session.command("close")
def session_close():
    """Close the current MICA session (writes close timestamp)."""
    from ..session.mica_store import MICAStore

    store = MICAStore(pathlib.Path("."))
    store.close()
    click.echo("[+] MICA session closed.")


# ---------------------------------------------------------------------------
# govern
# ---------------------------------------------------------------------------
@main.group()
def govern():
    """CR-EP governance gate (init / status / log)."""


@govern.command("init")
@click.option(
    "--profile",
    type=click.Choice(["nano", "lite", "standard", "full"], case_sensitive=False),
    default="standard",
    show_default=True,
    help="CR-EP profile determines which artifacts are created.",
)
def govern_init(profile: str):
    """Bootstrap .cr-ep/ governance directory in current directory."""
    from ..governance.cr_ep_gate import bootstrap

    state = bootstrap(pathlib.Path("."), profile=profile)
    click.echo(f"[+] CR-EP initialized (profile={profile}, state={state})")


@govern.command("status")
def govern_status():
    """Show current CR-EP state and artifact validation results."""
    from ..governance.cr_ep_gate import detect_state as _crep_state
    from ..governance.cr_ep_gate import validate_artifacts

    root = pathlib.Path(".")
    state = _crep_state(root)
    click.echo(f"CR-EP state: {state}")
    errs = validate_artifacts(root)
    if errs:
        click.echo("Validation errors:")
        for e in errs:
            click.echo(f"  [!] {e}")
    else:
        click.echo("[+] Artifacts valid.")


@govern.command("log")
@click.option("--last", "-n", type=int, default=10, show_default=True, help="Last N events.")
def govern_log(last: int):
    """Show recent enforcement log events."""
    from ..governance.cr_ep_gate import read_log

    events = read_log(pathlib.Path("."))
    if not events:
        click.echo("No enforcement log events.")
        return
    for ev in events[-last:]:
        click.echo(f"  {ev.get('ts_utc', '')} [{ev.get('event_type', '')}] {ev.get('reason', '')}")


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


# ---------------------------------------------------------------------------
# review-sim
# ---------------------------------------------------------------------------
@main.command("review-sim")
@click.argument("file", required=False, default=None)
@click.option("--text", "-t", default=None, help="Inline text (skips FILE).")
@click.option("--stdin", is_flag=True, help="Read from STDIN.")
@click.option(
    "--reviewers",
    "-n",
    type=click.IntRange(2, 3),
    default=3,
    show_default=True,
    help="Number of reviewer personas: 2=STRICT+BALANCED, 3=STRICT+BALANCED+LENIENT.",
)
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option("--out", "-o", default=None, help="Save output to this path.")
def review_sim(file, text, stdin, reviewers, fmt, out):
    """Simulate multi-persona peer review (STRICT / BALANCED / LENIENT).

    Runs up to 3 reviewer personas with calibrated omega thresholds,
    computes consensus, and triggers DR3 tiebreaker when consensus < 0.60.

    Examples:\n
      veritas review-sim paper.pdf\n
      veritas review-sim --text "Methods: ..." --reviewers 2\n
      veritas review-sim paper.pdf --format json --out review_result.json
    """
    from ..reviewer.engine import ReviewSimEngine

    raw = _read_input(file, text, stdin)
    engine = ReviewSimEngine()
    result = engine.run(raw, reviewers=reviewers)

    if fmt == "json":
        output = json.dumps(result.as_dict(), indent=2, ensure_ascii=False)
    else:
        output = result.render_text()

    if out:
        pathlib.Path(out).write_text(output, encoding="utf-8")
        click.echo(f"[+] Review simulation saved to {out}")
    else:
        click.echo(output)



# ---------------------------------------------------------------------------
# rebuttal
# ---------------------------------------------------------------------------
@main.command()
@click.argument("file", required=False, default=None)
@click.option("--text", "-t", default=None, help="Inline text (skips FILE).")
@click.option("--stdin", is_flag=True, help="Read from STDIN.")
@click.option(
    "--style",
    type=click.Choice(["ieee", "acm", "nature"], case_sensitive=False),
    default="ieee",
    show_default=True,
    help="Response letter citation style.",
)
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option("--out", "-o", default=None, help="Save output to this path.")
@click.option(
    "--render-letter",
    "render_letter",
    is_flag=True,
    default=False,
    help="Render a formal IEEE/ACM/Nature response letter (Markdown).",
)
@click.option(
    "--domain",
    default="biomedical",
    metavar="DOMAIN",
    show_default=True,
    help="IRF scoring domain for critique: biomedical (default), cs, math.",
)
def rebuttal(file, text, stdin, style, fmt, out, render_letter, domain):
    """Generate a structured point-by-point rebuttal from a critique report.

    Runs the full critique pipeline, then maps every reviewer finding to a
    RebuttalItem with category, severity, and author-response template.

    Examples:\n
      veritas rebuttal paper.pdf\n
      veritas rebuttal paper.md --style nature\n
      veritas rebuttal --text "Abstract: ..." --format json --out rebuttal.json\n
      veritas rebuttal paper.pdf --render-letter --out response.md
    """
    from ..rebuttal.rebuttal_engine import RebuttalEngine

    raw = _read_input(file, text, stdin)
    engine = _load_engine(domain=domain)
    critique_report = engine.critique(raw)

    rb_engine = RebuttalEngine()
    rb_report = rb_engine.generate(critique_report, style=style)

    if render_letter:
        from ..render.response_letter import ResponseLetterRenderer
        renderer = ResponseLetterRenderer()
        output = renderer.render(rb_report, style=style)
        if out:
            pathlib.Path(out).write_text(output, encoding="utf-8")
            click.echo(f"[+] Response letter saved to {out}")
        else:
            click.echo(output)
        return

    if fmt == "json":
        output = json.dumps(rb_report.as_dict(), indent=2, ensure_ascii=False)
    else:
        lines = [
            f"VERITAS Rebuttal Report [{style.upper()}]",
            f"Generated: {rb_report.generated_at}",
            f"Total issues: {len(rb_report.items)} | "
            f"CRITICAL: {rb_report.critical_count} | HIGH: {rb_report.high_count}",
            f"Rebuttal coverage: {rb_report.rebuttal_coverage:.0%}",
            "",
        ]
        for item in rb_report.items:
            icon = "[!]" if item.severity in ("CRITICAL", "HIGH") else "[~]"
            lines.append(f"{icon} [{item.issue_id}] {item.category} ({item.severity})")
            lines.append(f"   Reviewer: {item.reviewer_text[:120]}")
            lines.append(f"   Template: {item.author_response_template[:120]}")
            lines.append("")
        output = "\n".join(lines)

    if out:
        pathlib.Path(out).write_text(output, encoding="utf-8")
        click.echo(f"[+] Rebuttal report saved to {out}")
    else:
        click.echo(output)


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------
@main.command()
@click.argument("file_v1")
@click.argument("file_v2")
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option("--out", "-o", default=None, help="Save output to this path.")
def diff(file_v1, file_v2, fmt, out):
    """Compare two versions of a paper and compute Revision Completeness Score.

    FILE_V1 is the original submission, FILE_V2 is the revised version.
    Runs critique on both, then computes delta_omega and addressed issues.

    Examples:\n
      veritas diff paper_v1.pdf paper_v2.pdf\n
      veritas diff paper_v1.md paper_v2.md --format json --out revision.json
    """
    from ..rebuttal.revision_tracker import RevisionTracker

    engine = _load_engine()
    p1 = pathlib.Path(file_v1)
    p2 = pathlib.Path(file_v2)
    if not p1.exists():
        raise click.ClickException(f"File not found: {file_v1}")
    if not p2.exists():
        raise click.ClickException(f"File not found: {file_v2}")

    click.echo(f"[>] Critiquing {p1.name} ...")
    r1 = engine.critique(p1.read_text(encoding="utf-8", errors="replace"))
    click.echo(f"[>] Critiquing {p2.name} ...")
    r2 = engine.critique(p2.read_text(encoding="utf-8", errors="replace"))

    tracker = RevisionTracker()
    result = tracker.compare(r1, r2)

    if fmt == "json":
        output = json.dumps(result.as_dict(), indent=2, ensure_ascii=False)
    else:
        grade_icon = {"COMPLETE": "[+]", "PARTIAL": "[~]", "INSUFFICIENT": "[!]"}.get(
            result.revision_grade.value, "[?]"
        )
        lines = [
            "VERITAS Revision Diff",
            f"  V1 omega: {r1.omega_score:.4f}   V2 omega: {r2.omega_score:.4f}"
            f"   delta: {result.delta_omega:+.4f}",
            f"  RCS: {result.rcs:.4f}  "
            f"  {grade_icon} Grade: {result.revision_grade.value}",
            f"  Addressed: {result.addressed_count}/{result.total_v1_issues} issues",
            f"  Improved: {'yes' if result.improved else 'no'}",
        ]
        if result.addressed_codes:
            lines.append(f"  Addressed codes: {', '.join(result.addressed_codes)}")
        if result.remaining_codes:
            lines.append(f"  Remaining codes: {', '.join(result.remaining_codes)}")
        output = "\n".join(lines)

    if out:
        pathlib.Path(out).write_text(output, encoding="utf-8")
        click.echo(f"[+] Diff result saved to {out}")
    else:
        click.echo(output)


# ---------------------------------------------------------------------------
# journal-profiles
# ---------------------------------------------------------------------------
@main.command("journal-profiles")
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format.",
)
def journal_profiles_cmd(fmt):
    """List all built-in journal profiles with acceptance thresholds.

    Examples:\n
      veritas journal-profiles\n
      veritas journal-profiles --format json
    """
    from ..journal.journal_profiles import JOURNAL_PROFILES

    if fmt == "json":
        output = json.dumps(
            {k: v.as_dict() for k, v in JOURNAL_PROFILES.items()},
            indent=2,
            ensure_ascii=False,
        )
    else:
        lines = ["VERITAS Journal Profiles", ""]
        for key, profile in JOURNAL_PROFILES.items():
            lines.append(
                f"  {key:<10}  accept>={profile.accept_omega:.2f}  "
                f"revise>={profile.revise_omega:.2f}  — {profile.description}"
            )
        output = "\n".join(lines)

    click.echo(output)


# ---------------------------------------------------------------------------
# domains
# ---------------------------------------------------------------------------
@main.group()
def domains():
    """Domain plugin management (list registered IRF scoring domains)."""


@domains.command("list")
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format.",
)
def domains_list(fmt):
    """List all registered IRF scoring domains (built-in + plugins).

    Built-in domains: biomedical, cs, math.
    External plugins registered via entry_points group 'veritas.domains' are
    included automatically when installed.

    Examples:\n
      veritas domains list\n
      veritas domains list --format json
    """
    from ..logos.domain.registry import list_domain_keys, get_domain

    keys = list_domain_keys()
    if fmt == "json":
        result = {}
        for k in keys:
            rs = get_domain(k)
            result[k] = {
                "name": rs.name,
                "composite_threshold": rs.composite_threshold,
                "component_min": rs.component_min,
                "marker_counts": {
                    dim: len(rs.markers_for(dim)) for dim in ("M", "A", "D", "I", "F", "P")
                },
            }
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        lines = ["VERITAS Registered IRF Domains", ""]
        for k in sorted(keys):
            rs = get_domain(k)
            counts = "/".join(
                str(len(rs.markers_for(d))) for d in ("M", "A", "D", "I", "F", "P")
            )
            lines.append(
                f"  {k:<14}  [{rs.name}]  "
                f"threshold={rs.composite_threshold:.2f}  "
                f"markers(M/A/D/I/F/P)={counts}"
            )
        lines.append("")
        lines.append("Use: veritas critique paper.pdf --domain <key>")
        click.echo("\n".join(lines))


if __name__ == "__main__":
    main()
