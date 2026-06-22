from collections.abc import Iterable

from tree_sitter import Node as TSNode
from typing_extensions import TypeVar

from graph_sitter.core.interfaces.editable import Editable

E = TypeVar("E", bound=Editable)

def sort_editables(
    nodes: Iterable[E | None] | Iterable[E],
    *,
    reverse: bool = False,
    dedupe: bool = True,
    alphabetical: bool = False,
    by_file: bool = False,
    by_id: bool = False,
) -> list[E]: ...
def sort_nodes(nodes: Iterable[TSNode | None] | Iterable[TSNode], *, reverse: bool = False, dedupe: bool = True) -> list[TSNode]: ...
