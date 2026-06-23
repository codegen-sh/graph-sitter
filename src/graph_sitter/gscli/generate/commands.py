import os
import re
import shutil

import click
from termcolor import colored

from graph_sitter.code_generation.codegen_sdk_codebase import get_codegen_sdk_codebase
from graph_sitter.code_generation.doc_utils.generate_docs_json import generate_docs_json
from graph_sitter.code_generation.mdx_docs_generation import render_mdx_page_for_class
from graph_sitter.gscli.generate.runner_imports import _generate_runner_imports
from graph_sitter.gscli.generate.utils import LanguageType, generate_builtins_file
from graph_sitter.shared.logging.get_logger import get_logger

logger = get_logger(__name__)

AUTO_GENERATED_COMMENT = "THE CODE BELOW IS AUTO GENERATED. UPDATE THE SNIPPET BY UPDATING THE SKILL"
CODE_SNIPPETS_REGEX = r"(?:```python\n(?:(?!```)[\s\S])*?\n```|<CodeGroup>(?:(?!</CodeGroup>)[\s\S])*?</CodeGroup>)"


@click.group()
def generate() -> None:
    """Commands for running auto-generate commands, currently for typestubs, imports to include in runners, and docs"""
    ...


@generate.command()
@click.argument("docs_dir", default="docs", required=False)
def docs(docs_dir: str) -> None:
    """Compile new .MDX files for the auto-generated docs pages and write them to the file system.
    To actually deploy these changes, you must commit and merge the changes into develop

    This will generate docs using the codebase locally, including any unstaged changes
    """
    docs_dir = os.path.join(os.getcwd(), docs_dir)
    generate_docs(docs_dir)


@generate.command()
@click.argument("imports_file", default="function_imports.py", required=False)
def runner_imports(imports_file: str) -> None:
    """Generate imports to include in runner execution environment"""
    _generate_runner_imports(imports_file)


@generate.command()
def typestubs() -> None:
    """Generate typestubs for the the graphsitter Codebase module
    The Codebase class and it's constituents contain methods that should not be exposed, i.e we have private methods
    and private properties that we'd like to keep internal. So the way this works is we generate the typestubs and the remove
    the "internal" symbols. For example we'll remove:
     - "_" prefixed methods and properties
     - methods with `@noapidocs` decorator
    """
    _generate_codebase_typestubs()


def _generate_codebase_typestubs() -> None:
    initial_dir = os.getcwd()

    # right now this command expects you to run it from here
    if not initial_dir.endswith("codegen/codegen-backend"):
        print(colored("Error: Must be in a directory ending with 'codegen/codegen-backend'", "red"))
        exit(1)

    out_dir = os.path.abspath(os.path.join(initial_dir, "typings"))
    frontend_typestubs_dir = os.path.abspath(os.path.join(initial_dir, os.pardir, "codegen-frontend/assets/typestubs/graphsitter"))
    if os.path.isdir(out_dir):
        # remove typings dir if it exists
        shutil.rmtree(out_dir)
    if os.path.isdir(frontend_typestubs_dir):
        # remove typings dir if it exists
        shutil.rmtree(frontend_typestubs_dir)
    # generate typestubs in codegen-frontend/assets/typestubs/graphsitter  using pyright
    os.system("uv run pyright -p . --createstub graph_sitter.core.codebase")
    os.system("uv run pyright -p . --createstub graph_sitter.git")
    os.system("uv run pyright -p . --createstub networkx")
    # also generate for codemod context model and all its nested models
    os.system("uv run pyright -p . --createstub app.codemod.compilation.models.context")
    os.system("uv run pyright -p . --createstub app.codemod.compilation.models.pr_options")
    os.system("uv run pyright -p . --createstub app.codemod.compilation.models.github_named_user_context")
    os.system("uv run pyright -p . --createstub app.codemod.compilation.models.pull_request_context")
    os.system("uv run pyright -p . --createstub app.codemod.compilation.models.pr_part_context")

    # TODO fix this, to remove noapidoc and hidden methods
    # right now it uses astor.to_source, which doesn't respect the generics, and breaks things
    # strip_internal_symbols(frontend_typestubs_dir)

    # Autogenerate the builtins file based on what has apidoc, we use the same logic here as we do to generate the runner imports
    generate_builtins_file(frontend_typestubs_dir + "/__builtins__.pyi", LanguageType.BOTH)
    generate_builtins_file(frontend_typestubs_dir + "/__builtins__python__.pyi", LanguageType.PYTHON)
    generate_builtins_file(frontend_typestubs_dir + "/__builtins__typescript__.pyi", LanguageType.TYPESCRIPT)

    if os.path.isdir(out_dir):
        # remove typings dir if it exists
        shutil.rmtree(out_dir)


def generate_docs(docs_dir: str) -> None:
    """Compile new .MDX files for the auto-generated docs pages and write them to the file system.
    To actually deploy these changes, you must commit and merge the changes into develop

    This will generate docs using the codebase locally, including any unstaged changes
    """
    generate_codegen_sdk_docs(docs_dir)


def get_snippet_pattern(target_name: str) -> str:
    pattern = rf"\[//\]: # \(--{re.escape(target_name)}--\)\s*(?:\[//\]: # \(--{re.escape(AUTO_GENERATED_COMMENT)}--\)\s*)?"
    pattern += CODE_SNIPPETS_REGEX
    return pattern


def generate_codegen_sdk_docs(docs_dir: str) -> None:
    """Generate the docs for the codegen_sdk API."""
    print(colored("Generating codegen_sdk docs", "green"))

    # Generate docs page for codebase api and write to the file system
    codebase = get_codegen_sdk_codebase()
    gs_docs = generate_docs_json(codebase, "HEAD")

    # Prepare the directories for the new docs
    # Delete existing documentation directories if they exist
    # So we remove generated docs for any classes which no longer exist
    python_docs_dir = os.path.join(docs_dir, "api-reference", "python")
    typescript_docs_dir = os.path.join(docs_dir, "api-reference", "typescript")
    core_dir = os.path.join(docs_dir, "api-reference", "core")

    for dir_path in [python_docs_dir, typescript_docs_dir, core_dir]:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)

    os.makedirs(python_docs_dir, exist_ok=True)
    os.makedirs(typescript_docs_dir, exist_ok=True)
    os.makedirs(core_dir, exist_ok=True)

    # Generate the docs pages for core, python, and typescript classes

    # Write the generated docs to the file system, splitting between core, python, and typescript.
    # The custom Next.js docs site discovers these files directly from docs/.
    # TODO replace this with new `get_mdx_for_class` function
    for class_doc in gs_docs.classes:
        class_name = class_doc.title
        lower_class_name = class_name.lower()
        if lower_class_name.startswith("py"):
            file_path = os.path.join(python_docs_dir, f"{class_name}.mdx")
        elif lower_class_name.startswith(("ts", "jsx")):
            file_path = os.path.join(typescript_docs_dir, f"{class_name}.mdx")
        else:
            file_path = os.path.join(core_dir, f"{class_name}.mdx")

        mdx_page = render_mdx_page_for_class(cls_doc=class_doc)
        with open(file_path, "w") as f:
            f.write(mdx_page)
    print(colored("Finished writing new .mdx files", "green"))
