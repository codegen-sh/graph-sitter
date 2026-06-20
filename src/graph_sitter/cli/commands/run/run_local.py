import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import rich
import rich.progress
import rich_click as click
from rich.panel import Panel
from rich.status import Status

from graph_sitter.cli.auth.session import CliSession
from graph_sitter.cli.utils.function_finder import DecoratedFunction
from graph_sitter.codebase.config import ProjectConfig
from graph_sitter.codebase.progress.progress import Progress
from graph_sitter.codebase.progress.task import Task
from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode
from graph_sitter.core.codebase import Codebase
from graph_sitter.git.repo_operator.repo_operator import RepoOperator
from graph_sitter.git.schemas.repo_config import RepoConfig
from graph_sitter.git.utils.language import determine_project_language
from graph_sitter.shared.enums.programming_language import ProgrammingLanguage

_CHECK_SANDBOX_IGNORES = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
}


class RichTask(Task):
    _task: rich.progress.Task
    _progress: rich.progress.Progress
    _total: int | None

    def __init__(self, task: rich.progress.Task, progress: rich.progress.Progress, total: int | None = None) -> None:
        self._task = task
        self._progress = progress
        self._total = total

    def update(self, message: str, count: int | None = None) -> None:
        self._progress.update(self._task, description=message, completed=count)

    def end(self) -> None:
        self._progress.update(self._task, completed=self._total)


class RichProgress(Progress[RichTask]):
    _progress: rich.progress.Progress

    def __init__(self, progress: rich.progress.Progress) -> None:
        self._progress = progress

    def begin(self, message: str, count: int | None = None) -> RichTask:
        task = self._progress.add_task(description=message, total=count)
        return RichTask(task, progress=self._progress, total=count)


def parse_codebase(
    repo_path: Path,
    subdirectories: list[str] | None = None,
    language: ProgrammingLanguage | None = None,
    backend: GraphBackend = GraphBackend.PYTHON,
    fallback: RustFallbackMode = RustFallbackMode.PYTHON,
) -> Codebase:
    """Parse the codebase at the given root.

    Args:
        repo_root: Path to the repository root

    Returns:
        Parsed Codebase object
    """
    with rich.progress.Progress(
        rich.progress.TextColumn("[progress.description]{task.description}"),
        rich.progress.BarColumn(bar_width=None),
        rich.progress.TaskProgressColumn(),
        rich.progress.TimeRemainingColumn(),
        rich.progress.TimeElapsedColumn(),
        expand=True,
    ) as progress:
        codebase = Codebase(
            projects=[
                ProjectConfig(
                    repo_operator=RepoOperator(repo_config=RepoConfig.from_repo_path(repo_path=repo_path)),
                    subdirectories=subdirectories,
                    programming_language=language or determine_project_language(repo_path),
                )
            ],
            config=CodebaseConfig(graph_backend=backend, rust_fallback=fallback),
            progress=RichProgress(progress),
        )
    return codebase


def _ignore_check_sandbox_entries(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in _CHECK_SANDBOX_IGNORES}


def _initialize_check_sandbox_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", str(repo_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.email", "graph-sitter-check@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Graph-sitter Check"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-m", "graph-sitter check baseline"], check=True, capture_output=True)


def _print_diff(result: str, diff_preview: int | None = None) -> None:
    rich.print("")
    diff_lines = result.splitlines()
    truncated = diff_preview is not None and len(diff_lines) > diff_preview
    limited_diff = "\n".join(diff_lines[:diff_preview] if diff_preview is not None else diff_lines)

    if truncated:
        limited_diff += f"\n\n...\n\n[yellow]diff truncated to {diff_preview} lines[/yellow]"

    panel = Panel(limited_diff, title="[bold]Diff Preview[/bold]", border_style="blue", padding=(1, 2), expand=False)
    rich.print(panel)


def _execute_codemod(
    *,
    repo_path: Path,
    function: DecoratedFunction,
    arguments: dict | None,
    backend: GraphBackend,
    fallback: RustFallbackMode,
    language: ProgrammingLanguage | None,
) -> str:
    codebase_language = language or function.language
    rich.print(f"Parsing codebase at {repo_path} with subdirectories {function.subdirectories or 'ALL'} and language {codebase_language or 'AUTO'} ...")
    codebase = parse_codebase(
        repo_path=repo_path,
        subdirectories=function.subdirectories,
        language=codebase_language,
        backend=backend,
        fallback=fallback,
    )
    with Status("[bold]Running codemod...", spinner="dots") as status:
        status.update("")
        function.run(codebase, arguments=arguments)
        status.update("[bold green]✓ Completed codemod")

    return codebase.get_diff()


def _run_check(
    *,
    source_repo_path: Path,
    function: DecoratedFunction,
    diff_preview: int | None,
    arguments: dict | None,
    backend: GraphBackend,
    fallback: RustFallbackMode,
    language: ProgrammingLanguage | None,
    check_function_resolver: Callable[[Path], Any] | None = None,
) -> None:
    from graph_sitter.cli.utils.codemod_manager import CodemodManager

    with TemporaryDirectory(prefix="graph-sitter-check-") as temporary_directory:
        sandbox_repo_path = Path(temporary_directory) / source_repo_path.name
        shutil.copytree(source_repo_path, sandbox_repo_path, ignore=_ignore_check_sandbox_entries)
        _initialize_check_sandbox_repo(sandbox_repo_path)
        sandbox_function = check_function_resolver(sandbox_repo_path) if check_function_resolver else CodemodManager.get_codemod(function.name, start_path=sandbox_repo_path)
        result = _execute_codemod(
            repo_path=sandbox_repo_path,
            function=sandbox_function,
            arguments=arguments,
            backend=backend,
            fallback=fallback,
            language=language,
        )

    if not result:
        rich.print("\n[green]✓ No changes would be produced by this codemod[/green]")
        return

    rich.print("\n[yellow]Codemod would produce changes[/yellow]")
    _print_diff(result, diff_preview=diff_preview)
    raise click.exceptions.Exit(1)


def run_local(
    session: CliSession | None,
    function: DecoratedFunction,
    diff_preview: int | None = None,
    *,
    repo_path: Path | None = None,
    arguments: dict | None = None,
    backend: GraphBackend = GraphBackend.PYTHON,
    fallback: RustFallbackMode = RustFallbackMode.PYTHON,
    language: ProgrammingLanguage | None = None,
    check: bool = False,
    check_function_resolver: Callable[[Path], Any] | None = None,
) -> None:
    """Run a function locally against the codebase.

    Args:
        session: The current codegen session, if running from initialized session state
        function: The function to run
        diff_preview: Number of lines of diff to preview (None for all)
    """
    repo_path = repo_path or session.repo_path

    if check:
        _run_check(
            source_repo_path=repo_path,
            function=function,
            diff_preview=diff_preview,
            arguments=arguments,
            backend=backend,
            fallback=fallback,
            language=language,
            check_function_resolver=check_function_resolver,
        )
        return

    result = _execute_codemod(
        repo_path=repo_path,
        function=function,
        arguments=arguments,
        backend=backend,
        fallback=fallback,
        language=language,
    )

    # Handle no changes case
    if not result:
        rich.print("\n[yellow]No changes were produced by this codemod[/yellow]")
        return

    # Show diff preview if requested
    if diff_preview:
        _print_diff(result, diff_preview=diff_preview)

    # Apply changes
    rich.print("")
    rich.print("[green]✓ Changes have been applied to your local filesystem[/green]")
