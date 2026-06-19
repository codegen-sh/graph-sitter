import subprocess
from pathlib import Path

from click.testing import CliRunner
from click.utils import strip_ansi

from graph_sitter.cli.cli import main


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test User"], check=True)


def _commit_all(path: Path, message: str = "initial") -> None:
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", message], check=True, capture_output=True)


def test_transform_function_check_reports_diff_without_writing_target_repo(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("def target():\n    return 1\n")
    transform_file = tmp_path / "rename_transform.py"
    transform_file.write_text(
        """
from pydantic import BaseModel


class RenameArgs(BaseModel):
    new_name: str


def rename(codebase, arguments: RenameArgs):
    function = codebase.get_function("target")
    function.rename(arguments.new_name)
    codebase.commit()
""".lstrip()
    )
    _commit_all(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "transform",
            f"{transform_file}:rename",
            str(tmp_path),
            "--arguments",
            '{"new_name": "renamed"}',
            "--check",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "Codemod would produce changes" in result.output
    output = strip_ansi(result.output)
    assert "target -> renamed" in output or ("-def target():" in output and "+def renamed():" in output)
    assert (tmp_path / "app.py").read_text() == "def target():\n    return 1\n"


def test_transform_codemod_subclass_write_modifies_target_repo(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("def target():\n    return 1\n")
    transform_file = tmp_path / "rename_class_transform.py"
    transform_file.write_text(
        """
from codemods.codemod import Codemod


class RenameCodemod(Codemod):
    def execute(self, codebase):
        function = codebase.get_function("target")
        function.rename("renamed")
        codebase.commit()
""".lstrip()
    )
    _commit_all(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "transform",
            f"{transform_file}:RenameCodemod",
            str(tmp_path),
            "--write",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "def renamed()" in (tmp_path / "app.py").read_text()
    assert "Changes have been applied" in result.output


def test_transform_importable_module_function_write_modifies_target_repo(tmp_path, monkeypatch):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _init_repo(repo_path)
    (repo_path / "app.py").write_text("def target():\n    return 1\n")
    package_dir = tmp_path / "transforms"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("")
    (package_dir / "rename.py").write_text(
        """
def rename(codebase):
    function = codebase.get_function("target")
    function.rename("renamed")
    codebase.commit()
""".lstrip()
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    _commit_all(repo_path)

    result = CliRunner().invoke(
        main,
        [
            "transform",
            "transforms.rename:rename",
            str(repo_path),
            "--write",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "def renamed()" in (repo_path / "app.py").read_text()


def test_transform_rejects_arguments_for_target_without_arguments_parameter(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("def target():\n    return 1\n")
    transform_file = tmp_path / "noop_transform.py"
    transform_file.write_text(
        """
def noop(codebase):
    return None
""".lstrip()
    )
    _commit_all(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "transform",
            f"{transform_file}:noop",
            str(tmp_path),
            "--arguments",
            '{"unused": true}',
            "--write",
        ],
    )

    assert result.exit_code != 0
    assert "does not accept an arguments parameter" in strip_ansi(result.output)


def test_transform_requires_check_or_write(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("def target():\n    return 1\n")
    transform_file = tmp_path / "noop_transform.py"
    transform_file.write_text(
        """
def noop(codebase):
    return None
""".lstrip()
    )
    _commit_all(tmp_path)

    result = CliRunner().invoke(main, ["transform", f"{transform_file}:noop", str(tmp_path)])

    assert result.exit_code != 0
    assert "Choose either --check to preview changes or --write to apply them." in strip_ansi(result.output)


def test_transform_rejects_check_and_write_together(tmp_path):
    result = CliRunner().invoke(main, ["transform", "anything:anything", str(tmp_path), "--check", "--write"])

    assert result.exit_code != 0
    assert "--check and --write cannot be used together" in strip_ansi(result.output)
