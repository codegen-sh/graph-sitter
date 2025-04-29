from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from graph_sitter.core.statements.catch_statement import CatchStatement
from graph_sitter.shared.decorators.docs import apidoc, noapidoc
from graph_sitter.typescript.statements.block_statement import TSBlockStatement

if TYPE_CHECKING:
    from tree_sitter import Node as TSNode

    from graph_sitter.codebase.codebase_context import CodebaseContext
    from graph_sitter.core.interfaces.conditional_block import ConditionalBlock
    from graph_sitter.core.node_id_factory import NodeId
    from graph_sitter.typescript.detached_symbols.code_block import TSCodeBlock

Parent = TypeVar("Parent", bound="TSCodeBlock")


@apidoc
class TSCatchStatement(CatchStatement[Parent], TSBlockStatement, Generic[Parent]):
    """Typescript catch clause.

    Attributes:
        code_block: The code block that may trigger an exception
        condition: The condition which triggers this clause
    """

    def __init__(self, ts_node: TSNode, file_node_id: NodeId, ctx: CodebaseContext, parent: Parent, pos: int | None = None) -> None:
        super().__init__(ts_node, file_node_id, ctx, parent, pos)
        self.condition = self.child_by_field_name("parameter")

    @property
    @noapidoc
    def other_possible_blocks(self) -> list[ConditionalBlock]:
        return [self.parent]
