from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from graph_sitter.codebase.codebase_context import CodebaseContext

from graph_sitter._proxy import proxy_property
from graph_sitter.core.dataclasses.usage import UsageKind, UsageType
from graph_sitter.enums import ImportType, NodeType, SymbolType


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
    global_variables: int
    imports: int
    import_resolutions: int
    references: int
    dependencies: int
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
    parent_symbol_id: int | None
    is_top_level: bool
    name: str
    kind: str
    range: RustSourceRange
    name_range: RustSourceRange

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RustSymbolRecord:
        return cls(
            id=int(data["id"]),
            file_id=int(data["file_id"]),
            parent_symbol_id=None if data.get("parent_symbol_id") is None else int(data["parent_symbol_id"]),
            is_top_level=bool(data.get("is_top_level", True)),
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


@dataclass(frozen=True)
class RustReferenceRecord:
    id: int
    source_file_id: int
    source_symbol_id: int | None
    target_symbol_id: int
    import_id: int | None
    name: str
    range: RustSourceRange

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RustReferenceRecord:
        source_symbol_id = data["source_symbol_id"]
        import_id = data["import_id"]
        return cls(
            id=int(data["id"]),
            source_file_id=int(data["source_file_id"]),
            source_symbol_id=None if source_symbol_id is None else int(source_symbol_id),
            target_symbol_id=int(data["target_symbol_id"]),
            import_id=None if import_id is None else int(import_id),
            name=str(data["name"]),
            range=RustSourceRange.from_dict(data["range"]),
        )


@dataclass(frozen=True)
class RustDependencyRecord:
    id: int
    source_symbol_id: int
    target_symbol_id: int
    source_file_id: int
    target_file_id: int
    reference_ids: list[int]
    reference_count: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RustDependencyRecord:
        return cls(
            id=int(data["id"]),
            source_symbol_id=int(data["source_symbol_id"]),
            target_symbol_id=int(data["target_symbol_id"]),
            source_file_id=int(data["source_file_id"]),
            target_file_id=int(data["target_file_id"]),
            reference_ids=[int(reference_id) for reference_id in data["reference_ids"]],
            reference_count=int(data["reference_count"]),
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
    _references: list[RustReferenceRecord] | None = None
    _dependencies: list[RustDependencyRecord] | None = None
    _file_handles: list[RustCompactFile] | None = None
    _symbol_handles: list[RustCompactSymbol] | None = None
    _import_handles: list[RustCompactImport] | None = None
    _file_handles_by_id: dict[int, RustCompactFile] | None = None
    _symbol_handles_by_id: dict[int, RustCompactSymbol] | None = None
    _import_handles_by_id: dict[int, RustCompactImport] | None = None
    _symbols_by_file_id: dict[int, list[RustCompactSymbol]] | None = None
    _imports_by_file_id: dict[int, list[RustCompactImport]] | None = None
    _import_resolutions_by_import_id: dict[int, RustImportResolutionRecord] | None = None
    _import_resolutions_by_target_file_id: dict[int, list[RustImportResolutionRecord]] | None = None
    _references_by_target_symbol_id: dict[int, list[RustReferenceRecord]] | None = None
    _references_by_source_symbol_id: dict[int, list[RustReferenceRecord]] | None = None
    _references_by_import_id: dict[int, list[RustReferenceRecord]] | None = None
    _dependencies_by_source_symbol_id: dict[int, list[RustDependencyRecord]] | None = None
    _dependencies_by_target_symbol_id: dict[int, list[RustDependencyRecord]] | None = None
    _symbols_by_parent_symbol_id: dict[int, list[RustCompactSymbol]] | None = None

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

    @property
    def references(self) -> list[RustReferenceRecord]:
        if self._references is None:
            self._references = [RustReferenceRecord.from_dict(record) for record in json.loads(self.index.references_json())]
        return self._references

    @property
    def dependencies(self) -> list[RustDependencyRecord]:
        if self._dependencies is None:
            self._dependencies = [RustDependencyRecord.from_dict(record) for record in json.loads(self.index.dependencies_json())]
        return self._dependencies

    @property
    def file_handles(self) -> list[RustCompactFile]:
        if self._file_handles is None:
            self._file_handles = [RustCompactFile(self, record) for record in self.files]
        return self._file_handles

    @property
    def symbol_handles(self) -> list[RustCompactSymbol]:
        if self._symbol_handles is None:
            self._symbol_handles = [RustCompactSymbol(self, record) for record in self.symbols]
        return self._symbol_handles

    @property
    def import_handles(self) -> list[RustCompactImport]:
        if self._import_handles is None:
            self._import_handles = [RustCompactImport(self, record) for record in self.imports]
        return self._import_handles

    def get_file_handle(self, filepath: str, *, ignore_case: bool = False) -> RustCompactFile | None:
        path = Path(filepath.replace("\\", "/"))
        if path.is_absolute():
            try:
                path = path.resolve().relative_to(self.repo_path)
            except ValueError:
                return None
        normalized = path.as_posix()
        if normalized.startswith("./"):
            normalized = normalized[2:]
        if ignore_case:
            normalized = normalized.lower()
            return next((file for file in self.file_handles if file.filepath.lower() == normalized), None)
        return next((file for file in self.file_handles if file.filepath == normalized), None)

    def symbols_for_file(self, file_id: int) -> list[RustCompactSymbol]:
        if self._symbols_by_file_id is None:
            symbols_by_file_id: dict[int, list[RustCompactSymbol]] = {}
            for symbol in self.symbol_handles:
                symbols_by_file_id.setdefault(symbol.record.file_id, []).append(symbol)
            self._symbols_by_file_id = symbols_by_file_id
        return self._symbols_by_file_id.get(file_id, [])

    def symbols_for_parent(self, parent_symbol_id: int) -> list[RustCompactSymbol]:
        if self._symbols_by_parent_symbol_id is None:
            symbols_by_parent_symbol_id: dict[int, list[RustCompactSymbol]] = {}
            for symbol in self.symbol_handles:
                if symbol.record.parent_symbol_id is not None:
                    symbols_by_parent_symbol_id.setdefault(symbol.record.parent_symbol_id, []).append(symbol)
            self._symbols_by_parent_symbol_id = symbols_by_parent_symbol_id
        return self._symbols_by_parent_symbol_id.get(parent_symbol_id, [])

    def imports_for_file(self, file_id: int) -> list[RustCompactImport]:
        if self._imports_by_file_id is None:
            imports_by_file_id: dict[int, list[RustCompactImport]] = {}
            for import_handle in self.import_handles:
                imports_by_file_id.setdefault(import_handle.record.file_id, []).append(import_handle)
            self._imports_by_file_id = imports_by_file_id
        return self._imports_by_file_id.get(file_id, [])

    def file_handle_by_id(self, file_id: int) -> RustCompactFile | None:
        if self._file_handles_by_id is None:
            self._file_handles_by_id = {file.record.id: file for file in self.file_handles}
        return self._file_handles_by_id.get(file_id)

    def symbol_handle_by_id(self, symbol_id: int) -> RustCompactSymbol | None:
        if self._symbol_handles_by_id is None:
            self._symbol_handles_by_id = {symbol.record.id: symbol for symbol in self.symbol_handles}
        return self._symbol_handles_by_id.get(symbol_id)

    def import_handle_by_id(self, import_id: int) -> RustCompactImport | None:
        if self._import_handles_by_id is None:
            self._import_handles_by_id = {import_handle.record.id: import_handle for import_handle in self.import_handles}
        return self._import_handles_by_id.get(import_id)

    def import_resolution_for_import(self, import_id: int) -> RustImportResolutionRecord | None:
        if self._import_resolutions_by_import_id is None:
            self._import_resolutions_by_import_id = {resolution.import_id: resolution for resolution in self.import_resolutions}
        return self._import_resolutions_by_import_id.get(import_id)

    def import_resolutions_to_file(self, file_id: int) -> list[RustImportResolutionRecord]:
        if self._import_resolutions_by_target_file_id is None:
            import_resolutions_by_target_file_id: dict[int, list[RustImportResolutionRecord]] = {}
            for resolution in self.import_resolutions:
                import_resolutions_by_target_file_id.setdefault(resolution.target_file_id, []).append(resolution)
            self._import_resolutions_by_target_file_id = import_resolutions_by_target_file_id
        return self._import_resolutions_by_target_file_id.get(file_id, [])

    def references_to_symbol(self, symbol_id: int) -> list[RustReferenceRecord]:
        if self._references_by_target_symbol_id is None:
            references_by_target_symbol_id: dict[int, list[RustReferenceRecord]] = {}
            for reference in self.references:
                references_by_target_symbol_id.setdefault(reference.target_symbol_id, []).append(reference)
            self._references_by_target_symbol_id = references_by_target_symbol_id
        return self._references_by_target_symbol_id.get(symbol_id, [])

    def references_from_symbol(self, symbol_id: int) -> list[RustReferenceRecord]:
        if self._references_by_source_symbol_id is None:
            references_by_source_symbol_id: dict[int, list[RustReferenceRecord]] = {}
            for reference in self.references:
                if reference.source_symbol_id is not None:
                    references_by_source_symbol_id.setdefault(reference.source_symbol_id, []).append(reference)
            self._references_by_source_symbol_id = references_by_source_symbol_id
        return self._references_by_source_symbol_id.get(symbol_id, [])

    def references_for_import(self, import_id: int) -> list[RustReferenceRecord]:
        if self._references_by_import_id is None:
            references_by_import_id: dict[int, list[RustReferenceRecord]] = {}
            for reference in self.references:
                if reference.import_id is not None:
                    references_by_import_id.setdefault(reference.import_id, []).append(reference)
            self._references_by_import_id = references_by_import_id
        return self._references_by_import_id.get(import_id, [])

    def dependencies_from_symbol(self, symbol_id: int) -> list[RustDependencyRecord]:
        if self._dependencies_by_source_symbol_id is None:
            dependencies_by_source_symbol_id: dict[int, list[RustDependencyRecord]] = {}
            for dependency in self.dependencies:
                dependencies_by_source_symbol_id.setdefault(dependency.source_symbol_id, []).append(dependency)
            self._dependencies_by_source_symbol_id = dependencies_by_source_symbol_id
        return self._dependencies_by_source_symbol_id.get(symbol_id, [])

    def dependencies_to_symbol(self, symbol_id: int) -> list[RustDependencyRecord]:
        if self._dependencies_by_target_symbol_id is None:
            dependencies_by_target_symbol_id: dict[int, list[RustDependencyRecord]] = {}
            for dependency in self.dependencies:
                dependencies_by_target_symbol_id.setdefault(dependency.target_symbol_id, []).append(dependency)
            self._dependencies_by_target_symbol_id = dependencies_by_target_symbol_id
        return self._dependencies_by_target_symbol_id.get(symbol_id, [])

    def to_json(self) -> str:
        return str(self.index.to_json())


@dataclass(frozen=True)
class _RustCompatTreeNode:
    range: RustSourceRange
    kind_id: int

    @property
    def start_byte(self) -> int:
        return self.range.start_byte

    @property
    def end_byte(self) -> int:
        return self.range.end_byte

    @property
    def start_point(self) -> tuple[int, int]:
        return (self.range.start_row, self.range.start_column)

    @property
    def end_point(self) -> tuple[int, int]:
        return (self.range.end_row, self.range.end_column)


@dataclass(frozen=True)
class RustCompactName:
    source: str

    def __str__(self) -> str:
        return self.source


@dataclass(frozen=True)
class RustCompactReferenceMatch:
    backend: RustIndexBackend
    record: RustReferenceRecord

    @property
    def source(self) -> str:
        return self.record.name

    @property
    def file(self) -> RustCompactFile:
        file = self.backend.file_handle_by_id(self.record.source_file_id)
        if file is None:
            msg = f"Rust compact reference {self.record.id} references missing file {self.record.source_file_id}"
            raise RuntimeError(msg)
        return file

    @property
    def filepath(self) -> str:
        return self.file.filepath

    @property
    def range(self) -> RustSourceRange:
        return self.record.range

    @property
    def ts_node(self) -> _RustCompatTreeNode:
        return _RustCompatTreeNode(self.record.range, int(NodeType.SYMBOL))

    @property
    def start_byte(self) -> int:
        return self.record.range.start_byte

    @property
    def end_byte(self) -> int:
        return self.record.range.end_byte

    @property
    def start_point(self) -> tuple[int, int]:
        return (self.record.range.start_row, self.record.range.start_column)

    @property
    def end_point(self) -> tuple[int, int]:
        return (self.record.range.end_row, self.record.range.end_column)


@dataclass(frozen=True)
class RustCompactUsage:
    backend: RustIndexBackend
    record: RustReferenceRecord

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RustCompactUsage) and self.backend is other.backend and self.record.id == other.record.id

    def __hash__(self) -> int:
        return hash(("rust-compact-usage", id(self.backend), self.record.id))

    @property
    def match(self) -> RustCompactReferenceMatch:
        return RustCompactReferenceMatch(self.backend, self.record)

    @property
    def usage_symbol(self) -> RustCompactSymbol | RustCompactFile:
        if self.record.source_symbol_id is not None:
            symbol = self.backend.symbol_handle_by_id(self.record.source_symbol_id)
            if symbol is None:
                msg = f"Rust compact reference {self.record.id} references missing source symbol {self.record.source_symbol_id}"
                raise RuntimeError(msg)
            return symbol
        file = self.backend.file_handle_by_id(self.record.source_file_id)
        if file is None:
            msg = f"Rust compact reference {self.record.id} references missing source file {self.record.source_file_id}"
            raise RuntimeError(msg)
        return file

    @property
    def imported_by(self) -> RustCompactImport | None:
        if self.record.import_id is None:
            return None
        return self.backend.import_handle_by_id(self.record.import_id)

    @property
    def usage_type(self) -> UsageType:
        return UsageType.DIRECT

    @property
    def kind(self) -> UsageKind:
        return UsageKind.BODY

    @property
    def file(self) -> RustCompactFile:
        return self.match.file

    @property
    def filepath(self) -> str:
        return self.match.filepath


def _usage_types_include_direct(usage_types: UsageType | None) -> bool:
    return usage_types is None or bool(usage_types & UsageType.DIRECT)


def _byte_range_bounds(range_like: Any) -> tuple[int, int]:
    if isinstance(range_like, dict):
        start_byte = range_like["start_byte"]
        end_byte = range_like["end_byte"]
    else:
        start_byte = getattr(range_like, "start_byte")
        end_byte = getattr(range_like, "end_byte")

    start = int(start_byte)
    end = int(end_byte)
    if end < start:
        msg = f"Invalid byte range: end_byte {end} is before start_byte {start}"
        raise ValueError(msg)
    return start, end


def _ranges_overlap(record_range: RustSourceRange, query_start: int, query_end: int) -> bool:
    if query_start == query_end:
        return record_range.start_byte <= query_start < record_range.end_byte
    return record_range.start_byte < query_end and query_start < record_range.end_byte


def _python_import_module_name_for_filepath(filepath: str, base_path: str | None = None) -> str:
    module = filepath.replace("\\", "/")
    if module.endswith(".py"):
        module = module[:-3]
    if module.endswith("__init__"):
        module = "/".join(module.split("/")[:-1])
    module = module.replace("/", ".")

    if base_path:
        normalized_base_path = base_path.replace("\\", "/").replace("/", ".").rstrip(".")
        if normalized_base_path and module.startswith(normalized_base_path):
            module = module.replace(f"{normalized_base_path}.", "", 1)

    if module.startswith("src."):
        module = module.replace("src.", "", 1)
    return module


class RustCompactHandle:
    node_type: NodeType

    def __init__(self, backend: RustIndexBackend, node_id: int, source_range: RustSourceRange) -> None:
        self.backend = backend
        self.ctx: CodebaseContext | None = None
        self.node_id = node_id
        self.ts_node = _RustCompatTreeNode(source_range, int(self.node_type))

    def __hash__(self) -> int:
        return hash((self.node_type, self.node_id))

    @property
    def start_byte(self) -> int:
        return self.ts_node.start_byte

    @property
    def end_byte(self) -> int:
        return self.ts_node.end_byte

    @property
    def start_point(self) -> tuple[int, int]:
        return self.ts_node.start_point

    @property
    def end_point(self) -> tuple[int, int]:
        return self.ts_node.end_point

    @property
    def range(self) -> RustSourceRange:
        return self.ts_node.range

    def _unsupported(self, method: str) -> RuntimeError:
        return RuntimeError(f"{method} is not supported by the compact Rust handle yet")


class RustCompactFile(RustCompactHandle):
    node_type = NodeType.FILE

    def __init__(self, backend: RustIndexBackend, record: RustFileRecord) -> None:
        self.record = record
        super().__init__(backend, record.id, record.root_range)
        self.file_path = record.path
        self.filepath = record.path
        self.path = backend.repo_path / record.path
        self.name = self.path.stem
        self._binary = False

    def __repr__(self) -> str:
        return f"RustCompactFile(filepath={self.filepath!r})"

    @property
    def file(self) -> RustCompactFile:
        return self

    @property
    def parent_symbol(self) -> RustCompactFile:
        return self

    @property
    def module_name(self) -> str | None:
        return self.record.module_name

    @property
    def import_module_name(self) -> str:
        return self.record.module_name or self.get_import_module_name_for_file(self.filepath, self.ctx)

    def get_import_module_name_for_file(self, filepath: str, ctx: CodebaseContext | None = None) -> str:
        base_path = None
        if ctx is not None and getattr(ctx, "projects", None):
            base_path = getattr(ctx.projects[0], "base_path", None)
        return _python_import_module_name_for_filepath(filepath, base_path)

    def get_import_string(self, alias: str | None = None, module: str | None = None, import_type: ImportType = ImportType.UNKNOWN, is_type_import: bool = False) -> str:
        symbol_name = self.name
        import_module = module if module is not None else self.import_module_name
        if f".{symbol_name}" in import_module:
            import_module = import_module.replace(f".{symbol_name}", "")
        if symbol_name == import_module:
            import_module = "."

        if import_type == ImportType.WILDCARD:
            return f"from {import_module} import * as {symbol_name}"
        if alias is not None and alias != self.name:
            return f"from {import_module} import {symbol_name} as {alias}"
        return f"from {import_module} import {symbol_name}"

    @property
    def extension(self) -> str:
        return self.path.suffix

    @property
    def is_binary(self) -> bool:
        return self._binary

    @property
    def content_bytes(self) -> bytes:
        return self.path.read_bytes()

    @property
    def content(self) -> str:
        return self.content_bytes.decode("utf-8")

    @property
    def source(self) -> str:
        return self.content

    @property
    def imports(self) -> list[RustCompactImport]:
        return self.backend.imports_for_file(self.record.id)

    @property
    def import_statements(self) -> list[RustCompactImport]:
        import_statements: list[RustCompactImport] = []
        seen: set[tuple[int, int, str]] = set()
        for import_handle in self.imports:
            key = (import_handle.start_byte, import_handle.end_byte, import_handle.source)
            if key in seen:
                continue
            seen.add(key)
            import_statements.append(import_handle.import_statement)
        return import_statements

    def get_nodes(self, *, sort_by_id: bool = False, sort: bool = True) -> list[RustCompactImport | RustCompactSymbol]:
        nodes: list[RustCompactImport | RustCompactSymbol] = [*self.imports, *self.backend.symbols_for_file(self.record.id)]
        if not sort:
            return nodes

        if sort_by_id:
            return sorted(nodes, key=lambda node: (node.node_id, int(node.node_type), node.start_byte, node.end_byte))
        return sorted(nodes, key=lambda node: (node.start_byte, node.end_byte, int(node.node_type), node.node_id))

    def find_by_byte_range(self, range: Any) -> list[RustCompactImport | RustCompactSymbol]:
        start_byte, end_byte = _byte_range_bounds(range)
        return [node for node in self.get_nodes() if _ranges_overlap(node.range, start_byte, end_byte)]

    @property
    def valid_symbol_names(self) -> dict[str, RustCompactImport | RustCompactSymbol]:
        valid_symbol_names: dict[str, RustCompactImport | RustCompactSymbol] = {}
        for symbol in self.symbols:
            valid_symbol_names[symbol.full_name] = symbol
        for import_handle in self.imports:
            for name, destination in import_handle.names:
                if name is not None:
                    valid_symbol_names[name] = destination
        return valid_symbol_names

    @property
    def valid_import_names(self) -> dict[str, RustCompactImport | RustCompactSymbol]:
        return self.valid_symbol_names

    def resolve_name(self, name: str, start_byte: int | None = None, strict: bool = True) -> Any:
        resolved = self.valid_symbol_names.get(name)
        if resolved is None:
            return

        if start_byte is not None and resolved.end_byte > start_byte:
            for symbol in reversed(self.symbols):
                symbol_boundary = symbol.start_byte if symbol.symbol_type in {SymbolType.Class, SymbolType.Function} else symbol.end_byte
                if symbol.name == name and symbol_boundary <= start_byte:
                    yield symbol
                    return
            if not strict:
                return
            return

        yield resolved

    def resolve_attribute(self, name: str) -> RustCompactImport | RustCompactSymbol | None:
        return self.valid_import_names.get(name)

    def get_node_by_name(self, name: str) -> RustCompactImport | RustCompactSymbol | None:
        symbol = self.get_symbol(name)
        if symbol is not None:
            return symbol
        return self.get_import(name)

    @proxy_property
    def symbols(self, nested: bool = False) -> list[RustCompactSymbol]:
        if nested:
            return self.backend.symbols_for_file(self.record.id)
        return [symbol for symbol in self.backend.symbols_for_file(self.record.id) if symbol.is_top_level]

    @property
    def global_vars(self) -> list[RustCompactSymbol]:
        return [symbol for symbol in self.symbols if symbol.symbol_type == SymbolType.GlobalVar]

    @property
    def classes(self) -> list[RustCompactSymbol]:
        return [symbol for symbol in self.symbols if symbol.symbol_type == SymbolType.Class]

    @property
    def functions(self) -> list[RustCompactSymbol]:
        return [symbol for symbol in self.symbols if symbol.symbol_type == SymbolType.Function]

    @property
    def symbols_sorted_topologically(self) -> list[RustCompactSymbol]:
        symbols = self.symbols
        symbols_by_id = {symbol.record.id: symbol for symbol in symbols}
        original_index = {symbol.record.id: index for index, symbol in enumerate(symbols)}
        outgoing: dict[int, list[int]] = {symbol.record.id: [] for symbol in symbols}
        indegrees: dict[int, int] = {symbol.record.id: 0 for symbol in symbols}

        for symbol in symbols:
            for dependency in self.backend.dependencies_from_symbol(symbol.record.id):
                if dependency.target_symbol_id not in symbols_by_id:
                    continue
                outgoing[symbol.record.id].append(dependency.target_symbol_id)
                indegrees[dependency.target_symbol_id] += 1

        ready = sorted((symbol_id for symbol_id, indegree in indegrees.items() if indegree == 0), key=original_index.__getitem__)
        ordered_ids: list[int] = []
        while ready:
            symbol_id = ready.pop(0)
            ordered_ids.append(symbol_id)
            for target_symbol_id in sorted(outgoing[symbol_id], key=original_index.__getitem__):
                indegrees[target_symbol_id] -= 1
                if indegrees[target_symbol_id] == 0:
                    ready.append(target_symbol_id)
                    ready.sort(key=original_index.__getitem__)

        if len(ordered_ids) != len(symbols):
            ordered_set = set(ordered_ids)
            ordered_ids.extend(symbol.record.id for symbol in symbols if symbol.record.id not in ordered_set)

        return [symbols_by_id[symbol_id] for symbol_id in ordered_ids]

    def get_symbol(self, name: str) -> RustCompactSymbol | None:
        return next((symbol for symbol in self.symbols if symbol.name == name), None)

    def get_global_var(self, name: str) -> RustCompactSymbol | None:
        return next((symbol for symbol in self.global_vars if symbol.name == name), None)

    def get_class(self, name: str) -> RustCompactSymbol | None:
        return next((symbol for symbol in self.classes if symbol.name == name), None)

    def get_function(self, name: str) -> RustCompactSymbol | None:
        return next((symbol for symbol in self.functions if symbol.name == name), None)

    def has_import(self, symbol_alias: str) -> bool:
        return self.get_import(symbol_alias) is not None

    def get_import(self, symbol_alias: str) -> RustCompactImport | None:
        return next((import_handle for import_handle in self.imports if import_handle.matches_lookup(symbol_alias)), None)

    @property
    def inbound_imports(self) -> list[RustCompactImport]:
        import_handles: list[RustCompactImport] = []
        seen: set[RustCompactImport] = set()
        for resolution in self.backend.import_resolutions_to_file(self.record.id):
            import_handle = self.backend.import_handle_by_id(resolution.import_id)
            if import_handle is None or import_handle in seen:
                continue
            seen.add(import_handle)
            import_handles.append(import_handle)
        return sorted(import_handles, key=lambda import_handle: (import_handle.filepath, import_handle.start_byte))

    @property
    def importers(self) -> list[RustCompactImport]:
        import_handles: list[RustCompactImport] = []
        seen: set[RustCompactImport] = set()
        for resolution in self.backend.import_resolutions_to_file(self.record.id):
            if resolution.target_symbol_id is not None:
                continue
            import_handle = self.backend.import_handle_by_id(resolution.import_id)
            if import_handle is None or import_handle in seen:
                continue
            seen.add(import_handle)
            import_handles.append(import_handle)
        return sorted(import_handles, key=lambda import_handle: (import_handle.filepath, import_handle.start_byte))


class RustCompactSymbol(RustCompactHandle):
    node_type = NodeType.SYMBOL

    def __init__(self, backend: RustIndexBackend, record: RustSymbolRecord) -> None:
        self.record = record
        super().__init__(backend, record.id, record.range)
        self.name = record.name
        self._name_node = RustCompactName(record.name)
        self.is_top_level = record.is_top_level

    def __repr__(self) -> str:
        return f"RustCompactSymbol(name={self.name!r}, filepath={self.filepath!r})"

    @property
    def symbol_type(self) -> SymbolType:
        return {
            "class": SymbolType.Class,
            "function": SymbolType.Function,
            "global_variable": SymbolType.GlobalVar,
        }[self.record.kind]

    @property
    def file(self) -> RustCompactFile:
        file = self.backend.file_handle_by_id(self.record.file_id)
        if file is None:
            msg = f"Rust compact symbol {self.record.id} references missing file {self.record.file_id}"
            raise RuntimeError(msg)
        return file

    @property
    def filepath(self) -> str:
        return self.file.filepath

    @property
    def full_name(self) -> str:
        return self.name

    @property
    def source(self) -> str:
        return self.file.content_bytes[self.start_byte : self.end_byte].decode("utf-8")

    @property
    def extended_source(self) -> str:
        return self.source

    @property
    def extended_nodes(self) -> list[RustCompactSymbol]:
        return [self]

    @proxy_property
    def dependencies(self, usage_types: UsageType | None = UsageType.DIRECT, max_depth: int | None = None) -> list[object]:
        if not _usage_types_include_direct(usage_types):
            return []

        dependencies = self._direct_dependencies()
        if max_depth is None or max_depth <= 1:
            return dependencies

        seen = set(dependencies)
        frontier = list(dependencies)
        for _ in range(1, max_depth):
            next_frontier: list[RustCompactSymbol] = []
            for dependency in frontier:
                if not isinstance(dependency, RustCompactSymbol):
                    continue
                for nested_dependency in dependency._direct_dependencies():
                    if nested_dependency in seen:
                        continue
                    seen.add(nested_dependency)
                    dependencies.append(nested_dependency)
                    next_frontier.append(nested_dependency)
            if not next_frontier:
                break
            frontier = next_frontier
        return dependencies

    def _direct_dependencies(self) -> list[RustCompactSymbol]:
        dependencies: list[RustCompactSymbol] = []
        seen: set[RustCompactSymbol] = set()
        for dependency in self.backend.dependencies_from_symbol(self.record.id):
            target = self.backend.symbol_handle_by_id(dependency.target_symbol_id)
            if target is None or target in seen:
                continue
            seen.add(target)
            dependencies.append(target)
        return dependencies

    @proxy_property
    def usages(self, usage_types: UsageType | None = None) -> list[RustCompactUsage]:
        if not _usage_types_include_direct(usage_types):
            return []

        usages = [RustCompactUsage(self.backend, reference) for reference in self.backend.references_to_symbol(self.record.id)]
        return sorted(dict.fromkeys(usages), key=lambda usage: (usage.file.filepath, usage.match.start_byte), reverse=True)

    @proxy_property
    def symbol_usages(self, usage_types: UsageType | None = None) -> list[object]:
        if not _usage_types_include_direct(usage_types):
            return []

        symbol_usages: list[object] = []
        seen: set[object] = set()
        for usage in self.usages(usage_types=usage_types):
            usage_symbol = usage.usage_symbol.parent_symbol
            if usage_symbol in seen:
                continue
            seen.add(usage_symbol)
            symbol_usages.append(usage_symbol)
        return symbol_usages

    @property
    def descendant_symbols(self) -> list[RustCompactSymbol]:
        descendants = [self]
        for child in self.child_symbols:
            descendants.extend(child.descendant_symbols)
        return descendants

    @property
    def child_symbols(self) -> list[RustCompactSymbol]:
        return self.backend.symbols_for_parent(self.record.id)

    @property
    def function_calls(self) -> list[object]:
        return []

    @property
    def is_exported(self) -> bool:
        return False

    @property
    def parent_symbol(self) -> RustCompactSymbol:
        if self.record.parent_symbol_id is None:
            return self
        parent = self.backend.symbol_handle_by_id(self.record.parent_symbol_id)
        return self if parent is None else parent

    def get_name(self) -> str:
        return self.name

    def get_import_string(self, alias: str | None = None, module: str | None = None, import_type: ImportType = ImportType.UNKNOWN, is_type_import: bool = False) -> str:
        import_module = module if module is not None else self.file.import_module_name
        if import_type == ImportType.WILDCARD:
            file_as_module = self.file.name
            return f"from {import_module} import * as {file_as_module}"
        if alias is not None and alias != self.name:
            return f"from {import_module} import {self.name} as {alias}"
        return f"from {import_module} import {self.name}"


class RustCompactImport(RustCompactHandle):
    node_type = NodeType.IMPORT

    def __init__(self, backend: RustIndexBackend, record: RustImportRecord) -> None:
        self.record = record
        super().__init__(backend, record.id, record.range)
        self.module = RustCompactName(self._module_source()) if self._module_source() is not None else None
        self.symbol_name = RustCompactName(record.name) if record.name is not None else None
        alias = record.alias or record.name
        self.alias = RustCompactName(alias) if alias is not None else None
        self.import_type = self._import_type()
        self.import_statement = self

    def __repr__(self) -> str:
        return f"RustCompactImport(source={self.source!r}, filepath={self.filepath!r})"

    @property
    def file(self) -> RustCompactFile:
        file = self.backend.file_handle_by_id(self.record.file_id)
        if file is None:
            msg = f"Rust compact import {self.record.id} references missing file {self.record.file_id}"
            raise RuntimeError(msg)
        return file

    @property
    def filepath(self) -> str:
        return self.file.filepath

    @property
    def source(self) -> str:
        return self.file.content_bytes[self.start_byte : self.end_byte].decode("utf-8")

    @property
    def name(self) -> str | None:
        return self.alias.source if self.alias is not None else None

    @property
    def names(self) -> list[tuple[str | None, RustCompactImport]]:
        return [(self.name, self)]

    @property
    def import_specifier(self) -> str | None:
        if self.symbol_name is not None:
            return self.symbol_name.source
        return self.module.source if self.module is not None else None

    @property
    def from_file(self) -> RustCompactFile | None:
        resolution = self.backend.import_resolution_for_import(self.record.id)
        if resolution is None:
            return None
        return self.backend.file_handle_by_id(resolution.target_file_id)

    @property
    def to_file(self) -> RustCompactFile:
        return self.file

    @property
    def imported_symbol(self) -> RustCompactSymbol | RustCompactFile | None:
        resolution = self.backend.import_resolution_for_import(self.record.id)
        if resolution is None:
            return None
        if resolution.target_symbol_id is not None:
            return self.backend.symbol_handle_by_id(resolution.target_symbol_id)
        return self.backend.file_handle_by_id(resolution.target_file_id)

    @property
    def resolved_symbol(self) -> RustCompactSymbol | RustCompactFile | None:
        return self.imported_symbol

    @property
    def imported_exports(self) -> list[RustCompactSymbol | RustCompactFile]:
        imported = self.imported_symbol
        if imported is None:
            return []
        if not self.is_module_import():
            return [imported]
        if isinstance(imported, RustCompactFile):
            return [*imported.symbols, *imported.imports]
        return [imported]

    def resolve_attribute(self, attribute: str) -> RustCompactImport | RustCompactSymbol | RustCompactFile | None:
        imported = self.imported_symbol
        if isinstance(imported, RustCompactFile):
            return imported.valid_import_names.get(attribute)
        return None

    def get_import_string(self, alias: str | None = None, module: str | None = None, import_type: ImportType = ImportType.UNKNOWN, is_type_import: bool = False) -> str:
        import_module = module if module is not None else self.file.import_module_name
        if import_type == ImportType.WILDCARD:
            file_as_module = self.file.name
            return f"from {import_module} import * as {file_as_module}"
        if alias is not None and alias != self.name:
            return f"from {import_module} import {self.name} as {alias}"
        return f"from {import_module} import {self.name}"

    @proxy_property
    def usages(self, usage_types: UsageType | None = None) -> list[RustCompactUsage]:
        if not _usage_types_include_direct(usage_types):
            return []

        usages = [RustCompactUsage(self.backend, reference) for reference in self.backend.references_for_import(self.record.id)]
        return sorted(dict.fromkeys(usages), key=lambda usage: (usage.file.filepath, usage.match.start_byte), reverse=True)

    @proxy_property
    def symbol_usages(self, usage_types: UsageType | None = None) -> list[object]:
        if not _usage_types_include_direct(usage_types):
            return []

        symbol_usages: list[object] = []
        seen: set[object] = set()
        for usage in self.usages(usage_types=usage_types):
            usage_symbol = usage.usage_symbol.parent_symbol
            if usage_symbol in seen:
                continue
            seen.add(usage_symbol)
            symbol_usages.append(usage_symbol)
        return symbol_usages

    @property
    def namespace(self) -> str | None:
        if not self.is_module_import():
            return None
        return self.name

    @property
    def is_dynamic(self) -> bool:
        return False

    @property
    def is_reexport(self) -> bool:
        return False

    @property
    def parent_symbol(self) -> RustCompactImport:
        return self

    def is_aliased_import(self) -> bool:
        return self.record.alias is not None and self.record.alias != self.record.name

    def is_module_import(self) -> bool:
        return self.import_type in {ImportType.MODULE, ImportType.WILDCARD}

    def is_symbol_import(self) -> bool:
        return not self.is_module_import()

    def is_wildcard_import(self) -> bool:
        return self.import_type == ImportType.WILDCARD

    def matches_lookup(self, name_or_source: str) -> bool:
        return name_or_source in self._lookup_names()

    def _lookup_names(self) -> set[str]:
        names = {self.source}
        if self.name is not None:
            names.add(self.name)
        if self.module is not None:
            names.add(self.module.source)
        if self.symbol_name is not None:
            names.add(self.symbol_name.source)
        if self.import_specifier is not None:
            names.add(self.import_specifier)
        return names

    def _module_source(self) -> str | None:
        if self.record.kind == "import":
            return self.record.name
        return self.record.module

    def _import_type(self) -> ImportType:
        if self.record.name == "*":
            return ImportType.WILDCARD
        if self.record.kind == "import":
            return ImportType.MODULE
        if self.record.kind in {"from_import", "future_import"}:
            return ImportType.NAMED_EXPORT
        return ImportType.UNKNOWN
