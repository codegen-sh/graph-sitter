import importlib
import importlib.util
import inspect
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import rich_click as click

from codemods.codemod import Codemod
from graph_sitter.cli.commands.run.main import _parse_arguments, _parse_language
from graph_sitter.cli.commands.run.run_local import run_local
from graph_sitter.configs.models.codebase import GraphBackend, RustFallbackMode
from graph_sitter.shared.enums.programming_language import ProgrammingLanguage


@dataclass
class ImportPathTransform:
    name: str
    target: Any
    subdirectories: list[str] | None = None
    language: ProgrammingLanguage | None = None

    def run(self, codebase, arguments: dict[str, Any] | None = None) -> Any:
        callable_target = _get_callable(self.target)
        call_arguments = _build_call_arguments(callable_target, arguments)
        return callable_target(codebase, *call_arguments)


def _load_module(module_ref: str) -> ModuleType:
    if module_ref.endswith(".py") or "/" in module_ref or "\\" in module_ref:
        module_path = Path(module_ref).expanduser()
        if not module_path.is_absolute():
            module_path = Path.cwd() / module_path
        module_path = module_path.resolve()
        if not module_path.exists():
            msg = f"Transform module file does not exist: {module_path}"
            raise click.ClickException(msg)

        spec = importlib.util.spec_from_file_location(f"graph_sitter_transform_{module_path.stem}", module_path)
        if spec is None or spec.loader is None:
            msg = f"Could not load transform module from {module_path}"
            raise click.ClickException(msg)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    try:
        return importlib.import_module(module_ref)
    except ImportError as error:
        msg = f"Could not import transform module '{module_ref}': {error}"
        raise click.ClickException(msg) from error


def _load_object(specifier: str) -> Any:
    if ":" not in specifier:
        msg = "Transform specifier must be MODULE:OBJECT, for example ./codemod.py:run"
        raise click.ClickException(msg)

    module_ref, object_ref = specifier.split(":", 1)
    if not module_ref or not object_ref:
        msg = "Transform specifier must include both MODULE and OBJECT"
        raise click.ClickException(msg)

    target: Any = _load_module(module_ref)
    try:
        for part in object_ref.split("."):
            target = getattr(target, part)
    except AttributeError as error:
        msg = f"Transform object '{object_ref}' was not found in '{module_ref}'"
        raise click.ClickException(msg) from error
    return target


def _get_callable(target: Any) -> Any:
    if inspect.isclass(target):
        if issubclass(target, Codemod):
            target = target()
        else:
            msg = f"Transform class '{target.__name__}' must inherit from codemods.codemod.Codemod"
            raise click.ClickException(msg)

    execute = getattr(target, "execute", None)
    if callable(execute):
        return execute

    if callable(target):
        return target

    msg = "Transform object must be a function, Codemod subclass, Codemod instance, or object with callable execute"
    raise click.ClickException(msg)


def _build_call_arguments(callable_target: Any, arguments: dict[str, Any] | None) -> list[Any]:
    try:
        signature = inspect.signature(callable_target)
    except (TypeError, ValueError):
        if arguments:
            msg = "Transform target does not expose a signature and cannot accept --arguments"
            raise click.ClickException(msg)
        return []

    parameters = signature.parameters
    if "arguments" not in parameters:
        if arguments:
            msg = "Transform target does not accept an arguments parameter"
            raise click.ClickException(msg)
        return []

    parameter = parameters["arguments"]
    if arguments is None:
        if parameter.default is inspect.Signature.empty:
            msg = "Transform target requires --arguments"
            raise click.ClickException(msg)
        return []

    annotation = parameter.annotation
    if isinstance(annotation, str):
        annotation = getattr(inspect.getmodule(callable_target), annotation, None)
    if hasattr(annotation, "model_validate"):
        return [annotation.model_validate(arguments)]
    return [arguments]


def _normalize_subdirectories(repo_path: Path, raw_subdirectories: tuple[str, ...]) -> list[str] | None:
    if not raw_subdirectories:
        return None

    repo_root = repo_path.resolve()
    subdirectories: list[str] = []
    for raw_subdirectory in raw_subdirectories:
        raw_path = Path(raw_subdirectory).expanduser()
        if raw_path.is_absolute():
            try:
                relative_path = raw_path.resolve().relative_to(repo_root)
            except ValueError as error:
                msg = f"--subdir must be inside the target repository: {raw_subdirectory}"
                raise click.ClickException(msg) from error
        else:
            relative_path = raw_path

        normalized = relative_path.as_posix().removeprefix("./").rstrip("/")
        if normalized in {"", "."}:
            continue

        full_path = repo_root / normalized
        if not full_path.exists():
            msg = f"--subdir path does not exist: {normalized}"
            raise click.ClickException(msg)
        if full_path.is_dir():
            normalized = f"{normalized}/"
        subdirectories.append(normalized)

    return subdirectories or None


@click.command(name="transform")
@click.argument("specifier", required=True)
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@click.option("--diff-preview", type=int, help="Show a preview of the first N lines of the diff")
@click.option("--arguments", type=str, help="Arguments as a json string to pass as the transform's 'arguments' parameter")
@click.option("--backend", type=click.Choice(["python", "rust", "auto"]), default="python", show_default=True, help="Graph backend to use.")
@click.option("--fallback", type=click.Choice(["python", "error"]), default="python", show_default=True, help="Fallback behavior when the Rust backend is unavailable.")
@click.option("--language", type=click.Choice(["auto", "python", "typescript"]), default="auto", show_default=True, help="Project language.")
@click.option("--check", is_flag=True, help="Run in a temporary sandbox and exit non-zero if changes would be produced.")
@click.option("--write", is_flag=True, help="Apply changes to the target repo.")
@click.option("--subdir", "subdirectories", multiple=True, help="Limit parsing to a repository-relative subdirectory or file. Can be passed more than once.")
def transform_command(
    specifier: str,
    path: Path,
    diff_preview: int | None = None,
    arguments: str | None = None,
    backend: str = "python",
    fallback: str = "python",
    language: str = "auto",
    check: bool = False,
    write: bool = False,
    subdirectories: tuple[str, ...] = (),
) -> None:
    """Run an import-path transform against a local codebase."""
    if check and write:
        msg = "--check and --write cannot be used together"
        raise click.ClickException(msg)
    if not check and not write:
        msg = "Choose either --check to preview changes or --write to apply them."
        raise click.ClickException(msg)

    repo_path = path.resolve()
    transform = ImportPathTransform(
        name=specifier,
        target=_load_object(specifier),
        subdirectories=_normalize_subdirectories(repo_path, subdirectories),
    )
    run_local(
        None,
        transform,
        diff_preview=diff_preview,
        repo_path=repo_path,
        arguments=_parse_arguments(arguments),
        backend=GraphBackend(backend),
        fallback=RustFallbackMode(fallback),
        language=_parse_language(language),
        check=check,
        check_function_resolver=lambda _sandbox_repo_path: transform,
    )
