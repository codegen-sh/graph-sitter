import json
import subprocess
import sys
import tomllib
from pathlib import Path

from click.testing import CliRunner

from graph_sitter.cli.cli import main


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test User"], check=True)


def test_graph_sitter_console_script_alias_is_declared():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    scripts = pyproject["project"]["scripts"]
    assert scripts["gs"] == "graph_sitter.cli.cli:main"
    assert scripts["graph-sitter"] == "graph_sitter.cli.cli:main"


def test_parse_command_summarizes_python_repo_as_json(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("import os\n\nclass Service:\n    pass\n\ndef run():\n    return os.getcwd()\n")

    result = CliRunner().invoke(
        main,
        [
            "parse",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["backend_requested"] == "python"
    assert payload["backend"] == "python"
    assert payload["language"] == "python"
    assert payload["files"] == 1
    assert payload["classes"] == 1
    assert payload["functions"] == 1
    assert payload["imports"] == 1
    assert payload["symbols"] == 2
    assert payload["exports"] == 0
    assert payload["dependencies"] >= 1


def test_parse_command_json_stdout_is_machine_readable(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("import os\n\ndef run():\n    return os.getcwd()\n")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "graph_sitter.cli.cli",
            "parse",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.startswith("{")
    assert json.loads(result.stdout)["backend"] == "python"


def test_parse_command_rust_backend_missing_extension_fails_cleanly(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("def run():\n    return 1\n")

    result = CliRunner().invoke(
        main,
        [
            "parse",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "rust",
            "--fallback",
            "error",
            "--format",
            "json",
        ],
    )

    if result.exit_code == 0:
        payload = json.loads(result.output)
        assert payload["backend"] == "rust"
        assert payload["files"] == 1
    else:
        assert "Rust graph backend" in result.output
