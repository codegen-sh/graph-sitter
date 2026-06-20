import json
import os
from pathlib import Path

import rich_click as click

from graph_sitter.cli.auth.session import CliSession
from graph_sitter.cli.utils.codemod_manager import CodemodManager
from graph_sitter.cli.utils.json_schema import validate_json
from graph_sitter.cli.workspace.venv_manager import VenvManager
from graph_sitter.configs.models.codebase import GraphBackend, RustFallbackMode
from graph_sitter.shared.enums.programming_language import ProgrammingLanguage


def _parse_language(value: str) -> ProgrammingLanguage | None:
    if value == "auto":
        return None
    if value == "python":
        return ProgrammingLanguage.PYTHON
    if value == "typescript":
        return ProgrammingLanguage.TYPESCRIPT
    msg = f"Unsupported language: {value}"
    raise click.ClickException(msg)


def _parse_arguments(raw_arguments: str | None) -> dict | None:
    if raw_arguments is None:
        return None
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError as error:
        msg = f"Invalid --arguments JSON: {error.msg}"
        raise click.ClickException(msg) from error
    if not isinstance(parsed, dict):
        msg = "--arguments must be a JSON object"
        raise click.ClickException(msg)
    return parsed


@click.command(name="run")
@click.argument("label", required=True)
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False))
@click.option("--daemon", "-d", is_flag=True, help="Run the codemod against a running daemon.")
@click.option("--diff-preview", type=int, help="Show a preview of the first N lines of the diff")
@click.option("--arguments", type=str, help="Arguments as a JSON object to pass to the codemod's arguments parameter.")
@click.option("--backend", type=click.Choice(["python", "rust", "auto"]), default="python", show_default=True, help="Graph backend to use.")
@click.option("--fallback", type=click.Choice(["python", "error"]), default="python", show_default=True, help="Fallback behavior when the Rust backend is unavailable.")
@click.option("--language", type=click.Choice(["auto", "python", "typescript"]), default="auto", show_default=True, help="Project language.")
@click.option("--check", is_flag=True, help="Run in a temporary sandbox and exit non-zero if changes would be produced.")
@click.option("--write", is_flag=True, help="Apply changes to the target repo. This remains the default for compatibility.")
def run_command(
    label: str,
    path: Path | None = None,
    daemon: bool = False,
    diff_preview: int | None = None,
    arguments: str | None = None,
    backend: str = "python",
    fallback: str = "python",
    language: str = "auto",
    check: bool = False,
    write: bool = False,
):
    """Run a registered codemod by label."""
    if check and write:
        msg = "--check and --write cannot be used together"
        raise click.ClickException(msg)

    session = None if path is not None else CliSession.from_active_session()
    if path is None and session is None:
        msg = "Graph-sitter not initialized. Pass PATH or run `gs init` from a git repo workspace."
        raise click.ClickException(msg)

    repo_path = path.resolve() if path is not None else session.repo_path

    if session is not None:
        # Ensure venv is initialized for backwards-compatible active-session runs.
        venv = VenvManager(session.codegen_dir)
        if not venv.is_initialized():
            msg = "Virtual environment not found. Please run 'gs init' first."
            raise click.ClickException(msg)

        # Set up environment with venv
        os.environ["VIRTUAL_ENV"] = str(venv.venv_dir)
        os.environ["PATH"] = f"{venv.venv_dir}/bin:{os.environ['PATH']}"

    # Get and validate the codemod
    codemod = CodemodManager.get_codemod(label, start_path=repo_path)
    arguments_json = _parse_arguments(arguments)

    # Handle arguments if needed
    if codemod.arguments_type_schema and not arguments:
        msg = f"This codemod requires the --arguments parameter. Expected schema: {codemod.arguments_type_schema}"
        raise click.ClickException(msg)

    if codemod.arguments_type_schema and arguments_json:
        is_valid = validate_json(codemod.arguments_type_schema, arguments_json)
        if not is_valid:
            msg = f"Invalid arguments format. Expected schema: {codemod.arguments_type_schema}"
            raise click.ClickException(msg)
    elif arguments_json and not any(parameter_name == "arguments" for parameter_name, _ in codemod.parameters):
        msg = f"Codemod '{label}' does not accept an arguments parameter"
        raise click.ClickException(msg)

    # Run the codemod
    if daemon:
        if check:
            msg = "--check is only supported for local codemod runs"
            raise click.ClickException(msg)
        if session is None:
            msg = "--daemon requires an initialized active session. Run without PATH or omit --daemon."
            raise click.ClickException(msg)
        from graph_sitter.cli.commands.run.run_daemon import run_daemon

        run_daemon(session, codemod, diff_preview=diff_preview)
    else:
        from graph_sitter.cli.commands.run.run_local import run_local

        run_local(
            session,
            codemod,
            diff_preview=diff_preview,
            repo_path=repo_path,
            arguments=arguments_json,
            backend=GraphBackend(backend),
            fallback=RustFallbackMode(fallback),
            language=_parse_language(language),
            check=check,
        )
