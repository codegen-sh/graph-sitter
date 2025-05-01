from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from graph_sitter.compiled.autocommit import commiter
from graph_sitter.core.expressions.expression import Expression
from graph_sitter.shared.decorators.docs import apidoc, noapidoc

if TYPE_CHECKING:
    from graph_sitter.core.dataclasses.usage import UsageKind
    from graph_sitter.core.interfaces.editable import Editable
    from graph_sitter.core.interfaces.has_name import HasName

Parent = TypeVar("Parent", bound="Editable")


@apidoc
class Value(Expression[Parent], Generic[Parent]):
    """Editable attribute on code objects that has a value.

    For example, Functions, Classes, Assignments, Interfaces, Expressions, Arguments and Parameters all have values.

    See also HasValue.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ctx.parser.log_unparsed(self.ts_node)

    @noapidoc
    @commiter
    def _compute_dependencies(self, usage_type: UsageKind, dest: HasName | None = None):
        for node in self.children:
            node._compute_dependencies(usage_type, dest=dest)
