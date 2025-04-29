from typing import Generic, TypeVar

from graph_sitter.core.expressions.union_type import UnionType
from graph_sitter.shared.decorators.docs import ts_apidoc

Parent = TypeVar("Parent")


@ts_apidoc
class TSUnionType(UnionType["TSType", Parent], Generic[Parent]):
    """Union type

    Examples:
        string | number
    """

    pass
