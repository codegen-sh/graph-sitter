from typing import TYPE_CHECKING, Generic, TypeVar

from graph_sitter.core.expressions.union_type import UnionType
from graph_sitter.shared.decorators.docs import py_apidoc

if TYPE_CHECKING:
    from graph_sitter.python.expressions.type import PyType

Parent = TypeVar("Parent")


@py_apidoc
class PyUnionType(UnionType["PyType", Parent], Generic[Parent]):
    """Union type

    Examples:
        str | int
    """

    pass
