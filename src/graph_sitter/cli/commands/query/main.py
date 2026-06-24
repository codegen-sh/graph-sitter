import json
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import rich_click as click

from graph_sitter.cli.commands.graph.common import (
    GRAPH_COMMAND_JSON_SCHEMA_VERSION,
    all_symbol_records,
    filter_edge_records,
    graph_options,
    load_codebase,
    resolve_file,
    resolve_target,
    trace_edges,
)
from graph_sitter.cli.commands.inspect.main import _file_payload
from graph_sitter.cli.commands.parse.main import _base_payload
from graph_sitter.core.codebase import Codebase

QUERY_JSON_SCHEMA_VERSION = 1
DEFAULT_QUERY_SERVER_HOST = "127.0.0.1"
DEFAULT_QUERY_SERVER_START_TIMEOUT_SECONDS = 300.0
QUERY_SERVER_STATE_VERSION = 1


@click.command(name="query")
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@graph_options
def query_command(path: Path, backend: str, fallback: str, language: str, subdirectories: tuple[str, ...]) -> None:
    """Parse once, then answer JSONL graph queries from stdin."""
    session = QuerySession.load(path=path, backend=backend, fallback=fallback, language=language, subdirectories=subdirectories)
    _emit(
        {
            "schema_version": QUERY_JSON_SCHEMA_VERSION,
            "event": "ready",
            "ok": True,
            "summary": session.summary_payload(),
        }
    )
    for response in session.run_lines(sys.stdin):
        _emit(response)
        if response.get("event") == "exit":
            break


@click.group(name="query-server")
def query_server_command() -> None:
    """Manage a background in-memory graph query server."""


@query_server_command.command(name="start")
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@click.option("--host", default=DEFAULT_QUERY_SERVER_HOST, show_default=True, help="Host for the local query server.")
@click.option("--port", type=int, default=0, show_default=True, help="Port for the local query server. Use 0 to pick a free port.")
@click.option("--timeout", type=float, default=DEFAULT_QUERY_SERVER_START_TIMEOUT_SECONDS, show_default=True, help="Seconds to wait for initial parse and server readiness.")
@click.option("--force", is_flag=True, help="Stop an existing server for the same repo/backend key before starting.")
@graph_options
def query_server_start_command(
    path: Path,
    host: str,
    port: int,
    timeout: float,
    force: bool,
    backend: str,
    fallback: str,
    language: str,
    subdirectories: tuple[str, ...],
) -> None:
    """Start a background server that keeps one parsed graph in memory."""
    config = QueryServerConfig(path=path, backend=backend, fallback=fallback, language=language, subdirectories=subdirectories)
    state_file = _state_file_for(config)
    existing_state = _load_state(state_file)
    if existing_state is not None and _server_is_healthy(existing_state):
        if not force:
            _emit(
                {
                    "schema_version": QUERY_JSON_SCHEMA_VERSION,
                    "ok": True,
                    "event": "already_running",
                    "server": existing_state,
                }
            )
            return
        _request_shutdown(existing_state)
        if not _wait_for_shutdown(existing_state, timeout=10.0):
            msg = f"Existing query server for {config.path} did not stop after shutdown request"
            raise click.ClickException(msg)
        _remove_state_file(state_file)

    state_file.parent.mkdir(parents=True, exist_ok=True)
    if port == 0:
        port = _free_port(host)
    log_file = state_file.with_suffix(".log")
    cmd = [
        sys.executable,
        "-m",
        "graph_sitter.cli.cli",
        "query-server",
        "serve",
        str(path.resolve()),
        "--host",
        host,
        "--port",
        str(port),
        "--state-file",
        str(state_file),
        "--backend",
        backend,
        "--fallback",
        fallback,
        "--language",
        language,
    ]
    for subdirectory in subdirectories:
        cmd.extend(["--subdir", subdirectory])

    with log_file.open("a") as log:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(path.resolve()),
        )

    try:
        state = _wait_for_server(state_file, process, timeout=timeout)
    except Exception:
        if process.poll() is None:
            process.terminate()
        raise
    _emit(
        {
            "schema_version": QUERY_JSON_SCHEMA_VERSION,
            "ok": True,
            "event": "started",
            "server": state,
        }
    )


