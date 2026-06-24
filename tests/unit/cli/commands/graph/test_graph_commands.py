import json
import subprocess
import threading
from pathlib import Path

from click.testing import CliRunner

from graph_sitter.cli.cli import main
from graph_sitter.cli.commands.query.main import (
    QueryHTTPServer,
    QueryServerConfig,
    QueryServerHandler,
    QuerySession,
    _post_json,
)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test User"], check=True)


def _write_call_graph_repo(path: Path) -> Path:
    _init_repo(path)
    app = path / "app.py"
    app.write_text(
        """
def leaf():
    return 1


def helper():
    return leaf()


def entry():
    return helper()
""".lstrip()
    )
    return app


def test_inspect_command_reports_file_functions_and_calls(tmp_path):
    _write_call_graph_repo(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "inspect",
            "app.py",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
            "--format",
            "json",
            "--level",
            "calls",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["file"] == "app.py"
    assert payload["functions"] == 3

    functions = {function["name"]: function for function in payload["function_details"]}
    assert functions["leaf"]["line"] == 1
    assert functions["helper"]["uses"] == ["leaf"]
    assert functions["entry"]["uses"] == ["helper"]


def test_using_command_traces_outbound_call_graph(tmp_path):
    _write_call_graph_repo(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "using",
            "app.py:entry",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
            "--format",
            "json",
            "--depth",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    edges = {(edge["source"]["name"], edge["target"]["name"], edge["depth"]) for edge in payload["edges"]}
    assert ("entry", "helper", 1) in edges
    assert ("helper", "leaf", 2) in edges


def test_using_command_can_filter_to_resolved_deduped_edges(tmp_path):
    _write_call_graph_repo(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "using",
            "app.py:entry",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
            "--format",
            "json",
            "--depth",
            "2",
            "--resolved-only",
            "--dedupe",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["filters"]["resolved_only"] is True
    edges = {(edge["source"]["name"], edge["target"]["name"], edge["depth"]) for edge in payload["edges"]}
    assert edges == {("entry", "helper", 1), ("helper", "leaf", 2)}


def test_callgraph_command_defaults_to_clean_resolved_edges(tmp_path):
    _write_call_graph_repo(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "callgraph",
            "app.py.entry",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
            "--format",
            "json",
            "--depth",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["raw"] is False
    edges = {(edge["source"]["name"], edge["target"]["name"], edge["depth"]) for edge in payload["edges"]}
    assert edges == {("entry", "helper", 1), ("helper", "leaf", 2)}


def test_usages_command_traces_inbound_call_graph(tmp_path):
    _write_call_graph_repo(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "usages",
            "app.py:leaf",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
            "--format",
            "json",
            "--depth",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    edges = {(edge["source"]["name"], edge["target"]["name"], edge["depth"]) for edge in payload["edges"]}
    assert ("helper", "leaf", 1) in edges
    assert ("entry", "helper", 2) in edges


def test_symbols_command_lists_copyable_targets(tmp_path):
    _write_call_graph_repo(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "symbols",
            "help",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
            "--format",
            "json",
            "--kind",
            "function",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [symbol["target"] for symbol in payload["symbols"]] == ["app.py.helper"]


def test_query_command_reuses_one_parse_for_multiple_requests(tmp_path, monkeypatch):
    _write_call_graph_repo(tmp_path)
    from graph_sitter.cli.commands.query import main as query_main

    load_calls = []
    original_load_codebase = query_main.load_codebase

    def counting_load_codebase(*args, **kwargs):
        load_calls.append((args, kwargs))
        return original_load_codebase(*args, **kwargs)

    monkeypatch.setattr(query_main, "load_codebase", counting_load_codebase)
    requests = "\n".join(
        [
            json.dumps({"id": "symbols", "op": "symbols", "query": "help", "kind": "function"}),
            json.dumps({"id": "using", "op": "using", "target": "app.py:entry", "depth": 2}),
            json.dumps({"id": "inspect", "op": "inspect", "file": "app.py", "level": "calls"}),
            json.dumps({"id": "exit", "op": "exit"}),
        ]
    )

    result = CliRunner().invoke(
        main,
        [
            "query",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
        ],
        input=f"{requests}\n",
    )

    assert result.exit_code == 0, result.output
    assert len(load_calls) == 1
    payloads = [json.loads(line) for line in result.output.splitlines()]
    assert payloads[0]["event"] == "ready"
    assert payloads[0]["summary"]["files"] == 1

    responses = {payload["id"]: payload for payload in payloads[1:]}
    assert responses["symbols"]["ok"] is True
    assert [symbol["target"] for symbol in responses["symbols"]["result"]["symbols"]] == ["app.py.helper"]

    edges = {(edge["source"]["name"], edge["target"]["name"], edge["depth"]) for edge in responses["using"]["result"]["edges"]}
    assert ("entry", "helper", 1) in edges
    assert ("helper", "leaf", 2) in edges

    functions = {function["name"]: function for function in responses["inspect"]["result"]["function_details"]}
    assert functions["entry"]["uses"] == ["helper"]
    assert responses["exit"]["event"] == "exit"


def test_query_command_reports_request_errors_as_jsonl(tmp_path):
    _write_call_graph_repo(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "query",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
        ],
        input=json.dumps({"id": "missing-target", "op": "callgraph"}) + "\n",
    )

    assert result.exit_code == 0, result.output
    payloads = [json.loads(line) for line in result.output.splitlines()]
    assert payloads[0]["event"] == "ready"
    assert payloads[1]["id"] == "missing-target"
    assert payloads[1]["ok"] is False
    assert payloads[1]["error"]["message"] == "Missing required field: target"


def test_query_session_reports_stale_and_reload_after_edit(tmp_path):
    app = _write_call_graph_repo(tmp_path)
    session = QuerySession.load(path=tmp_path, backend="python", fallback="python", language="python", subdirectories=())

    assert session.status_payload()["stale"] is False
    app.write_text(app.read_text() + "\n\ndef new_leaf():\n    return leaf()\n")

    assert session.status_payload()["stale"] is True
    before_reload = session.handle_request({"id": "before", "op": "symbols", "query": "new_leaf", "kind": "function"})
    assert before_reload["result"]["symbols"] == []

    reload_response = session.handle_request({"id": "reload", "op": "reload"})
    assert reload_response["ok"] is True
    assert reload_response["result"]["stale"] is False

    after_reload = session.handle_request({"id": "after", "op": "symbols", "query": "new_leaf", "kind": "function"})
    assert [symbol["target"] for symbol in after_reload["result"]["symbols"]] == ["app.py.new_leaf"]


def test_query_http_server_can_reload_if_stale(tmp_path):
    app = _write_call_graph_repo(tmp_path)
    config = QueryServerConfig(path=tmp_path, backend="python", fallback="python", language="python", subdirectories=())
    session = QuerySession.load(path=tmp_path, backend="python", fallback="python", language="python", subdirectories=())
    server = QueryHTTPServer(("127.0.0.1", 0), QueryServerHandler, session=session, config=config, state_file=tmp_path / "server.json")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        state = server.state_payload()
        app.write_text(app.read_text() + "\n\ndef new_leaf():\n    return leaf()\n")
        response = _post_json(state, "/query", {"id": "new", "op": "symbols", "query": "new_leaf", "kind": "function", "reload_if_stale": True})
        assert response["ok"] is True
        assert [symbol["target"] for symbol in response["result"]["symbols"]] == ["app.py.new_leaf"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_rename_command_applies_function_rename_when_write_is_passed(tmp_path):
    app = _write_call_graph_repo(tmp_path)

    dry_run = CliRunner().invoke(
        main,
        [
            "rename",
            "app.py:leaf",
            str(tmp_path),
            "--to",
            "branch",
            "--language",
            "python",
            "--backend",
            "python",
            "--format",
            "json",
        ],
    )

    assert dry_run.exit_code == 0, dry_run.output
    dry_run_payload = json.loads(dry_run.output)
    assert dry_run_payload["applied"] is False
    assert dry_run_payload["affected_files"] == ["app.py"]
    assert "def leaf()" in app.read_text()

    result = CliRunner().invoke(
        main,
        [
            "rename",
            "app.py:leaf",
            str(tmp_path),
            "--to",
            "branch",
            "--language",
            "python",
            "--backend",
            "python",
            "--format",
            "json",
            "--write",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] is True
    source = app.read_text()
    assert "def branch():" in source
    assert "return branch()" in source
