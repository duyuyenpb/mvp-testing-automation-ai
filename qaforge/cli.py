"""
QAForge CLI entry point (click).

Includes the MVP flow commands: `plan`, `generate`, `run`, and `heal`,
plus `init` for Week 6 scaffolding and a few diagnostic helpers.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from qaforge import __version__
from qaforge.context import PROJECT_ROOT, build_system_prompt, list_skills
from qaforge.generator import GenerateResult, generate_from_plan
from qaforge.healer import format_failure_brief, heal as run_heal
from qaforge.initializer import init_project
from qaforge.integration import run as integration_run
from qaforge.llm import ask_llm
from qaforge.planner import PlanResult, plan_feature, save_plan, slugify
from qaforge.runner import diagnose_environment, format_summary, run_tests

load_dotenv()

console = Console()
err = Console(stderr=True)


def _configure_console_encoding() -> None:
    """Prefer UTF-8 output on Windows consoles that default to cp1252."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


_configure_console_encoding()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="qaforge")
def main() -> None:
    """QAForge: AI-driven test automation. Plan → Generate → Run → Heal."""


# ----------------------- Week 1 commands -----------------------


@main.command()
@click.argument("skills", nargs=-1)
def context(skills: tuple[str, ...]) -> None:
    """Print the resolved system prompt (knowledge.md + skills)."""
    prompt = build_system_prompt(list(skills) if skills else None)
    click.echo(prompt)
    err.print(f"[dim][context] {len(prompt)} chars[/dim]")


@main.command()
def skills() -> None:
    """List available skills."""
    names = list_skills()
    if not names:
        click.echo("(no skills found in skills/)")
        return
    for n in names:
        click.echo(f"- {n}")


@main.command()
@click.argument("question", nargs=-1, required=True)
@click.option("-s", "--skill", "skills_filter", multiple=True, help="Restrict to specific skills")
def ask(question: tuple[str, ...], skills_filter: tuple[str, ...]) -> None:
    """Ask the configured LLM a question with full project context loaded."""
    q = " ".join(question).strip()
    system = build_system_prompt(list(skills_filter) if skills_filter else None)
    result = ask_llm(system=system, user=q)
    click.echo(result.text)
    err.print(
        f"[dim][ask] model={result.model} in={result.input_tokens} out={result.output_tokens}[/dim]"
    )


@main.command()
@click.argument("question", nargs=-1)
def integration(question: tuple[str, ...]) -> None:
    """Week 1 integration smoke: load context + ask the configured LLM + assert project-aware."""
    rc = integration_run(" ".join(question).strip() or None)
    sys.exit(rc)


# ----------------------- Week 2: plan -----------------------


@main.command()
@click.argument("description", nargs=-1)
@click.option(
    "--file",
    "from_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Read the feature description from a file (overrides positional args).",
)
@click.option("--auto", is_flag=True, help="Skip the interactive approval prompt.")
@click.option(
    "--out",
    "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Override the test-plans/ directory.",
)
def plan(
    description: tuple[str, ...],
    from_file: Optional[Path],
    auto: bool,
    out_dir: Optional[Path],
) -> None:
    """Generate a Markdown test plan from a feature DESCRIPTION (or --file)."""
    feature_text = _resolve_feature_text(description, from_file)

    err.print("[dim][plan] asking configured LLM…[/dim]")
    try:
        result = plan_feature(feature_text)
    except ValueError as exc:
        err.print(f"[red][plan] generation failed:[/red] {exc}")
        sys.exit(1)

    while True:
        _show_plan(result)
        if auto:
            decision = "y"
        else:
            decision = _prompt_decision()

        if decision == "y":
            target_root = (out_dir.parent if out_dir else PROJECT_ROOT)
            # If user passed --out, write directly there; otherwise use test-plans/ under root.
            if out_dir:
                out_dir.mkdir(parents=True, exist_ok=True)
                from qaforge.planner import next_counter
                counter = next_counter(out_dir)
                path = out_dir / f"{counter:03d}-{result.slug}.md"
                path.write_text(result.markdown.rstrip() + "\n", encoding="utf-8")
            else:
                path = save_plan(result.markdown, result.slug)
            err.print(
                f"[green][plan] saved → {path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path}[/green]"
            )
            err.print(
                f"[dim][plan] tokens: in={result.input_tokens} out={result.output_tokens} "
                f"model={result.model}[/dim]"
            )
            return

        if decision == "n":
            err.print("[yellow][plan] discarded.[/yellow]")
            sys.exit(2)

        # decision == "edit": let the user describe changes, re-roll once.
        feedback = click.prompt(
            "What should change? (1-2 sentences; leave empty to cancel)",
            default="",
            show_default=False,
        ).strip()
        if not feedback:
            err.print("[yellow][plan] no feedback given; discarding.[/yellow]")
            sys.exit(2)

        err.print("[dim][plan] regenerating with feedback…[/dim]")
        revised_feature = (
            f"{feature_text}\n\n"
            f"REVISION FEEDBACK (apply this when redrafting the plan):\n{feedback}"
        )
        try:
            result = plan_feature(revised_feature)
        except ValueError as exc:
            err.print(f"[red][plan] generation failed:[/red] {exc}")
            sys.exit(1)


