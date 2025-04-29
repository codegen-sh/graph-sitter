from __future__ import annotations

from typing import TYPE_CHECKING

from graph_sitter.core.statements.import_statement import ImportStatement
from graph_sitter.core.symbol_groups.collection import Collection
from graph_sitter.python.detached_symbols.code_block import PyCodeBlock
from graph_sitter.python.import_resolution import PyImport
from graph_sitter.shared.decorators.docs import py_apidoc

if TYPE_CHECKING:
    from tree_sitter import Node as TSNode

    from graph_sitter.codebase.codebase_context import CodebaseContext
    from graph_sitter.core.node_id_factory import NodeId


@py_apidoc
class PyImportStatement(ImportStatement["PyFile", PyImport, PyCodeBlock]):
    """An abstract representation of a python import statement."""

    def __init__(self, ts_node: TSNode, file_node_id: NodeId, ctx: CodebaseContext, parent: PyCodeBlock, pos: int) -> None:
        super().__init__(ts_node, file_node_id, ctx, parent, pos)
        imports = []
        if ts_node.type == "import_statement":
            imports.extend(PyImport.from_import_statement(ts_node, file_node_id, ctx, self))
        elif ts_node.type == "import_from_statement":
            imports.extend(PyImport.from_import_from_statement(ts_node, file_node_id, ctx, self))
        elif ts_node.type == "future_import_statement":
            imports.extend(PyImport.from_future_import_statement(ts_node, file_node_id, ctx, self))
        self.imports = Collection(ts_node, file_node_id, ctx, self, delimiter="\n", children=imports)
        for imp in self.imports:
            imp.import_statement = self
