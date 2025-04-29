from typing import Generic, TypeVar

from graph_sitter.core.expressions.union_type import UnionType
from graph_sitter.shared.decorators.docs import py_apidoc

Parent = TypeVar("Parent")


@py_apidoc
class PyUnionType(UnionType["PyType", Parent], Generic[Parent]):
    """Union type

    Examples:
        str | int
    """

    pass
