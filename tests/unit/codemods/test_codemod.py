from codemods.codemod import Codemod
from graph_sitter.core.codebase import Codebase


def test_codemod_execute():
    def sample_execute(codebase: Codebase):
        for file in codebase.files:
            file.content = "print('hello')"

    codemod = Codemod(name="sample_codemod", execute=sample_execute)
    assert id(codemod.execute) == id(sample_execute)

    codemod = Codemod(name="sample_codemod")
    assert codemod.execute is None
