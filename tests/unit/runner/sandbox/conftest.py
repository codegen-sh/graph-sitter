from collections.abc import Generator
from unittest.mock import patch

import pytest

from graph_sitter.codebase.config import ProjectConfig
from graph_sitter.core.codebase import Codebase
from graph_sitter.git.repo_operator.repo_operator import RepoOperator
from graph_sitter.runner.sandbox.executor import SandboxExecutor
from graph_sitter.runner.sandbox.runner import SandboxRunner
from graph_sitter.shared.enums.programming_language import ProgrammingLanguage


@pytest.fixture
def codebase(tmpdir) -> Codebase:
    op = RepoOperator.create_from_files(repo_path=f"{tmpdir}/test-repo", files={"test.py": "a = 1"}, bot_commit=True)
    projects = [ProjectConfig(repo_operator=op, programming_language=ProgrammingLanguage.PYTHON)]
    codebase = Codebase(projects=projects)
    return codebase


@pytest.fixture
def executor(codebase: Codebase) -> Generator[SandboxExecutor]:
    yield SandboxExecutor(codebase)


@pytest.fixture
def runner(codebase: Codebase, tmpdir):
    with patch("graph_sitter.runner.sandbox.runner.RepoOperator") as mock_op:
        with patch.object(SandboxRunner, "_build_graph") as mock_init_codebase:
            mock_init_codebase.return_value = codebase
            mock_op.return_value = codebase.op

            yield SandboxRunner(repo_config=codebase.op.repo_config)
