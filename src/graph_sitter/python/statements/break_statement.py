from __future__ import annotations

from typing import TYPE_CHECKING, override

from graph_sitter.compiled.autocommit import commiter
from graph_sitter.core.statements.statement import Statement, StatementType
from graph_sitter.shared.decorators.docs import noapidoc, py_apidoc

if TYPE_CHECKING:
    from graph_sitter.core.dataclasses.usage import UsageKind
    from graph_sitter.core.interfaces.has_name import HasName


@py_apidoc
class PyBreakStatement(Statement["PyCodeBlock"]):
    """An abstract representation of a python break statement."""

    statement_type = StatementType.BREAK_STATEMENT

    @noapidoc
    @commiter
    @override
    def _compute_dependencies(self, usage_type: UsageKind, dest: HasName | None = None) -> None:
        pass
