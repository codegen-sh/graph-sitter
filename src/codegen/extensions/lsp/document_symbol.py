from lsprotocol.types import DocumentSymbol

from codegen.extensions.lsp.kind import get_kind
from codegen.extensions.lsp.range import get_range
from graph_sitter.core.class_definition import Class
from graph_sitter.core.interfaces.editable import Editable
from graph_sitter.extensions.sort import sort_editables


def get_document_symbol(node: Editable) -> DocumentSymbol:
    children = []
    nodes = []
    if isinstance(node, Class):
        nodes.extend(node.methods)
        nodes.extend(node.attributes)
        nodes.extend(node.nested_classes)
    nodes = sort_editables(nodes)
    for child in nodes:
        children.append(get_document_symbol(child))
    return DocumentSymbol(
        name=node.name,
        kind=get_kind(node),
        range=get_range(node),
        selection_range=get_range(node.get_name()),
        children=children,
    )
