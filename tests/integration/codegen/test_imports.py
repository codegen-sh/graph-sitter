import os

from graph_sitter.cli.sdk.decorator import function
from graph_sitter.cli.sdk.function import Function
from graph_sitter.code_generation.current_code_codebase import get_graphsitter_repo_path
from graph_sitter.core.codebase import Codebase


def test_codegen_imports():
    # Test decorated function
    @function(name="sample_codemod")
    def run(codebase):
        pass

    # Test class
    cls = Function
    assert cls is not None
    os.chdir(get_graphsitter_repo_path())  # TODO: CG-10643
    codebase = Codebase("./")
    assert codebase is not None
