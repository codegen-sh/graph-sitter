from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from graph_sitter.core.symbol_groups.collection import Collection

if TYPE_CHECKING:
    from tree_sitter import Node as TSNode

    from graph_sitter.codebase.codebase_context import CodebaseContext
    from graph_sitter.core.expressions.type import Type
    from graph_sitter.core.interfaces.supports_generic import SupportsGenerics
    from graph_sitter.core.node_id_factory import NodeId


TType = TypeVar("TType", bound="Type")
Parent = TypeVar("Parent", bound="SupportsGenerics")


class TypeParameters(Collection["TType", Parent], Generic[TType, Parent]):
    def __init__(self, ts_node: TSNode, file_node_id: NodeId, ctx: CodebaseContext, parent: Parent) -> None:
        super().__init__(ts_node, file_node_id, ctx, parent)
        self._init_children([self._parse_type(child) for child in ts_node.named_children])