# ----------------------- Week 3-5: generate / run / heal -----------------------


@main.command()
@click.option(
    "--plan",
    "plan_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Path to a saved plan markdown file (under test-plans/).",
)
@click.option("--no-run", is_flag=True, help="Skip the first-run pytest check after compile.")
@click.option("--no-retry", is_flag=True, help="Skip the single retry on compile error.")
def generate(plan_path: Path, no_run: bool, no_retry: bool) -> None:
    """Test plan → test_*.py + page object files."""
    err.print(f"[dim][generate] reading plan: {plan_path}[/dim]")
    err.print("[dim][generate] asking configured LLM…[/dim]")
    result: GenerateResult = generate_from_plan(
        plan_path,
        retry_on_compile_error=not no_retry,
        run_first=not no_run,
    )

    err.print(
        f"[dim][generate] attempts={result.attempts} model={result.model} "
        f"tokens in={result.input_tokens} out={result.output_tokens}[/dim]"
    )

    if not result.files:
        err.print("[red][generate] no files were produced.[/red]")
        for line in result.compile_errors:
            err.print(f"[red]  {line}[/red]")
        sys.exit(1)

    for f in result.files:
        rel = f.path
        marker = "✓" if result.compile_ok else "·"
        console.print(f"  [green]{marker}[/green] {rel}")

    if not result.compile_ok:
        err.print("[red][generate] compile check FAILED:[/red]")
        for line in result.compile_errors:
            err.print(f"[red]{line}[/red]")
        sys.exit(3)

    err.print("[green][generate] compile check passed.[/green]")

    if result.first_run_ok is None:
        err.print("[yellow][generate] first-run check skipped (--no-run).[/yellow]")
        return

    if result.first_run_ok:
        err.print("[green][generate] first-run check PASSED.[/green]")
    else:
        err.print("[yellow][generate] first-run check FAILED — see summary below.[/yellow]")
        if result.first_run_summary:
            err.print(result.first_run_summary)
        sys.exit(4)


@main.command()
@click.argument("paths", nargs=-1, type=click.Path())
@click.option(
    "--show-failures/--hide-failures",
    default=True,
    help="Print full traceback for each failure.",
)
def run(paths: tuple[str, ...], show_failures: bool) -> None:
    """Run pytest on tests/specs/ (or PATHS) and print a structured summary."""
    target_paths = list(paths) if paths else None
    err.print("[dim][run] launching pytest…[/dim]")
    result = run_tests(target_paths)

    summary = format_summary(result)
    if result.all_passed:
        err.print(f"[green][run] {summary}[/green]")
    else:
        err.print(f"[yellow][run] {summary}[/yellow]")

    if result.report_path:
        report = result.report_path
        label = report.relative_to(PROJECT_ROOT) if report.is_relative_to(PROJECT_ROOT) else report
        err.print(f"[cyan][run] HTML report → {label}[/cyan]")

    if result.failures and show_failures:
        err.print("")
        for f in result.failures:
            console.print(f"  [red]{format_failure_brief(f)}[/red]")
            tb = f.traceback.strip()
            if tb:
                console.print(f"    [dim]{tb.splitlines()[-1][:200]}[/dim]")

    hint = diagnose_environment(result)
    if hint:
        err.print(f"\n[yellow][run] hint: {hint}[/yellow]")

    sys.exit(0 if result.all_passed else 1)