@query_server_command.command(name="serve", hidden=True)
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@click.option("--host", default=DEFAULT_QUERY_SERVER_HOST, show_default=True, help="Host for the local query server.")
@click.option("--port", type=int, required=True, help="Port for the local query server.")
@click.option("--state-file", type=click.Path(path_type=Path, dir_okay=False), required=True, help="State file to write once ready.")
@graph_options
def query_server_serve_command(path: Path, host: str, port: int, state_file: Path, backend: str, fallback: str, language: str, subdirectories: tuple[str, ...]) -> None:
    """Run the in-memory query server in the foreground."""
    config = QueryServerConfig(path=path, backend=backend, fallback=fallback, language=language, subdirectories=subdirectories)
    session = QuerySession.load(path=path, backend=backend, fallback=fallback, language=language, subdirectories=subdirectories)
    httpd = QueryHTTPServer((host, port), QueryServerHandler, session=session, config=config, state_file=state_file)
    httpd.write_state()
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        _remove_state_file(state_file)


@query_server_command.command(name="run")
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@click.option("--request", "request_text", type=str, help="JSON query request. Reads JSONL from stdin when omitted.")
@click.option("--reload-if-stale/--no-reload-if-stale", default=True, show_default=True, help="Reload the server graph before the query when the repo changed since parse.")
@graph_options
def query_server_run_command(
    path: Path,
    request_text: str | None,
    reload_if_stale: bool,
    backend: str,
    fallback: str,
    language: str,
    subdirectories: tuple[str, ...],
) -> None:
    """Send one or more JSON queries to a background query server."""
    config = QueryServerConfig(path=path, backend=backend, fallback=fallback, language=language, subdirectories=subdirectories)
    state = _require_running_state(config)
    raw_requests = [request_text] if request_text is not None else [line for line in sys.stdin.read().splitlines() if line.strip()]
    if not raw_requests:
        msg = "Pass --request or provide JSONL requests on stdin"
        raise click.ClickException(msg)

    for raw_request in raw_requests:
        try:
            payload = json.loads(raw_request)
        except json.JSONDecodeError as error:
            msg = f"Invalid JSON query request: {error.msg}"
            raise click.ClickException(msg) from error
        if not isinstance(payload, dict):
            msg = "Query request must be a JSON object"
            raise click.ClickException(msg)
        if reload_if_stale:
            payload.setdefault("reload_if_stale", True)
        _emit(_post_json(state, "/query", payload))


@query_server_command.command(name="status")
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@graph_options
def query_server_status_command(path: Path, backend: str, fallback: str, language: str, subdirectories: tuple[str, ...]) -> None:
    """Report server health, parse summary, and stale state."""
    config = QueryServerConfig(path=path, backend=backend, fallback=fallback, language=language, subdirectories=subdirectories)
    state = _require_running_state(config)
    _emit(_get_json(state, "/health"))


@query_server_command.command(name="reload")
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@graph_options
def query_server_reload_command(path: Path, backend: str, fallback: str, language: str, subdirectories: tuple[str, ...]) -> None:
    """Reload the server graph from the current filesystem state."""
    config = QueryServerConfig(path=path, backend=backend, fallback=fallback, language=language, subdirectories=subdirectories)
    state = _require_running_state(config)
    _emit(_post_json(state, "/query", {"op": "reload"}))


@query_server_command.command(name="stop")
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@graph_options
def query_server_stop_command(path: Path, backend: str, fallback: str, language: str, subdirectories: tuple[str, ...]) -> None:
    """Stop the background query server for this repo/backend key."""
    config = QueryServerConfig(path=path, backend=backend, fallback=fallback, language=language, subdirectories=subdirectories)
    match = _find_running_state(config)
    state_file = match[0] if match is not None else _state_file_for(config)
    state = match[1] if match is not None else _load_state(state_file)
    if state is None:
        _emit({"schema_version": QUERY_JSON_SCHEMA_VERSION, "ok": True, "event": "not_running"})
        return
    if _server_is_healthy(state):
        _request_shutdown(state)
    _remove_state_file(state_file)
    _emit({"schema_version": QUERY_JSON_SCHEMA_VERSION, "ok": True, "event": "stopped", "server": state})


