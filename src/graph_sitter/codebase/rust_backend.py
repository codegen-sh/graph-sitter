from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


class RustBackendUnavailableError(RuntimeError):
    """Raised when the optional Rust backend extension cannot be loaded."""


class RustIndexBuildError(RuntimeError):
    """Raised when the Rust backend extension loads but cannot index the repo."""


@dataclass(frozen=True)
class RustIndexSummary:
    files: int
    symbols: int
    classes: int
    functions: int
    imports: int
    import_resolutions: int
    bytes: int
    lines: int
    files_with_errors: int

    @classmethod
    def from_object(cls, summary: Any) -> RustIndexSummary:
        if hasattr(summary, "as_dict"):
            data = dict(summary.as_dict())
        elif isinstance(summary, dict):
            data = summary
        else:
            data = {field: getattr(summary, field) for field in cls.__dataclass_fields__}
        return cls(**{field: int(data[field]) for field in cls.__dataclass_fields__})


@dataclass
class RustIndexBackend:
    repo_path: Path
    extension: Any
    index: Any
    summary: RustIndexSummary

    @classmethod
    def build(cls, repo_path: str | Path, file_paths: Sequence[str] | None = None) -> RustIndexBackend:
        path = Path(repo_path).resolve()
        try:
            extension = import_module("graph_sitter_py")
        except ImportError as error:
            message = "Rust graph backend extension `graph_sitter_py` is not installed"
            raise RustBackendUnavailableError(message) from error

        try:
            if file_paths is None:
                index = extension.index_python_path(str(path))
            else:
                index = extension.index_python_paths(str(path), list(file_paths))
            summary = RustIndexSummary.from_object(index.summary())
        except Exception as error:
            message = f"Rust graph backend failed to index {path}"
            raise RustIndexBuildError(message) from error

        return cls(repo_path=path, extension=extension, index=index, summary=summary)

    @property
    def engine_version(self) -> str:
        return str(self.extension.engine_version())

    def to_json(self) -> str:
        return str(self.index.to_json())
