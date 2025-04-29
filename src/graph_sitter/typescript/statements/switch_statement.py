from __future__ import annotations

from typing import TYPE_CHECKING

from graph_sitter.core.statements.switch_statement import SwitchStatement
from graph_sitter.shared.decorators.docs import ts_apidoc
from graph_sitter.typescript.statements.switch_case import TSSwitchCase

if TYPE_CHECKING:
    from tree_sitter import Node as TSNode

    from graph_sitter.codebase.codebase_context import CodebaseContext
    from graph_sitter.core.node_id_factory import NodeId
    from graph_sitter.typescript.detached_symbols.code_block import TSCodeBlock


@ts_apidoc
class TSSwitchStatement(SwitchStatement["TSCodeBlock[Self]", "TSCodeBlock", TSSwitchCase]):
    """Typescript switch statement"""

    def __init__(self, ts_node: TSNode, file_node_id: NodeId, ctx: CodebaseContext, parent: TSCodeBlock, pos: int | None = None) -> None:
        super().__init__(ts_node, file_node_id, ctx, parent, pos)
        self.value = self.child_by_field_name("value")
        code_block = self.ts_node.child_by_field_name("body")
        self.cases = []
        for node in code_block.named_children:
            self.cases.append(TSSwitchCase(node, file_node_id, ctx, self))