class QuerySession:
    def __init__(
        self,
        *,
        codebase: Codebase,
        path: Path,
        backend: str,
        fallback: str,
        language: str,
        subdirectories: tuple[str, ...],
        elapsed_seconds: float,
    ) -> None:
        self.codebase = codebase
        self.path = path.resolve()
        self.backend = backend
        self.fallback = fallback
        self.language = language
        self.subdirectories = subdirectories
        self.elapsed_seconds = elapsed_seconds
        self.loaded_at = time.time()
        self._lock = threading.RLock()
        self.snapshot = _repo_snapshot(self.path)

    @classmethod
    def load(cls, *, path: Path, backend: str, fallback: str, language: str, subdirectories: tuple[str, ...]) -> "QuerySession":
        start = time.perf_counter()
        codebase = load_codebase(path, backend, fallback, language, subdirectories, quiet=True)
        elapsed_seconds = time.perf_counter() - start
        return cls(codebase=codebase, path=path, backend=backend, fallback=fallback, language=language, subdirectories=subdirectories, elapsed_seconds=elapsed_seconds)

    def summary_payload(self) -> dict[str, Any]:
        with self._lock:
            return _base_payload(self.codebase, path=self.path, backend=self.backend, elapsed_seconds=self.elapsed_seconds)

    def status_payload(self) -> dict[str, Any]:
        with self._lock:
            current_snapshot = _repo_snapshot(self.path)
            return {
                "schema_version": QUERY_JSON_SCHEMA_VERSION,
                "pid": os.getpid(),
                "path": str(self.path),
                "backend": self.backend,
                "fallback": self.fallback,
                "language": self.language,
                "subdirectories": list(self.subdirectories),
                "loaded_at": self.loaded_at,
                "stale": current_snapshot != self.snapshot,
                "snapshot": self.snapshot,
                "current_snapshot": current_snapshot,
                "summary": self.summary_payload(),
            }

    def reload(self) -> dict[str, Any]:
        with self._lock:
            replacement = self.load(path=self.path, backend=self.backend, fallback=self.fallback, language=self.language, subdirectories=self.subdirectories)
            self.codebase = replacement.codebase
            self.elapsed_seconds = replacement.elapsed_seconds
            self.loaded_at = replacement.loaded_at
            self.snapshot = replacement.snapshot
            return self.status_payload()

    def run_lines(self, lines: Iterable[str]) -> Iterable[dict[str, Any]]:
        for line_number, line in enumerate(lines, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                request = json.loads(raw)
                if not isinstance(request, dict):
                    msg = "Query request must be a JSON object"
                    raise ValueError(msg)
                yield self.handle_request(request)
            except Exception as error:
                yield _error_response(None, None, error, line_number=line_number)

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            request_id = request.get("id")
            op: str | None = request.get("op") if isinstance(request.get("op"), str) else None
            try:
                op = _string_field(request, "op", required=True)
                if op in {"exit", "quit"}:
                    return _ok_response(request_id, op, {"bye": True}, event="exit")
                if _bool_field(request, "reload_if_stale", default=False) and op not in {"status", "reload"} and self.status_payload()["stale"]:
                    self.reload()
                return _ok_response(request_id, op, self._dispatch(request, op))
            except Exception as error:
                return _error_response(request_id, op, error)

    def _dispatch(self, request: dict[str, Any], op: str) -> dict[str, Any]:
        if op in {"summary", "parse"}:
            return self.summary_payload()
        if op == "status":
            return self.status_payload()
        if op == "reload":
            return self.reload()
        if op == "symbols":
            return self._symbols(request)
        if op == "inspect":
            return self._inspect(request)
        if op == "callgraph":
            return self._callgraph(request)
        if op in {"using", "usages"}:
            return self._trace(request, direction="outbound" if op == "using" else "inbound")
        msg = f"Unsupported query op: {op}"
        raise ValueError(msg)

    def _symbols(self, request: dict[str, Any]) -> dict[str, Any]:
        query = _optional_string_field(request, "query")
        kind = _choice_field(request, "kind", {"all", "function", "class", "symbol"}, default="all")
        max_results = _int_field(request, "max_results", default=200, minimum=1)
        return {
            "schema_version": GRAPH_COMMAND_JSON_SCHEMA_VERSION,
            "query": query,
            "kind": kind,
            "max_results": max_results,
            "symbols": all_symbol_records(self.codebase, query=query, kind=kind, max_results=max_results),
        }

    def _inspect(self, request: dict[str, Any]) -> dict[str, Any]:
        file = _string_field(request, "file", required=True)
        level = _choice_field(request, "level", {"summary", "functions", "calls", "full"}, default="functions")
        max_functions = _int_field(request, "max_functions", default=200, minimum=1)
        max_calls = _int_field(request, "max_calls", default=20, minimum=0)
        source_file = resolve_file(self.codebase, file)
        return _file_payload(source_file, level=level, max_functions=max_functions, max_calls=max_calls)

    def _callgraph(self, request: dict[str, Any]) -> dict[str, Any]:
        target = _string_field(request, "target", required=True)
        direction = _choice_field(request, "direction", {"outbound", "inbound"}, default="outbound")
        depth = _int_field(request, "depth", default=2, minimum=0)
        max_results = _int_field(request, "max_results", default=200, minimum=1)
        raw = _bool_field(request, "raw", default=False)
        resolved = resolve_target(self.codebase, target)
        trace_limit = max_results if raw else max_results * 5
        edges = trace_edges(resolved.symbol, direction=direction, depth=depth, max_results=trace_limit)
        if not raw:
            edges = filter_edge_records(edges, resolved_only=True, local_only=True, hide_runtime=True, dedupe=True)
        return {
            "schema_version": GRAPH_COMMAND_JSON_SCHEMA_VERSION,
            "direction": direction,
            "target": target,
            "depth": depth,
            "max_results": max_results,
            "raw": raw,
            "edges": edges[:max_results],
        }

    def _trace(self, request: dict[str, Any], *, direction: str) -> dict[str, Any]:
        target = _string_field(request, "target", required=True)
        depth = _int_field(request, "depth", default=1, minimum=0)
        max_results = _int_field(request, "max_results", default=200, minimum=1)
        resolved_only = _bool_field(request, "resolved_only", default=False)
        local_only = _bool_field(request, "local_only", default=False)
        hide_runtime = _bool_field(request, "hide_runtime", default=False)
        dedupe = _bool_field(request, "dedupe", default=False)
        resolved = resolve_target(self.codebase, target)
        should_overfetch = resolved_only or local_only or hide_runtime or dedupe
        trace_limit = max_results * 5 if should_overfetch else max_results
        edges = trace_edges(resolved.symbol, direction=direction, depth=depth, max_results=trace_limit)
        edges = filter_edge_records(edges, resolved_only=resolved_only, local_only=local_only, hide_runtime=hide_runtime, dedupe=dedupe)
        return {
            "schema_version": GRAPH_COMMAND_JSON_SCHEMA_VERSION,
            "direction": direction,
            "target": target,
            "depth": depth,
            "max_results": max_results,
            "filters": {
                "resolved_only": resolved_only,
                "local_only": local_only,
                "hide_runtime": hide_runtime,
                "dedupe": dedupe,
            },
            "edges": edges[:max_results],
        }


def _ok_response(request_id: Any, op: str, result: dict[str, Any], *, event: str | None = None) -> dict[str, Any]:
    payload = {
        "schema_version": QUERY_JSON_SCHEMA_VERSION,
        "id": request_id,
        "op": op,
        "ok": True,
        "result": result,
    }
    if event is not None:
        payload["event"] = event
    return payload


def _error_response(request_id: Any, op: str | None, error: Exception, *, line_number: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": QUERY_JSON_SCHEMA_VERSION,
        "id": request_id,
        "op": op,
        "ok": False,
        "error": {
            "type": type(error).__name__,
            "message": str(error),
        },
    }
    if line_number is not None:
        payload["line"] = line_number
    return payload


def _emit(payload: dict[str, Any]) -> None:
    click.echo(json.dumps(payload, sort_keys=True))


def _string_field(request: dict[str, Any], name: str, *, required: bool = False, default: str | None = None) -> str:
    value = request.get(name, default)
    if value is None:
        if required:
            msg = f"Missing required field: {name}"
            raise ValueError(msg)
        return ""
    if not isinstance(value, str):
        msg = f"{name} must be a string"
        raise ValueError(msg)
    return value


class QueryServerConfig:
    def __init__(self, *, path: Path, backend: str, fallback: str, language: str, subdirectories: tuple[str, ...]) -> None:
        self.path = path.resolve()
        self.backend = backend
        self.fallback = fallback
        self.language = language
        self.subdirectories = tuple(subdirectories)

    def key_payload(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "backend": self.backend,
            "fallback": self.fallback,
            "language": self.language,
            "subdirectories": list(self.subdirectories),
        }


class QueryHTTPServer(ThreadingHTTPServer):
    session: QuerySession
    config: QueryServerConfig
    state_file: Path

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        session: QuerySession,
        config: QueryServerConfig,
        state_file: Path,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.session = session
        self.config = config
        self.state_file = state_file

    def state_payload(self) -> dict[str, Any]:
        host = str(self.server_address[0])
        port = int(self.server_address[1])
        return {
            "schema_version": QUERY_SERVER_STATE_VERSION,
            "host": host,
            "port": port,
            "pid": os.getpid(),
            "state_file": str(self.state_file),
            "config": self.config.key_payload(),
            "summary": self.session.summary_payload(),
        }

    def write_state(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.state_payload(), sort_keys=True) + "\n")


