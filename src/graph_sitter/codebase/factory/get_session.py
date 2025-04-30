import os
import sys
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from typing import Literal, overload

from graph_sitter.codebase.codebase_context import CodebaseContext
from graph_sitter.codebase.config import ProjectConfig, SessionOptions, TestFlags
from graph_sitter.codebase.factory.codebase_factory import CodebaseFactory
from graph_sitter.configs.models.codebase import CodebaseConfig
from graph_sitter.configs.models.secrets import SecretsConfig
from graph_sitter.core.codebase import Codebase, PyCodebaseType, TSCodebaseType
from graph_sitter.core.file import SourceFile
from graph_sitter.git.repo_operator.repo_operator import RepoOperator
from graph_sitter.shared.enums.programming_language import ProgrammingLanguage
from graph_sitter.tree_sitter_parser import print_errors


@overload
def get_codebase_session(
    tmpdir: str | os.PathLike[str],
    programming_language: None = None,
    files: dict[str, str] = {},
    commit: bool = True,
    sync_graph: bool = True,
    verify_input: bool = True,
    verify_output: bool = True,
    config: CodebaseConfig = TestFlags,
    session_options: SessionOptions = SessionOptions(),
    secrets: SecretsConfig | None = None,
) -> AbstractContextManager[PyCodebaseType]: ...


@overload
def get_codebase_session(
    tmpdir: str | os.PathLike[str],
    programming_language: Literal[ProgrammingLanguage.PYTHON],
    files: dict[str, str] = {},
    commit: bool = True,
    sync_graph: bool = True,
    verify_input: bool = True,
    verify_output: bool = True,
    config: CodebaseConfig = TestFlags,
    session_options: SessionOptions = SessionOptions(),
    secrets: SecretsConfig | None = None,
) -> AbstractContextManager[PyCodebaseType]: ...


@overload
def get_codebase_session(
    tmpdir: str | os.PathLike[str],
    programming_language: Literal[ProgrammingLanguage.TYPESCRIPT],
    files: dict[str, str] = {},
    commit: bool = True,
    sync_graph: bool = True,
    verify_input: bool = True,
    verify_output: bool = True,
    config: CodebaseConfig = TestFlags,
    session_options: SessionOptions = SessionOptions(),
    secrets: SecretsConfig | None = None,
) -> AbstractContextManager[TSCodebaseType]: ...


@contextmanager
def get_codebase_session(
    tmpdir: str | os.PathLike[str],
    programming_language: ProgrammingLanguage = ProgrammingLanguage.PYTHON,
    files: dict[str, str] = {},
    commit: bool = True,
    sync_graph: bool = True,
    verify_input: bool = True,
    verify_output: bool = True,
    config: CodebaseConfig = TestFlags,
    session_options: SessionOptions = SessionOptions(),
    secrets: SecretsConfig | None = None,
) -> Generator[Codebase, None, None]:
    """Gives you a Codebase operating on the files you provided as a dict"""
    codebase = CodebaseFactory.get_codebase_from_files(repo_path=str(tmpdir), files=files, config=config, secrets=secrets, programming_language=programming_language)
    with codebase.session(
        commit=commit,
        sync_graph=sync_graph,
        session_options=session_options,
    ):
        if verify_input:
            for file in codebase.files:
                # NOTE: We only check SourceFiles for syntax errors
                abs_filepath = os.path.join(tmpdir, file.filepath)
                if os.path.exists(abs_filepath):
                    if isinstance(file, SourceFile):
                        # Check for syntax errors
                        print_errors(abs_filepath, file.content)
                        if file.ts_node.has_error:
                            msg = "Invalid syntax in test case"
                            raise SyntaxError(msg)
        yield codebase

    if verify_output:
        for file in codebase.files:
            if os.path.exists(file.filepath):
                if file.ts_node.has_error and len(file.content.splitlines()) < 10:
                    print(file.content, file=sys.stderr)
                print_errors(file.filepath, file.content)
                assert not file.ts_node.has_error, "Invalid syntax in file after commiting"


@contextmanager
def get_codebase_graph_session(
    tmpdir: str,
    programming_language: ProgrammingLanguage = ProgrammingLanguage.PYTHON,
    files: dict[str, str] = {},
    sync_graph: bool = True,
    session_options: SessionOptions = SessionOptions(),
) -> Generator[CodebaseContext, None, None]:
    """Gives you a Codebase2 operating on the files you provided as a dict"""
    op = RepoOperator.create_from_files(repo_path=tmpdir, files=files)
    projects = [ProjectConfig(repo_operator=op, programming_language=programming_language)]
    graph = CodebaseContext(projects=projects, config=TestFlags)
    with graph.session(sync_graph=sync_graph, session_options=session_options):
        try:
            yield graph
        finally:
            pass
