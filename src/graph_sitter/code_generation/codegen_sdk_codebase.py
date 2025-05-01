import os.path

from graph_sitter.code_generation.current_code_codebase import get_codegen_codebase_base_path, get_current_code_codebase
from graph_sitter.core.codebase import Codebase


def get_codegen_sdk_subdirectories() -> list[str]:
    base = get_codegen_codebase_base_path()
    graphsitter_path = os.path.join(base, "graph_sitter")
    paths = [os.path.join(base, "codemods")]
    for dir in os.listdir(graphsitter_path):
        if dir in ["git", "extensions"]:
            continue
        paths.append(os.path.join(graphsitter_path, dir))

    return paths


def get_codegen_sdk_codebase() -> Codebase:
    """Grabs a Codebase w/ GraphSitter content. Responsible for figuring out where it is, e.g. in Modal or local"""
    codebase = get_current_code_codebase(subdirectories=get_codegen_sdk_subdirectories())
    return codebase