class QueryServerHandler(BaseHTTPRequestHandler):
    server: QueryHTTPServer

    def do_GET(self) -> None:
        if self.path != "/health":
            self._write_json({"ok": False, "error": {"message": "Not found"}}, status=404)
            return
        self._write_json(
            {
                "schema_version": QUERY_JSON_SCHEMA_VERSION,
                "ok": True,
                "server": self.server.state_payload(),
                "status": self.server.session.status_payload(),
            }
        )

    def do_POST(self) -> None:
        if self.path == "/query":
            self._handle_query()
            return
        if self.path == "/shutdown":
            self._write_json({"schema_version": QUERY_JSON_SCHEMA_VERSION, "ok": True, "event": "stopping"})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self._write_json({"ok": False, "error": {"message": "Not found"}}, status=404)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle_query(self) -> None:
        try:
            payload = self._read_json()
            if not isinstance(payload, dict):
                msg = "Query request must be a JSON object"
                raise ValueError(msg)
            response = self.server.session.handle_request(payload)
        except Exception as error:
            response = _error_response(None, None, error)
        self._write_json(response)

    def _read_json(self) -> Any:
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _write_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _state_file_for(config: QueryServerConfig) -> Path:
    import hashlib

    digest = hashlib.sha256(json.dumps(config.key_payload(), sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return _state_dir() / f"{digest}.json"


def _state_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "graph-sitter" / "query-servers"


def _load_state(state_file: Path) -> dict[str, Any] | None:
    try:
        return json.loads(state_file.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _remove_state_file(state_file: Path) -> None:
    try:
        state_file.unlink()
    except FileNotFoundError:
        return


def _require_running_state(config: QueryServerConfig) -> dict[str, Any]:
    match = _find_running_state(config)
    if match is None:
        msg = f"No query server is running for {config.path}. Start one with `graph-sitter query-server start {config.path}`."
        raise click.ClickException(msg)
    state_file, state = match
    if not _server_is_healthy(state):
        _remove_state_file(state_file)
        msg = f"Recorded query server is not responding for {config.path}. Restart it with `graph-sitter query-server start {config.path}`."
        raise click.ClickException(msg)
    return state


def _find_running_state(config: QueryServerConfig) -> tuple[Path, dict[str, Any]] | None:
    exact_state_file = _state_file_for(config)
    exact_state = _load_state(exact_state_file)
    if exact_state is not None:
        if _server_is_healthy(exact_state):
            return exact_state_file, exact_state
        _remove_state_file(exact_state_file)

    matches: list[tuple[Path, dict[str, Any]]] = []
    for state_file in _state_dir().glob("*.json"):
        if state_file == exact_state_file:
            continue
        state = _load_state(state_file)
        if state is None:
            continue
        state_config = state.get("config") or {}
        if state_config.get("path") != str(config.path):
            continue
        if _server_is_healthy(state):
            matches.append((state_file, state))
        else:
            _remove_state_file(state_file)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        choices = ", ".join(
            f"backend={match[1].get('config', {}).get('backend')} language={match[1].get('config', {}).get('language')} subdirs={match[1].get('config', {}).get('subdirectories')}" for match in matches
        )
        msg = f"Multiple query servers are running for {config.path}. Specify backend/language/subdir. Matches: {choices}"
        raise click.ClickException(msg)
    return None


def _server_is_healthy(state: dict[str, Any], *, timeout: float = 1.0) -> bool:
    try:
        _get_json(state, "/health", timeout=timeout)
    except Exception:
        return False
    return True


def _wait_for_shutdown(state: dict[str, Any], *, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _server_is_healthy(state, timeout=0.2):
            return True
        time.sleep(0.1)
    return False


def _wait_for_server(state_file: Path, process: subprocess.Popen, *, timeout: float) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            log_tail = _log_tail(state_file.with_suffix(".log"))
            msg = f"Query server exited before becoming ready. Log:\n{log_tail}"
            raise click.ClickException(msg)
        state = _load_state(state_file)
        if state is not None and _server_is_healthy(state):
            return state
        time.sleep(0.2)
    msg = f"Timed out waiting for query server to parse and start after {timeout:.1f}s"
    raise click.ClickException(msg)


def _log_tail(log_file: Path, *, max_bytes: int = 4000) -> str:
    try:
        with log_file.open("rb") as file:
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(max(0, size - max_bytes))
            return file.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _server_url(state: dict[str, Any], path: str) -> str:
    return f"http://{state['host']}:{state['port']}{path}"


def _get_json(state: dict[str, Any], path: str, *, timeout: float = 5.0) -> dict[str, Any]:
    with urlopen(_server_url(state, path), timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(state: dict[str, Any], path: str, payload: dict[str, Any], *, timeout: float = 300.0) -> dict[str, Any]:
    request = Request(
        _server_url(state, path),
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as error:
        msg = f"Could not reach query server: {error}"
        raise click.ClickException(msg) from error


def _request_shutdown(state: dict[str, Any]) -> None:
    try:
        _post_json(state, "/shutdown", {}, timeout=5.0)
    except Exception:
        return


def _repo_snapshot(path: Path) -> dict[str, Any]:
    git_head = _run_git(path, "rev-parse", "HEAD")
    git_status = _run_git(path, "status", "--porcelain=v1", "--untracked-files=all")
    if git_status is None:
        stat = path.stat()
        return {
            "kind": "path",
            "mtime_ns": stat.st_mtime_ns,
        }

    import hashlib

    changed_paths = _git_status_paths(git_status)
    return {
        "kind": "git",
        "head": git_head.strip() if git_head is not None else None,
        "dirty": bool(git_status.strip()),
        "changed_files": len(changed_paths),
        "status_hash": hashlib.sha256(git_status.encode("utf-8")).hexdigest(),
        "changed_paths_hash": _changed_paths_hash(path, changed_paths),
    }


def _run_git(path: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", "-C", str(path), *args], check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _git_status_paths(git_status: str) -> list[str]:
    paths: list[str] = []
    for line in git_status.splitlines():
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            _, path = path.rsplit(" -> ", 1)
        if path:
            paths.append(path)
    return paths


def _changed_paths_hash(repo_path: Path, paths: list[str]) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(paths):
        absolute = repo_path / path
        digest.update(path.encode("utf-8"))
        try:
            stat = absolute.stat()
        except OSError:
            digest.update(b":missing")
            continue
        digest.update(f":{stat.st_size}:{stat.st_mtime_ns}".encode())
    return digest.hexdigest()


def _optional_string_field(request: dict[str, Any], name: str) -> str | None:
    value = request.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"{name} must be a string"
        raise ValueError(msg)
    return value


def _choice_field(request: dict[str, Any], name: str, choices: set[str], *, default: str) -> str:
    value = _string_field(request, name, default=default)
    if value not in choices:
        msg = f"{name} must be one of: {', '.join(sorted(choices))}"
        raise ValueError(msg)
    return value


def _int_field(request: dict[str, Any], name: str, *, default: int, minimum: int) -> int:
    value = request.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool):
        msg = f"{name} must be an integer"
        raise ValueError(msg)
    if value < minimum:
        msg = f"{name} must be >= {minimum}"
        raise ValueError(msg)
    return value


def _bool_field(request: dict[str, Any], name: str, *, default: bool) -> bool:
    value = request.get(name, default)
    if not isinstance(value, bool):
        msg = f"{name} must be a boolean"
        raise ValueError(msg)
    return value
