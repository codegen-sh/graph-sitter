import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from graph_sitter.cli.cli import main


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
