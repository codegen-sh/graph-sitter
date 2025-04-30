from graph_sitter.codebase.config import ProjectConfig
from graph_sitter.configs.models.codebase import CodebaseConfig
from graph_sitter.configs.models.secrets import SecretsConfig
from graph_sitter.core.codebase import (
    Codebase,
    CodebaseType,
)
from graph_sitter.git.repo_operator.repo_operator import RepoOperator
from graph_sitter.shared.enums.programming_language import ProgrammingLanguage


class CodebaseFactory:
    ####################################################################################################################
    # CREATE CODEBASE
    ####################################################################################################################

    @staticmethod
    def get_codebase_from_files(
        repo_path: str = "/tmp/codegen_run_on_str",
        files: dict[str, str] = {},
        bot_commit: bool = True,
        programming_language: ProgrammingLanguage = ProgrammingLanguage.PYTHON,
        config: CodebaseConfig | None = None,
        secrets: SecretsConfig | None = None,
    ) -> CodebaseType:
        op = RepoOperator.create_from_files(repo_path=repo_path, files=files, bot_commit=bot_commit)
        projects = [ProjectConfig(repo_operator=op, programming_language=programming_language)]
        return Codebase(projects=projects, config=config, secrets=secrets)
