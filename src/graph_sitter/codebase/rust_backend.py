from __future__ import annotations

import json
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
class RustSourceRange:
    start_byte: int
    end_byte: int
    start_row: int
    start_column: int
    end_row: int
    end_column: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RustSourceRange:
        return cls(**{field: int(data[field]) for field in cls.__dataclass_fields__})


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


@dataclass(frozen=True)
class RustFileRecord:
    id: int
    path: str
    module_name: str | None
    byte_len: int
    line_count: int
    has_error: bool
    root_range: RustSourceRange

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RustFileRecord:
        return cls(
            id=int(data["id"]),
            path=str(data["path"]),
            module_name=data["module_name"],
            byte_len=int(data["byte_len"]),
            line_count=int(data["line_count"]),
            has_error=bool(data["has_error"]),
            root_range=RustSourceRange.from_dict(data["root_range"]),
        )


@dataclass(frozen=True)
class RustSymbolRecord:
    id: int
    file_id: int
    name: str
    kind: str
    range: RustSourceRange
    name_range: RustSourceRange

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RustSymbolRecord:
        return cls(
            id=int(data["id"]),
            file_id=int(data["file_id"]),
            name=str(data["name"]),
            kind=str(data["kind"]),
            range=RustSourceRange.from_dict(data["range"]),
            name_range=RustSourceRange.from_dict(data["name_range"]),
        )


@dataclass(frozen=True)
class RustImportRecord:
    id: int
    file_id: int
    kind: str
    module: str | None
    name: str | None
    alias: str | None
    range: RustSourceRange

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RustImportRecord:
        return cls(
            id=int(data["id"]),
            file_id=int(data["file_id"]),
            kind=str(data["kind"]),
            module=data["module"],
            name=data["name"],
            alias=data["alias"],
            range=RustSourceRange.from_dict(data["range"]),
        )


@dataclass(frozen=True)
class RustImportResolutionRecord:
    id: int
    import_id: int
    source_file_id: int
    target_file_id: int
    target_symbol_id: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RustImportResolutionRecord:
        target_symbol_id = data["target_symbol_id"]
        return cls(
            id=int(data["id"]),
            import_id=int(data["import_id"]),
            source_file_id=int(data["source_file_id"]),
            target_file_id=int(data["target_file_id"]),
            target_symbol_id=None if target_symbol_id is None else int(target_symbol_id),
        )


@dataclass
class RustIndexBackend:
    repo_path: Path
    extension: Any
    index: Any
    summary: RustIndexSummary
    _files: list[RustFileRecord] | None = None
    _symbols: list[RustSymbolRecord] | None = None
    _imports: list[RustImportRecord] | None = None
    _import_resolutions: list[RustImportResolutionRecord] | None = None

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

    @property
    def files(self) -> list[RustFileRecord]:
        if self._files is None:
            self._files = [RustFileRecord.from_dict(record) for record in json.loads(self.index.files_json())]
        return self._files

    @property
    def symbols(self) -> list[RustSymbolRecord]:
        if self._symbols is None:
            self._symbols = [RustSymbolRecord.from_dict(record) for record in json.loads(self.index.symbols_json())]
        return self._symbols

    @property
    def imports(self) -> list[RustImportRecord]:
        if self._imports is None:
            self._imports = [RustImportRecord.from_dict(record) for record in json.loads(self.index.imports_json())]
        return self._imports

    @property
    def import_resolutions(self) -> list[RustImportResolutionRecord]:
        if self._import_resolutions is None:
            self._import_resolutions = [RustImportResolutionRecord.from_dict(record) for record in json.loads(self.index.import_resolutions_json())]
        return self._import_resolutions

    def to_json(self) -> str:
        return str(self.index.to_json())
