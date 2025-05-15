import graph_sitter
from graph_sitter.core.codebase import Codebase
from graph_sitter.shared.enums.programming_language import ProgrammingLanguage


@graph_sitter.function("test-language", subdirectories=["src/codegen/cli"], language=ProgrammingLanguage.PYTHON)
def run(codebase: Codebase):
    file = codebase.get_file("src/codegen/cli/errors.py")
    print(f"File: {file.path}")
    for s in file.symbols:
        print(s.name)


if __name__ == "__main__":
    print("Parsing codebase...")
    codebase = Codebase("./")

    print("Running...")
    run(codebase)
