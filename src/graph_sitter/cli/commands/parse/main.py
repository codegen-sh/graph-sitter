import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import rich
import rich_click as click

from graph_sitter.codebase.config import ProjectConfig
from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode
from graph_sitter.core.codebase import Codebase
from graph_sitter.shared.enums.programming_language import ProgrammingLanguage


@contextmanager
def _suppress_parse_logs(disabled_level: int) -> Iterator[None]:
    previous_disabled_level = logging.root.manager.disable
    logging.disable(disabled_level)
    try:
        yield
    finally:
        logging.disable(previous_disabled_level)


def _parse_language(value: str) -> ProgrammingLanguage | None:
    if value == "auto":
        return None
    if value == "python":
        return ProgrammingLanguage.PYTHON
    if value == "typescript":
        return ProgrammingLanguage.TYPESCRIPT
    msg = f"Unsupported language: {value}"
    raise click.ClickException(msg)


def _normalize_subdirectories(project: ProjectConfig, raw_subdirectories: tuple[str, ...]) -> list[str] | None:
    if not raw_subdirectories:
        return project.subdirectories

    repo_root = Path(project.repo_operator.repo_path).resolve()
    base_path = Path(project.base_path) if project.base_path else Path()
    subdirectories: list[str] = []
    for raw_subdirectory in raw_subdirectories:
        raw_path = Path(raw_subdirectory).expanduser()
        if raw_path.is_absolute():
            try:
                relative_path = raw_path.resolve().relative_to(repo_root)
            except ValueError as error:
                msg = f"--subdir must be inside the git repository: {raw_subdirectory}"
                raise click.ClickException(msg) from error
        else:
            relative_path = base_path / raw_path

        normalized = relative_path.as_posix().removeprefix("./").rstrip("/")
        if normalized in {"", "."}:
            if project.base_path:
                normalized = project.base_path.rstrip("/")
            else:
                continue

        full_path = repo_root / normalized
        if not full_path.exists():
            msg = f"--subdir path does not exist: {normalized}"
            raise click.ClickException(msg)
        if full_path.is_dir():
            normalized = f"{normalized}/"
        subdirectories.append(normalized)

    return subdirectories or project.subdirectories


def _project_for_parse(path: Path, language: ProgrammingLanguage | None, subdirectories: tuple[str, ...]) -> ProjectConfig:
    project = ProjectConfig.from_path(str(path), programming_language=language)
    normalized_subdirectories = _normalize_subdirectories(project, subdirectories)
    if normalized_subdirectories != project.subdirectories:
        project = project.model_copy(update={"subdirectories": normalized_subdirectories})
    return project


def _base_payload(codebase: Codebase, *, path: Path, backend: str, elapsed_seconds: float) -> dict[str, Any]:
    rust_summary = codebase.rust_index_summary
    actual_backend = "rust" if rust_summary is not None else "python"

    payload: dict[str, Any] = {
        "path": str(path.resolve()),
        "backend_requested": backend,
        "backend": actual_backend,
        "language": codebase.language.value.lower(),
        "elapsed_seconds": round(elapsed_seconds, 6),
        "subdirectories": codebase.ctx.projects[0].subdirectories,
    }

    if rust_summary is not None:
        payload.update(
            {
                "files": rust_summary.files,
                "symbols": rust_summary.symbols,
                "classes": rust_summary.classes,
                "functions": rust_summary.functions,
                "global_variables": rust_summary.global_variables,
                "imports": rust_summary.imports,
                "exports": rust_summary.exports,
                "references": rust_summary.references,
                "external_references": rust_summary.external_references,
                "dependencies": rust_summary.dependencies,
                "subclass_edges": rust_summary.subclass_edges,
                "files_with_errors": rust_summary.files_with_errors,
                "rust_backend_error": codebase.ctx.rust_backend_error,
            }
        )
        return payload

    payload.update(
        {
            "files": len(codebase.files),
            "symbols": len(codebase.symbols),
            "classes": len(codebase.classes),
            "functions": len(codebase.functions),
            "global_variables": len(codebase.global_vars),
            "imports": len(codebase.imports),
            "exports": _safe_export_count(codebase),
            "references": None,
            "external_references": None,
            "dependencies": len(codebase.ctx.edges),
            "subclass_edges": None,
            "files_with_errors": None,
            "rust_backend_error": codebase.ctx.rust_backend_error,
        }
    )
    return payload


def _safe_export_count(codebase: Codebase) -> int:
    if codebase.language != ProgrammingLanguage.TYPESCRIPT:
        return 0
    return len(codebase.exports)


def _print_summary(payload: dict[str, Any]) -> None:
    rich.print(f"[bold]Graph-sitter parse summary[/bold] ({payload['backend']}, {payload['language']})")
    rich.print(f"Path: {payload['path']}")
    rich.print(f"Subdirectories: {payload['subdirectories'] or 'ALL'}")
    rich.print(f"Elapsed: {payload['elapsed_seconds']:.3f}s")
    rich.print(
        "Files: {files}  Symbols: {symbols}  Imports: {imports}  Exports: {exports}  Dependencies: {dependencies}".format(
            **payload,
        )
    )
    if payload.get("rust_backend_error"):
        rich.print(f"[yellow]Rust backend fallback:[/yellow] {payload['rust_backend_error']}")


@click.command(name="parse")
@click.argument("path", type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."), required=False)
@click.option("--backend", type=click.Choice(["python", "rust", "auto"]), default="python", show_default=True, help="Graph backend to use.")
@click.option("--fallback", type=click.Choice(["python", "error"]), default="error", show_default=True, help="Fallback behavior when the Rust backend is unavailable.")
@click.option("--language", type=click.Choice(["auto", "python", "typescript"]), default="auto", show_default=True, help="Project language.")
@click.option("--format", "output_format", type=click.Choice(["summary", "json"]), default="summary", show_default=True, help="Output format.")
@click.option("--subdir", "subdirectories", multiple=True, help="Limit parsing to a repository-relative subdirectory or file. Can be passed more than once.")
def parse_command(path: Path, backend: str, fallback: str, language: str, output_format: str, subdirectories: tuple[str, ...]) -> None:
    """Parse a local codebase and print graph summary counts."""
    config = CodebaseConfig(
        graph_backend=GraphBackend(backend),
        rust_fallback=RustFallbackMode(fallback),
    )
    parsed_language = _parse_language(language)
    project = _project_for_parse(path, parsed_language, subdirectories)

    start = time.perf_counter()
    try:
        disabled_level = logging.WARNING if output_format == "json" else logging.INFO
        with _suppress_parse_logs(disabled_level):
            codebase = Codebase(projects=[project], config=config)
    except RuntimeError as error:
        raise click.ClickException(str(error)) from error
    elapsed_seconds = time.perf_counter() - start

    payload = _base_payload(codebase, path=path, backend=backend, elapsed_seconds=elapsed_seconds)
    if output_format == "json":
        click.echo(json.dumps(payload, sort_keys=True))
    else:
        _print_summary(payload)
