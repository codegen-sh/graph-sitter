from __future__ import annotations

import json
import logging
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any

import psutil
import rich
import rich_click as click
from rich.table import Table

from graph_sitter.cli.commands.parse.main import _base_payload, _parse_language, _project_for_parse, _suppress_parse_logs
from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode
from graph_sitter.core.codebase import Codebase

DIAGNOSTICS_JSON_SCHEMA_VERSION = 1


def _bytes_to_mb(value: int) -> float:
    return value / (1024 * 1024)


def _current_rss_bytes() -> int:
    return int(psutil.Process(os.getpid()).memory_info().rss)


def _max_rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(rss)
    return int(rss * 1024)


def _memory_sample(label: str) -> dict[str, float | str]:
    return {
        "label": label,
        "rss_mb": round(_bytes_to_mb(_current_rss_bytes()), 3),
        "max_rss_mb": round(_bytes_to_mb(_max_rss_bytes()), 3),
    }


def _memory_payload(samples: list[dict[str, float | str]]) -> dict[str, float | list[dict[str, float | str]]]:
    start_rss = float(samples[0]["rss_mb"])
    after_parse_rss = float(samples[1]["rss_mb"])
    after_stats_rss = float(samples[-1]["rss_mb"])
    peak_rss = max(float(sample["max_rss_mb"]) for sample in samples)
    return {
        "rss_start_mb": round(start_rss, 3),
        "rss_after_parse_mb": round(after_parse_rss, 3),
        "rss_after_stats_mb": round(after_stats_rss, 3),
        "rss_delta_mb": round(after_stats_rss - start_rss, 3),
        "peak_rss_mb": round(peak_rss, 3),
        "samples": samples,
    }


def _write_json_payload(payload: dict[str, Any], output: Path | None) -> None:
    contents = json.dumps(payload, sort_keys=True) + "\n"
    if output is None:
        click.echo(contents, nl=False)
        return

    try:
        output.write_text(contents)
    except OSError as error:
        msg = f"Could not write diagnostics JSON output to {output}: {error}"
        raise click.ClickException(msg) from error


def _print_summary(payload: dict[str, Any]) -> None:
    memory = payload["memory"]
    rich.print(f"[bold]Graph-sitter diagnostics[/bold] ({payload['backend']}, {payload['language']})")
    rich.print(f"Path: {payload['path']}")
    rich.print(f"Subdirectories: {payload['subdirectories'] or 'ALL'}")

    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Parse time", f"{payload['parse_seconds']:.3f}s")
    table.add_row("Files", str(payload["files"]))
    table.add_row("Memory after parse", f"{memory['rss_after_parse_mb']:.1f} MB")
    table.add_row("Peak memory", f"{memory['peak_rss_mb']:.1f} MB")
    table.add_row("Memory delta", f"{memory['rss_delta_mb']:+.1f} MB")
    table.add_row("Symbols", str(payload["symbols"]))
    table.add_row("Imports", str(payload["imports"]))
    table.add_row("Exports", str(payload["exports"]))
    table.add_row("Dependencies", str(payload["dependencies"]))
    rich.print(table)

    if payload.get("rust_backend_error"):
        rich.print(f"[yellow]Rust backend fallback:[/yellow] {payload['rust_backend_error']}")


@click.command(name="diagnose")
@click.argument("path", type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."), required=False)
@click.option("--backend", type=click.Choice(["python", "rust", "auto"]), default="auto", show_default=True, help="Graph backend to use.")
@click.option("--fallback", type=click.Choice(["python", "error"]), default="python", show_default=True, help="Fallback behavior when the Rust backend is unavailable.")
@click.option("--language", type=click.Choice(["auto", "python", "typescript"]), default="auto", show_default=True, help="Project language.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable diagnostics.")
@click.option("--output", type=click.Path(path_type=Path, dir_okay=False), help="Write JSON diagnostics to this file. Requires --json.")
@click.option("--subdir", "subdirectories", multiple=True, help="Limit parsing to a repository-relative subdirectory or file. Can be passed more than once.")
def diagnose_command(
    path: Path,
    backend: str,
    fallback: str,
    language: str,
    as_json: bool,
    output: Path | None,
    subdirectories: tuple[str, ...],
) -> None:
    """Parse a codebase and report timing, memory, and graph diagnostics."""
    if output is not None and not as_json:
        msg = "--output is only supported with --json"
        raise click.ClickException(msg)

    config = CodebaseConfig(
        graph_backend=GraphBackend(backend),
        rust_fallback=RustFallbackMode(fallback),
    )
    parsed_language = _parse_language(language)
    project = _project_for_parse(path, parsed_language, subdirectories)

    memory_samples = [_memory_sample("start")]
    parse_start = time.perf_counter()
    try:
        disabled_level = sys.maxsize if as_json else logging.INFO
        with _suppress_parse_logs(disabled_level):
            codebase = Codebase(projects=[project], config=config)
    except RuntimeError as error:
        raise click.ClickException(str(error)) from error
    parse_seconds = time.perf_counter() - parse_start
    memory_samples.append(_memory_sample("after_parse"))

    payload = _base_payload(codebase, path=path, backend=backend, elapsed_seconds=parse_seconds)
    memory_samples.append(_memory_sample("after_stats"))
    payload.update(
        {
            "schema_version": DIAGNOSTICS_JSON_SCHEMA_VERSION,
            "command": "diagnose",
            "parse_seconds": round(parse_seconds, 6),
            "memory": _memory_payload(memory_samples),
        }
    )

    if as_json:
        _write_json_payload(payload, output)
    else:
        _print_summary(payload)
