import subprocess
from pathlib import Path

from click.testing import CliRunner

from graph_sitter.cli.cli import main


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test User"], check=True)


def _commit_all(path: Path, message: str = "initial") -> None:
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", message], check=True, capture_output=True)


def test_run_command_accepts_path_and_typed_arguments_without_active_session(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("def target():\n    return 1\n")
    codemod_dir = tmp_path / ".codegen" / "codemods" / "rename"
    codemod_dir.mkdir(parents=True)
    (codemod_dir / "rename.py").write_text(
        """
import graph_sitter
from pydantic import BaseModel


class RenameArgs(BaseModel):
    new_name: str


@graph_sitter.function("rename-target")
def run(codebase, arguments: RenameArgs):
    function = codebase.get_function("target")
    function.rename(arguments.new_name)
    codebase.commit()
""".lstrip()
    )
    _commit_all(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "run",
            "rename-target",
            str(tmp_path),
            "--arguments",
            '{"new_name": "renamed"}',
            "--backend",
            "python",
            "--write",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "def renamed()" in (tmp_path / "app.py").read_text()
    assert "Changes have been applied" in result.output


def test_run_command_check_reports_diff_without_writing_target_repo(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("def target():\n    return 1\n")
    codemod_dir = tmp_path / ".codegen" / "codemods" / "rename"
    codemod_dir.mkdir(parents=True)
    (codemod_dir / "rename.py").write_text(
        """
import graph_sitter


@graph_sitter.function("rename-target")
def run(codebase):
    function = codebase.get_function("target")
    function.rename("renamed")
    codebase.commit()
""".lstrip()
    )
    _commit_all(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "run",
            "rename-target",
            str(tmp_path),
            "--check",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "Codemod would produce changes" in result.output
    assert "target -> renamed" in result.output
    assert (tmp_path / "app.py").read_text() == "def target():\n    return 1\n"


def test_run_command_rejects_check_and_write_together(tmp_path):
    result = CliRunner().invoke(main, ["run", "anything", str(tmp_path), "--check", "--write"])

    assert result.exit_code != 0
    assert "--check and --write cannot be used together" in result.output


def test_run_command_rejects_arguments_for_codemod_without_arguments_parameter(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("def target():\n    return 1\n")
    codemod_dir = tmp_path / ".codegen" / "codemods" / "noop"
    codemod_dir.mkdir(parents=True)
    (codemod_dir / "noop.py").write_text(
        """
import graph_sitter


@graph_sitter.function("noop")
def run(codebase):
    return None
""".lstrip()
    )
    _commit_all(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "run",
            "noop",
            str(tmp_path),
            "--arguments",
            '{"unused": true}',
        ],
    )

    assert result.exit_code != 0
    assert "does not accept an arguments parameter" in result.output
