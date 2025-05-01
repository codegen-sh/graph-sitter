from __future__ import annotations

from typing import TYPE_CHECKING, Generic, Self, TypeVar

from graph_sitter.compiled.autocommit import commiter
from graph_sitter.core.interfaces.conditional_block import ConditionalBlock
from graph_sitter.core.statements.block_statement import BlockStatement
from graph_sitter.shared.decorators.docs import apidoc, noapidoc

if TYPE_CHECKING:
    from graph_sitter.core.dataclasses.usage import UsageKind
    from graph_sitter.core.detached_symbols.code_block import CodeBlock
    from graph_sitter.core.expressions import Expression
    from graph_sitter.core.interfaces.has_name import HasName


Parent = TypeVar("Parent", bound="CodeBlock")


@apidoc
class CatchStatement(ConditionalBlock, BlockStatement[Parent], Generic[Parent]):
    """Abstract representation catch clause.

    Attributes:
        code_block: The code block that may trigger an exception
        condition: The condition which triggers this clause
    """

    condition: Expression[Self] | None = None

    @noapidoc
    @commiter
    def _compute_dependencies(self, usage_type: UsageKind | None = None, dest: HasName | None = None) -> None:
        if self.condition:
            self.condition._compute_dependencies(usage_type, dest)
        super()._compute_dependencies(usage_type, dest)
