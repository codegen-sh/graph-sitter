from typing import TYPE_CHECKING, Generic, TypeVar

from tree_sitter import Node as TSNode

from graph_sitter.core.expressions import Expression
from graph_sitter.core.node_id_factory import NodeId
from graph_sitter.shared.decorators.docs import ts_apidoc
from graph_sitter.typescript.expressions.named_type import TSNamedType

if TYPE_CHECKING:
    from graph_sitter.codebase.codebase_context import CodebaseContext
    from graph_sitter.core.interfaces.editable import Editable

Parent = TypeVar("Parent", bound="Editable")


@ts_apidoc
class TSExpressionType(TSNamedType, Generic[Parent]):
    """Type defined by evaluation of an expression

    Attributes:
        expression: The expression to evaluate that yields the type
    """

    expression: Expression["TSExpressionType[Parent]"]

    def __init__(self, ts_node: TSNode, file_node_id: NodeId, ctx: "CodebaseContext", parent: Parent):
        super().__init__(ts_node, file_node_id, ctx, parent)
        self.expression = self._parse_expression(ts_node)
