from typing import TYPE_CHECKING, TypeVar

from graph_sitter.core.expressions.union_type import UnionType
from graph_sitter.shared.decorators.docs import py_apidoc

if TYPE_CHECKING:
    from graph_sitter.python.expressions.type import PyType

Parent = TypeVar("Parent")


@py_apidoc
class PyUnionType[Parent](UnionType["PyType", Parent]):
    """Union type

    Examples:
        str | int
    """

    pass
