from dataclasses import dataclass
from pathlib import Path

from graph_sitter.cli.utils.schema import CodemodConfig


@dataclass
class Codemod:
    """Represents a codemod in the local filesystem."""

    name: str
    path: Path
    config: CodemodConfig | None = None

    def relative_path(self) -> str:
        """Get the relative path to this codemod."""
        return self.path.relative_to(Path.cwd())

    def get_current_source(self) -> str:
        """Get the current source code for this codemod."""
        text = self.path.read_text()
        text = text.strip()
        return text
