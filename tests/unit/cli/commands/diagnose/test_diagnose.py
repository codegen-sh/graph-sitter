import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from graph_sitter.cli.cli import main


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test User"], check=True)


def test_diagnose_command_reports_parse_time_memory_and_file_count_as_json(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("import os\n\ndef run():\n    return os.getcwd()\n")

    result = CliRunner().invoke(
        main,
        [
            "diagnose",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["command"] == "diagnose"
    assert payload["backend_requested"] == "python"
    assert payload["backend"] == "python"
    assert payload["language"] == "python"
    assert payload["files"] == 1
    assert payload["functions"] == 1
    assert payload["parse_seconds"] >= 0
    assert payload["elapsed_seconds"] == payload["parse_seconds"]
    assert payload["memory"]["rss_start_mb"] > 0
    assert payload["memory"]["rss_after_parse_mb"] > 0
    assert payload["memory"]["peak_rss_mb"] >= payload["memory"]["rss_after_parse_mb"]
    assert [sample["label"] for sample in payload["memory"]["samples"]] == ["start", "after_parse", "after_stats"]


def test_diagnose_command_prints_human_summary(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("def run():\n    return 1\n")

    result = CliRunner().invoke(
        main,
        [
            "diagnose",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Graph-sitter diagnostics" in result.output
    assert "Parse time" in result.output
    assert "Memory after parse" in result.output
    assert "Peak memory" in result.output
    assert "Files" in result.output
    assert "1" in result.output


def test_diagnose_command_writes_json_output_file(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("def run():\n    return 1\n")
    output_path = tmp_path / "diagnostics.json"

    result = CliRunner().invoke(
        main,
        [
            "diagnose",
            str(tmp_path),
            "--language",
            "python",
            "--backend",
            "python",
            "--json",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == ""
    payload = json.loads(output_path.read_text())
    assert payload["command"] == "diagnose"
    assert payload["files"] == 1
    assert payload["memory"]["rss_after_parse_mb"] > 0


def test_diagnose_command_rejects_output_without_json(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("def run():\n    return 1\n")

    result = CliRunner().invoke(
        main,
        [
            "diagnose",
            str(tmp_path),
            "--output",
            str(tmp_path / "diagnostics.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output" in result.output
    assert "--json" in result.output
