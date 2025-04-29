from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from graph_sitter.core.statements.block_statement import BlockStatement
from graph_sitter.shared.decorators.docs import apidoc
from graph_sitter.typescript.interfaces.has_block import TSHasBlock

if TYPE_CHECKING:
    from graph_sitter.typescript.detached_symbols.code_block import TSCodeBlock

Parent = TypeVar("Parent", bound="TSCodeBlock")


@apidoc
class TSBlockStatement(BlockStatement[Parent], TSHasBlock, Generic[Parent]):
    """Statement which contains a block."""
