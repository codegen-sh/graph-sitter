from __future__ import annotations

import importlib
import json
import platform
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path
from typing import Any

import rich
import rich_click as click

from graph_sitter.cli.commands.parse.main import _base_payload, _parse_language, _suppress_parse_logs
from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode
from graph_sitter.core.codebase import Codebase


def _distribution_version() -> str | None:
    try:
        return metadata.version("graph-sitter")
    except metadata.PackageNotFoundError:
        return None


def _module_check(module_name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
    except Exception as error:
        return {
            "ok": False,
            "error": f"{type(error).__name__}: {error}",
        }
    return {
        "ok": True,
        "version": getattr(module, "__version__", None),
    }


def _rust_extension_check() -> dict[str, Any]:
    try:
        extension = importlib.import_module("graph_sitter_py")
    except Exception as error:
        return {
            "ok": False,
            "error": f"{type(error).__name__}: {error}",
        }

    details: dict[str, Any] = {
        "ok": True,
        "engine_version": _call_optional_string(extension, "engine_version"),
    }
    debug_info = _call_optional(extension, "debug_info")
    if debug_info is not None:
        details["debug_info"] = {
            "version": getattr(debug_info, "version", None),
            "enabled_features": list(getattr(debug_info, "enabled_features", []) or []),
        }
    return details


def _call_optional(module: Any, name: str) -> Any | None:
    target = getattr(module, name, None)
    if not callable(target):
        return None
    try:
        return target()
    except Exception:
        return None


def _call_optional_string(module: Any, name: str) -> str | None:
    value = _call_optional(module, name)
    if value is None:
        return None
    return str(value)


def _rust_parse_smoke(language: str) -> dict[str, Any]:
    parsed_language = _parse_language(language)
    suffix = ".ts" if language == "typescript" else ".py"
    source = "export function run() {\n  return 1;\n}\n" if language == "typescript" else "def run():\n    return 1\n"

    with tempfile.TemporaryDirectory(prefix="graph-sitter-doctor-") as scratch:
        repo = Path(scratch)
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        (repo / f"doctor{suffix}").write_text(source)
        config = CodebaseConfig(
            graph_backend=GraphBackend.RUST,
            rust_fallback=RustFallbackMode.ERROR,
        )
        try:
            with _suppress_parse_logs(sys.maxsize):
                codebase = Codebase(str(repo), language=parsed_language, config=config)
        except Exception as error:
            return {
                "ok": False,
                "error": f"{type(error).__name__}: {error}",
            }
        payload = _base_payload(codebase, path=repo, backend="rust", elapsed_seconds=0.0)
        return {
            "ok": payload["backend"] == "rust",
            "backend": payload["backend"],
            "language": payload["language"],
            "files": payload["files"],
            "symbols": payload["symbols"],
            "imports": payload["imports"],
            "files_with_errors": payload["files_with_errors"],
            "rust_backend_error": payload["rust_backend_error"],
        }


def _doctor_payload(*, backend: str, language: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "platform": platform.platform(),
        "package": {
            "distribution": "graph-sitter",
            "version": _distribution_version(),
        },
        "dependencies": {
            "tree_sitter": _module_check("tree_sitter"),
            "tree_sitter_python": _module_check("tree_sitter_python"),
            "tree_sitter_typescript": _module_check("tree_sitter_typescript"),
        },
        "rust_extension": _rust_extension_check(),
        "backend_requested": backend,
        "language_requested": language,
    }

    if backend == "rust":
        payload["rust_parse_smoke"] = _rust_parse_smoke(language)

    dependency_failures = [name for name, result in payload["dependencies"].items() if not result["ok"]]
    payload["ok"] = not dependency_failures and (backend != "rust" or payload["rust_extension"]["ok"]) and (backend != "rust" or payload["rust_parse_smoke"]["ok"])
    if dependency_failures:
        payload["dependency_failures"] = dependency_failures
    return payload


def _print_summary(payload: dict[str, Any]) -> None:
    status = "ok" if payload["ok"] else "failed"
    rich.print(f"[bold]Graph-sitter doctor[/bold] ({status})")
    rich.print(f"Python: {payload['python']['version']} ({payload['python']['implementation']})")
    rich.print(f"Package: graph-sitter {payload['package']['version'] or 'not installed as a distribution'}")
    rich.print(f"Platform: {payload['platform']}")
    rich.print("Dependencies:")
    for name, result in payload["dependencies"].items():
        marker = "ok" if result["ok"] else "missing"
        detail = result.get("version") or result.get("error") or ""
        rich.print(f"  {name}: {marker} {detail}")
    rust_extension = payload["rust_extension"]
    if rust_extension["ok"]:
        rich.print(f"Rust extension: ok {rust_extension.get('engine_version') or ''}")
    else:
        rich.print(f"[yellow]Rust extension: unavailable[/yellow] {rust_extension.get('error') or ''}")
    rust_smoke = payload.get("rust_parse_smoke")
    if rust_smoke is not None:
        if rust_smoke["ok"]:
            rich.print(f"Rust parse smoke: ok {rust_smoke['files']} file(s), {rust_smoke['symbols']} symbol(s), {rust_smoke['language']}")
        else:
            rich.print(f"[red]Rust parse smoke: failed[/red] {rust_smoke.get('error') or ''}")


@click.command(name="doctor")
@click.option("--backend", type=click.Choice(["python", "rust"]), default="python", show_default=True, help="Backend readiness to verify.")
@click.option("--language", type=click.Choice(["python", "typescript"]), default="python", show_default=True, help="Language for the optional Rust parse smoke.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable diagnostics.")
def doctor_command(backend: str, language: str, as_json: bool) -> None:
    """Check local graph-sitter installation and optional Rust backend readiness."""
    payload = _doctor_payload(backend=backend, language=language)
    if as_json:
        click.echo(json.dumps(payload, sort_keys=True))
    else:
        _print_summary(payload)
    if not payload["ok"]:
        raise click.exceptions.Exit(1)