@main.command()
@click.argument("paths", nargs=-1, type=click.Path())
@click.option("--auto", is_flag=True, help="Apply patches without asking.")
@click.option(
    "--max-attempts",
    type=int,
    default=3,
    show_default=True,
    help="Maximum heal attempts before giving up.",
)
def heal(paths: tuple[str, ...], auto: bool, max_attempts: int) -> None:
    """Run pytest, then ask the configured LLM to heal failing tests (locator fixes, etc.)."""
    target_paths = list(paths) if paths else None
    err.print("[dim][heal] running tests first…[/dim]")
    initial = run_tests(target_paths)

    if initial.all_passed:
        err.print(f"[green][heal] {format_summary(initial)} — nothing to heal.[/green]")
        sys.exit(0)

    err.print(f"[yellow][heal] initial: {format_summary(initial)}[/yellow]")
    for f in initial.failures:
        console.print(f"  [red]{format_failure_brief(f)}[/red]")

    def _confirm(path: str, diff: str) -> bool:
        console.print(f"\n[bold]Proposed patch for {path}:[/bold]")
        console.print(diff or "(no textual change)", style="white", markup=False)
        answer = click.prompt(
            "Apply this patch? [y]es / [n]o", default="y", show_default=True
        ).strip().lower()
        return answer in ("y", "yes")

    result = run_heal(
        initial,
        max_attempts=max_attempts,
        auto=auto,
        confirm=None if auto else _confirm,
    )

    err.print("")
    err.print(
        f"[dim][heal] attempts={len(result.attempts)} healed={result.healed_count} "
        f"remaining={result.remaining_failures}[/dim]"
    )
    total_in = sum(a.input_tokens for a in result.attempts)
    total_out = sum(a.output_tokens for a in result.attempts)
    if total_in or total_out:
        err.print(f"[dim][heal] tokens: in={total_in} out={total_out} model={result.model}[/dim]")

    for a in result.attempts:
        status = "applied" if a.applied else f"skipped ({a.skipped_reason})"
        err.print(f"  attempt {a.attempt}: {status} — {a.failure.name}")

    if result.succeeded:
        err.print(f"[green][heal] PASSED after healing.[/green]")
        sys.exit(0)

    err.print("[red][heal] still failing — manual inspection needed.[/red]")
    sys.exit(1)


# ----------------------- Week 6: init -----------------------


@main.command()
@click.argument(
    "target",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("."),
)
@click.option("--name", default="my-test-project", help="Project name written into README.md.")
@click.option("--force", is_flag=True, help="Overwrite existing files.")
def init(target: Path, name: str, force: bool) -> None:
    """Scaffold a new QAForge project (knowledge.md, skills/, tests/, CI)."""
    err.print(f"[dim][init] scaffolding into {target}…[/dim]")
    result = init_project(target, name=name, force=force)

    for w in result.written:
        console.print(f"  [green]+[/green] {w}")
    for s in result.skipped:
        console.print(f"  [yellow]·[/yellow] {s} (exists; use --force to overwrite)")

    err.print("")
    err.print(f"[green][init] {len(result.written)} files written, "
              f"{len(result.skipped)} skipped.[/green]")
    err.print("[dim]next: cp .env.example .env  →  configure QAFORGE_LLM_PROVIDER + API key  →  qaforge plan \"...\"[/dim]")


# ----------------------- helpers -----------------------


def _resolve_feature_text(description: tuple[str, ...], from_file: Optional[Path]) -> str:
    if from_file is not None:
        text = from_file.read_text(encoding="utf-8").strip()
    else:
        text = " ".join(description).strip()

    if not text:
        err.print(
            "[red][plan] feature description is empty.[/red] "
            'Pass it inline (qaforge plan "...") or with --file.'
        )
        sys.exit(1)
    return text


def _show_plan(result: PlanResult) -> None:
    console.print(
        Panel(
            Markdown(result.markdown),
            title=f"Test plan: {result.title} (slug: {result.slug})",
            border_style="cyan",
            padding=(1, 2),
        )
    )


def _prompt_decision() -> str:
    while True:
        raw = click.prompt(
            "Approve this plan? [y]es / [n]o / [e]dit",
            default="y",
            show_default=True,
        ).strip().lower()
        if raw in ("y", "yes"):
            return "y"
        if raw in ("n", "no"):
            return "n"
        if raw in ("e", "edit"):
            return "edit"
        err.print("[yellow]please answer y, n, or e[/yellow]")


if __name__ == "__main__":
    main()
