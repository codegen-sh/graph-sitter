from collections.abc import Generator
from typing import Generic, Self, TypeVar, override

from graph_sitter.codebase.resolution_stack import ResolutionStack
from graph_sitter.compiled.autocommit import reader
from graph_sitter.core.dataclasses.usage import UsageKind
from graph_sitter.core.expressions.type import Type
from graph_sitter.core.interfaces.importable import Importable
from graph_sitter.shared.decorators.docs import noapidoc, ts_apidoc

Parent = TypeVar("Parent")


@ts_apidoc
class TSUndefinedType(Type[Parent], Generic[Parent]):
    """Undefined type. Represents the undefined keyword
    Examples:
        undefined
    """

    @noapidoc
    def _compute_dependencies(self, usage_type: UsageKind, dest: Importable):
        pass

    @reader
    @noapidoc
    @override
    def _resolved_types(self) -> Generator[ResolutionStack[Self], None, None]:
        yield from []
