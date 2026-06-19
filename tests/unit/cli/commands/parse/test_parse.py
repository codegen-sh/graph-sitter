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


def test_uvx_dependency_constraints_are_declared():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    dependencies = set(pyproject["project"]["dependencies"])

    assert "mini-racer==0.12.4" in dependencies
    assert "tree-sitter>=0.23.1,<0.25" in dependencies
    assert "tree-sitter-python>=0.23.4,<0.24" in dependencies
    assert "tree-sitter-typescript>=0.23.2,<0.24" in dependencies
    assert "tree-sitter-javascript>=0.23.1,<0.24" in dependencies


def test_uvx_wheel_includes_import_path_codemod_base_package():
    hatch = tomllib.loads(Path("hatch.toml").read_text())

    assert hatch["build"]["packages"] == ["src/graph_sitter", "src/codemods"]


def test_uvx_wheel_builds_rust_extension_by_default():
    hatch = tomllib.loads(Path("hatch.toml").read_text())
    custom_hook = hatch["build"]["targets"]["wheel"]["hooks"]["custom"]

    assert custom_hook["enable-by-default"] is True
    assert custom_hook["path"] == "src/gsbuild/build.py"
    assert custom_hook["rust-extension"] is True
    assert custom_hook["rust-profile"] == "release"


def test_rust_extension_ci_exercises_wheel_uvx_smoke():
    workflow = Path(".github/workflows/rust-rewrite-extension.yml").read_text()
    smoke_script = Path("rust-rewrite/tools/check_wheel_rust_backend.sh").read_text()

    assert "rust-rewrite/tools/check_wheel_rust_backend.sh" in workflow
    assert "PYTHON_VERSION: ${{ matrix.python-version }}" in workflow
    assert "graph_sitter_py" in smoke_script
    assert "codemods/codemod.py" in smoke_script
    assert "run_graph_sitter --help" in smoke_script
    assert "run_graph_sitter parse" in smoke_script
    assert "run_graph_sitter transform" in smoke_script
    assert "--check" in smoke_script
    assert "--write" in smoke_script


def test_graph_sitter_version_uses_canonical_program_name():
    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0
    assert result.output.startswith("graph-sitter, version ")
    assert "codegen" not in result.output


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


def test_parse_command_summarizes_typescript_repo_as_json(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "util.ts").write_text("export function helper() {\n  return 1;\n}\n")
    (tmp_path / "src" / "app.ts").write_text("import { helper } from './util';\n\nexport function run() {\n  return helper();\n}\n")

    result = CliRunner().invoke(
        main,
        [
            "parse",
            str(tmp_path),
            "--language",
            "typescript",
            "--backend",
            "python",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["backend"] == "python"
    assert payload["language"] == "typescript"
    assert payload["files"] == 2
    assert payload["functions"] == 2
    assert payload["imports"] == 1
    assert payload["exports"] == 2
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
