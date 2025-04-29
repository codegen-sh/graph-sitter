from lsprotocol.types import SymbolKind

from graph_sitter.core.assignment import Assignment
from graph_sitter.core.class_definition import Class
from graph_sitter.core.file import File
from graph_sitter.core.function import Function
from graph_sitter.core.interface import Interface
from graph_sitter.core.interfaces.editable import Editable
from graph_sitter.core.statements.attribute import Attribute
from graph_sitter.typescript.namespace import TSNamespace

kinds = {
    File: SymbolKind.File,
    Class: SymbolKind.Class,
    Function: SymbolKind.Function,
    Assignment: SymbolKind.Variable,
    Interface: SymbolKind.Interface,
    TSNamespace: SymbolKind.Namespace,
    Attribute: SymbolKind.Variable,
}


def get_kind(node: Editable) -> SymbolKind:
    if isinstance(node, Function):
        if node.is_method:
            return SymbolKind.Method
    for kind in kinds:
        if isinstance(node, kind):
            return kinds[kind]
    msg = f"No kind found for {node}, {type(node)}"
    raise ValueError(msg)
