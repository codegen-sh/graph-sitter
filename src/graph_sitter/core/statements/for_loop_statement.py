from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Generic, Self, TypeVar

from graph_sitter.core.autocommit import reader
from graph_sitter.core.interfaces.chainable import Chainable
from graph_sitter.core.interfaces.has_block import HasBlock
from graph_sitter.core.statements.block_statement import BlockStatement
from graph_sitter.core.statements.statement import StatementType
from graph_sitter.core.symbol_groups.collection import Collection
from graph_sitter.shared.decorators.docs import apidoc, noapidoc

if TYPE_CHECKING:
    from collections.abc import Generator

    from graph_sitter.core.detached_symbols.code_block import CodeBlock
    from graph_sitter.core.expressions import Expression
    from graph_sitter.core.import_resolution import Import, WildcardImport
    from graph_sitter.core.symbol import Symbol


Parent = TypeVar("Parent", bound="CodeBlock")


@apidoc
class ForLoopStatement(BlockStatement[Parent], HasBlock, ABC, Generic[Parent]):
    """Abstract representation of the for loop.

    Attributes:
        item: The item being iterated over, if applicable.
        iterable: The iterable expression that the loop iterates over.
    """

    statement_type = StatementType.FOR_LOOP_STATEMENT
    item: Expression[Self] | None = None
    iterable: Expression[Self]

    @noapidoc
    @reader
    def resolve_name(self, name: str, start_byte: int | None = None, strict: bool = True) -> Generator[Symbol | Import | WildcardImport]:
        if self.item and isinstance(self.iterable, Chainable):
            if start_byte is None or start_byte > self.iterable.end_byte:
                if name == self.item:
                    for frame in self.iterable.resolved_type_frames:
                        if frame.generics:
                            yield next(iter(frame.generics.values()))
                            return
                        yield frame.top.node
                        return
                elif isinstance(self.item, Collection):
                    for idx, item in enumerate(self.item):
                        if item == name:
                            for frame in self.iterable.resolved_type_frames:
                                if frame.generics and len(frame.generics) > idx:
                                    yield list(frame.generics.values())[idx]
                                    return
                                yield frame.top.node
                                return
        yield from super().resolve_name(name, start_byte, strict=strict)
