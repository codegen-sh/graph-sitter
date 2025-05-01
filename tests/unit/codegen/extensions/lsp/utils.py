from lsprotocol.types import CreateFile, TextDocumentEdit, WorkspaceEdit

from graph_sitter.core.codebase import Codebase
from graph_sitter.extensions.lsp.utils import get_path


def apply_edit(codebase: Codebase, edit: WorkspaceEdit):
    for change in edit.document_changes:
        if isinstance(change, TextDocumentEdit):
            path = get_path(change.text_document.uri)
            file = codebase.get_file(str(path.relative_to(codebase.repo_path)))
            for edit in change.edits:
                file.edit(edit.new_text)
        if isinstance(change, CreateFile):
            path = get_path(change.uri)
            codebase.create_file(str(path.relative_to(codebase.repo_path)))
    codebase.commit()
