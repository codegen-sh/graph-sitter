from abc import abstractmethod
from typing import Generic

from graph_sitter.core.autocommit import writer
from graph_sitter.core.interfaces.chainable import Chainable
from graph_sitter.core.interfaces.editable import Editable
from typing_extensions import TypeVar

from codegen.shared.decorators.docs import noapidoc

Parent = TypeVar("Parent", bound=Editable)


class Resolvable(Chainable[Parent], Generic[Parent]):
    """Represents a class resolved to another symbol during the compute dependencies step."""

    @abstractmethod
    @noapidoc
    @writer
    def rename_if_matching(self, old: str, new: str) -> None: ...
