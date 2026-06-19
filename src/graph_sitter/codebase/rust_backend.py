from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from graph_sitter.codebase.codebase_context import CodebaseContext

from graph_sitter._proxy import proxy_property
from graph_sitter.codebase.transactions import EditTransaction, InsertTransaction, RemoveTransaction
from graph_sitter.core.dataclasses.usage import UsageKind, UsageType
from graph_sitter.enums import ImportType, NodeType, SymbolType
from graph_sitter.shared.enums.programming_language import ProgrammingLanguage


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
class RustExternalModuleRecord:
    id: int
    import_id: int
    file_id: int
    module: str | None
    name: str
    alias: str | None
    range: RustSourceRange

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RustExternalModuleRecord:
        return cls(
            id=int(data["id"]),
            import_id=int(data["import_id"]),
            file_id=int(data["file_id"]),
            module=data["module"],
            name=str(data["name"]),
            alias=data["alias"],
            range=RustSourceRange.from_dict(data["range"]),
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
class RustExternalReferenceRecord:
    id: int
    source_file_id: int
    source_symbol_id: int | None
    import_id: int
    name: str
    range: RustSourceRange

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RustExternalReferenceRecord:
        source_symbol_id = data["source_symbol_id"]
        return cls(
            id=int(data["id"]),
            source_file_id=int(data["source_file_id"]),
            source_symbol_id=None if source_symbol_id is None else int(source_symbol_id),
            import_id=int(data["import_id"]),
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


@dataclass(frozen=True)
class RustSubclassRecord:
    id: int
    source_symbol_id: int
    target_symbol_id: int
    source_file_id: int
    target_file_id: int
    reference_id: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RustSubclassRecord:
        return cls(
            id=int(data["id"]),
            source_symbol_id=int(data["source_symbol_id"]),
            target_symbol_id=int(data["target_symbol_id"]),
            source_file_id=int(data["source_file_id"]),
            target_file_id=int(data["target_file_id"]),
            reference_id=int(data["reference_id"]),
        )


@dataclass(frozen=True)
class RustExportRecord:
    id: int
    file_id: int
    kind: str
    name: str | None
    local_name: str | None
    source_module: str | None
    symbol_id: int | None
    import_id: int | None
    range: RustSourceRange

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RustExportRecord:
        symbol_id = data["symbol_id"]
        import_id = data["import_id"]
        return cls(
            id=int(data["id"]),
            file_id=int(data["file_id"]),
            kind=str(data["kind"]),
            name=data["name"],
            local_name=data["local_name"],
            source_module=data["source_module"],
            symbol_id=None if symbol_id is None else int(symbol_id),
            import_id=None if import_id is None else int(import_id),
            range=RustSourceRange.from_dict(data["range"]),
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
    _external_modules: list[RustExternalModuleRecord] | None = None
    _exports: list[RustExportRecord] | None = None
    _references: list[RustReferenceRecord] | None = None
    _external_references: list[RustExternalReferenceRecord] | None = None
    _dependencies: list[RustDependencyRecord] | None = None
    _subclass_edges: list[RustSubclassRecord] | None = None
    _file_handles: list[RustCompactFile] | None = None
    _symbol_handles: list[RustCompactSymbol] | None = None
    _import_handles: list[RustCompactImport] | None = None
    _external_module_handles: list[RustCompactExternalModule] | None = None
    _export_handles: list[RustCompactExport] | None = None
    _file_handles_by_id: dict[int, RustCompactFile] | None = None
    _symbol_handles_by_id: dict[int, RustCompactSymbol] | None = None
    _import_handles_by_id: dict[int, RustCompactImport] | None = None
    _external_module_handles_by_import_id: dict[int, RustCompactExternalModule] | None = None
    _export_handles_by_id: dict[int, RustCompactExport] | None = None
    _symbols_by_file_id: dict[int, list[RustCompactSymbol]] | None = None
    _imports_by_file_id: dict[int, list[RustCompactImport]] | None = None
    _exports_by_file_id: dict[int, list[RustCompactExport]] | None = None
    _import_resolutions_by_import_id: dict[int, RustImportResolutionRecord] | None = None
    _import_resolutions_by_target_file_id: dict[int, list[RustImportResolutionRecord]] | None = None
    _references_by_target_symbol_id: dict[int, list[RustReferenceRecord]] | None = None
    _references_by_source_symbol_id: dict[int, list[RustReferenceRecord]] | None = None
    _references_by_import_id: dict[int, list[RustReferenceRecord]] | None = None
    _references_by_id: dict[int, RustReferenceRecord] | None = None
    _external_references_by_source_symbol_id: dict[int, list[RustExternalReferenceRecord]] | None = None
    _external_references_by_import_id: dict[int, list[RustExternalReferenceRecord]] | None = None
    _dependencies_by_source_symbol_id: dict[int, list[RustDependencyRecord]] | None = None
    _dependencies_by_target_symbol_id: dict[int, list[RustDependencyRecord]] | None = None
    _subclass_edges_by_source_symbol_id: dict[int, list[RustSubclassRecord]] | None = None
    _subclass_edges_by_target_symbol_id: dict[int, list[RustSubclassRecord]] | None = None
    _symbols_by_parent_symbol_id: dict[int, list[RustCompactSymbol]] | None = None
    _ctx: CodebaseContext | None = None

    @classmethod
    def build(cls, repo_path: str | Path, file_paths: Sequence[str] | None = None, *, language: ProgrammingLanguage = ProgrammingLanguage.PYTHON) -> RustIndexBackend:
        path = Path(repo_path).resolve()
        try:
            extension = import_module("graph_sitter_py")
        except ImportError as error:
            message = "Rust graph backend extension `graph_sitter_py` is not installed"
            raise RustBackendUnavailableError(message) from error

        try:
            if language is ProgrammingLanguage.PYTHON:
                if file_paths is None:
                    index = extension.index_python_path(str(path))
                else:
                    index = extension.index_python_paths(str(path), list(file_paths))
            elif language is ProgrammingLanguage.TYPESCRIPT:
                if file_paths is None:
                    index = extension.index_typescript_path(str(path))
                else:
                    index = extension.index_typescript_paths(str(path), list(file_paths))
            else:
                message = f"Rust graph backend does not support {language}"
                raise RustBackendUnavailableError(message)
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
    def external_modules(self) -> list[RustExternalModuleRecord]:
        if self._external_modules is None:
            external_modules_json = getattr(self.index, "external_modules_json", None)
            if external_modules_json is None:
                self._external_modules = []
            else:
                self._external_modules = [RustExternalModuleRecord.from_dict(record) for record in json.loads(external_modules_json())]
        return self._external_modules

    @property
    def exports(self) -> list[RustExportRecord]:
        if self._exports is None:
            exports_json = getattr(self.index, "exports_json", None)
            if exports_json is None:
                self._exports = []
            else:
                self._exports = [RustExportRecord.from_dict(record) for record in json.loads(exports_json())]
        return self._exports

    @property
    def references(self) -> list[RustReferenceRecord]:
        if self._references is None:
            self._references = [RustReferenceRecord.from_dict(record) for record in json.loads(self.index.references_json())]
        return self._references

    @property
    def external_references(self) -> list[RustExternalReferenceRecord]:
        if self._external_references is None:
            external_references_json = getattr(self.index, "external_references_json", None)
            if external_references_json is None:
                self._external_references = []
            else:
                self._external_references = [RustExternalReferenceRecord.from_dict(record) for record in json.loads(external_references_json())]
        return self._external_references

    @property
    def dependencies(self) -> list[RustDependencyRecord]:
        if self._dependencies is None:
            self._dependencies = [RustDependencyRecord.from_dict(record) for record in json.loads(self.index.dependencies_json())]
        return self._dependencies

    @property
    def subclass_edges(self) -> list[RustSubclassRecord]:
        if self._subclass_edges is None:
            subclass_edges_json = getattr(self.index, "subclass_edges_json", None)
            if subclass_edges_json is None:
                self._subclass_edges = []
            else:
                self._subclass_edges = [RustSubclassRecord.from_dict(record) for record in json.loads(subclass_edges_json())]
        return self._subclass_edges

    @property
    def file_handles(self) -> list[RustCompactFile]:
        if self._file_handles is None:
            self._file_handles = [RustCompactFile(self, record) for record in self.files]
            if self._ctx is not None:
                for file in self._file_handles:
                    file.ctx = self._ctx
        return self._file_handles

    @property
    def symbol_handles(self) -> list[RustCompactSymbol]:
        if self._symbol_handles is None:
            self._symbol_handles = [RustCompactSymbol(self, record) for record in self.symbols]
            if self._ctx is not None:
                for symbol in self._symbol_handles:
                    symbol.ctx = self._ctx
        return self._symbol_handles

    @property
    def import_handles(self) -> list[RustCompactImport]:
        if self._import_handles is None:
            self._import_handles = [RustCompactImport(self, record) for record in self.imports]
            if self._ctx is not None:
                for import_handle in self._import_handles:
                    import_handle.ctx = self._ctx
        return self._import_handles

    @property
    def external_module_handles(self) -> list[RustCompactExternalModule]:
        if self._external_module_handles is None:
            self._external_module_handles = [RustCompactExternalModule(self, record) for record in self.external_modules]
            if self._ctx is not None:
                for external_module in self._external_module_handles:
                    external_module.ctx = self._ctx
        return self._external_module_handles

    @property
    def export_handles(self) -> list[RustCompactExport]:
        if self._export_handles is None:
            self._export_handles = [RustCompactExport(self, record) for record in self.exports]
            if self._ctx is not None:
                for export_handle in self._export_handles:
                    export_handle.ctx = self._ctx
        return self._export_handles

    def bind_context(self, ctx: CodebaseContext) -> None:
        self._ctx = ctx
        for handles in (self._file_handles, self._symbol_handles, self._import_handles, self._external_module_handles, self._export_handles):
            if handles is None:
                continue
            for handle in handles:
                handle.ctx = ctx

    def register_added_file(self, filepath: str, content: str = "") -> RustCompactFile:
        relative_path = self._normalize_relative_path(filepath)
        if existing := self.get_file_handle(relative_path):
            return existing

        content_bytes = content.encode("utf-8")
        record = RustFileRecord(
            id=max((file.id for file in self.files), default=-1) + 1,
            path=relative_path,
            module_name=_python_import_module_name_for_filepath(relative_path) if relative_path.endswith(".py") else None,
            byte_len=len(content_bytes),
            line_count=_line_count(content),
            has_error=False,
            root_range=_source_range_for_content(content),
        )
        self.files.append(record)
        file = RustCompactFile(self, record)
        file.ctx = self._ctx
        self.file_handles.append(file)
        self._file_handles_by_id = None
        self._symbols_by_file_id = None
        self._imports_by_file_id = None
        return file

    def unregister_file(self, file_id: int) -> None:
        self._files = [file for file in self.files if file.id != file_id]
        self._file_handles = [file for file in self.file_handles if file.record.id != file_id]
        self._symbols = [symbol for symbol in self.symbols if symbol.file_id != file_id]
        self._imports = [import_record for import_record in self.imports if import_record.file_id != file_id]
        self._external_modules = [external_module for external_module in self.external_modules if external_module.file_id != file_id]
        self._exports = [export for export in self.exports if export.file_id != file_id]
        self._external_references = [reference for reference in self.external_references if reference.source_file_id != file_id]
        self._subclass_edges = [edge for edge in self.subclass_edges if edge.source_file_id != file_id and edge.target_file_id != file_id]
        self._file_handles_by_id = None
        self._symbol_handles = None
        self._import_handles = None
        self._external_module_handles = None
        self._export_handles = None
        self._external_module_handles_by_import_id = None
        self._export_handles_by_id = None
        self._symbols_by_file_id = None
        self._imports_by_file_id = None
        self._exports_by_file_id = None
        self._import_resolutions_by_import_id = None
        self._import_resolutions_by_target_file_id = None
        self._references_by_target_symbol_id = None
        self._references_by_source_symbol_id = None
        self._references_by_import_id = None
        self._references_by_id = None
        self._external_references_by_source_symbol_id = None
        self._external_references_by_import_id = None
        self._dependencies_by_source_symbol_id = None
        self._dependencies_by_target_symbol_id = None
        self._subclass_edges_by_source_symbol_id = None
        self._subclass_edges_by_target_symbol_id = None
        self._symbols_by_parent_symbol_id = None

    def _normalize_relative_path(self, filepath: str) -> str:
        path = Path(filepath.replace("\\", "/"))
        if path.is_absolute():
            path = path.resolve().relative_to(self.repo_path)
        normalized = path.as_posix()
        if normalized.startswith("./"):
            normalized = normalized[2:]
        return normalized

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

    def exports_for_file(self, file_id: int) -> list[RustCompactExport]:
        if self._exports_by_file_id is None:
            exports_by_file_id: dict[int, list[RustCompactExport]] = {}
            for export_handle in self.export_handles:
                exports_by_file_id.setdefault(export_handle.record.file_id, []).append(export_handle)
            self._exports_by_file_id = exports_by_file_id
        return self._exports_by_file_id.get(file_id, [])

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

    def external_module_for_import(self, import_id: int) -> RustCompactExternalModule | None:
        if self._external_module_handles_by_import_id is None:
            self._external_module_handles_by_import_id = {external_module.record.import_id: external_module for external_module in self.external_module_handles}
        return self._external_module_handles_by_import_id.get(import_id)

    def export_handle_by_id(self, export_id: int) -> RustCompactExport | None:
        if self._export_handles_by_id is None:
            self._export_handles_by_id = {export_handle.record.id: export_handle for export_handle in self.export_handles}
        return self._export_handles_by_id.get(export_id)

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

    def reference_by_id(self, reference_id: int) -> RustReferenceRecord | None:
        if self._references_by_id is None:
            self._references_by_id = {reference.id: reference for reference in self.references}
        return self._references_by_id.get(reference_id)

    def external_references_from_symbol(self, symbol_id: int) -> list[RustExternalReferenceRecord]:
        if self._external_references_by_source_symbol_id is None:
            references_by_source_symbol_id: dict[int, list[RustExternalReferenceRecord]] = {}
            for reference in self.external_references:
                if reference.source_symbol_id is not None:
                    references_by_source_symbol_id.setdefault(reference.source_symbol_id, []).append(reference)
            self._external_references_by_source_symbol_id = references_by_source_symbol_id
        return self._external_references_by_source_symbol_id.get(symbol_id, [])

    def external_references_for_import(self, import_id: int) -> list[RustExternalReferenceRecord]:
        if self._external_references_by_import_id is None:
            references_by_import_id: dict[int, list[RustExternalReferenceRecord]] = {}
            for reference in self.external_references:
                references_by_import_id.setdefault(reference.import_id, []).append(reference)
            self._external_references_by_import_id = references_by_import_id
        return self._external_references_by_import_id.get(import_id, [])

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

    def subclass_edges_from_symbol(self, symbol_id: int) -> list[RustSubclassRecord]:
        if self._subclass_edges_by_source_symbol_id is None:
            subclass_edges_by_source_symbol_id: dict[int, list[RustSubclassRecord]] = {}
            for edge in self.subclass_edges:
                subclass_edges_by_source_symbol_id.setdefault(edge.source_symbol_id, []).append(edge)
            self._subclass_edges_by_source_symbol_id = subclass_edges_by_source_symbol_id
        return self._subclass_edges_by_source_symbol_id.get(symbol_id, [])

    def subclass_edges_to_symbol(self, symbol_id: int) -> list[RustSubclassRecord]:
        if self._subclass_edges_by_target_symbol_id is None:
            subclass_edges_by_target_symbol_id: dict[int, list[RustSubclassRecord]] = {}
            for edge in self.subclass_edges:
                subclass_edges_by_target_symbol_id.setdefault(edge.target_symbol_id, []).append(edge)
            self._subclass_edges_by_target_symbol_id = subclass_edges_by_target_symbol_id
        return self._subclass_edges_by_target_symbol_id.get(symbol_id, [])

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

    @property
    def _source(self) -> str:
        return self.source

    @property
    def name(self) -> str:
        return self.source

    @property
    def full_name(self) -> str:
        return self.source

    def __str__(self) -> str:
        return self.source


@dataclass(frozen=True)
class RustCompactReferenceMatch:
    backend: RustIndexBackend
    record: RustReferenceRecord | RustExternalReferenceRecord

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

    def edit(self, new_src: str, priority: int = 0, dedupe: bool = True) -> None:
        transaction = EditTransaction(
            self.record.range.start_byte,
            self.record.range.end_byte,
            self.file,
            new_src,
            priority=priority,
        )
        self.file.transaction_manager.add_transaction(transaction, dedupe=dedupe)

    def rename_if_matching(self, old_name: str, new_name: str, priority: int = 0) -> None:
        if self.source == old_name:
            self.edit(new_name, priority=priority)


@dataclass(frozen=True)
class RustCompactUsage:
    backend: RustIndexBackend
    record: RustReferenceRecord | RustExternalReferenceRecord

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RustCompactUsage) and self.backend is other.backend and type(self.record) is type(other.record) and self.record.id == other.record.id

    def __hash__(self) -> int:
        return hash(("rust-compact-usage", id(self.backend), type(self.record), self.record.id))

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


@dataclass(frozen=True)
class RustCompactDecorator:
    parent: RustCompactSymbol
    start_byte: int
    end_byte: int
    remove_end_byte: int

    @property
    def file(self) -> RustCompactFile:
        return self.parent.file

    @property
    def filepath(self) -> str:
        return self.file.filepath

    @property
    def source(self) -> str:
        return self.file.content_bytes[self.start_byte : self.end_byte].decode("utf-8")

    @property
    def full_name(self) -> str:
        source = self.source.strip()
        if source.startswith("@"):
            source = source[1:]
        return source.split("(", 1)[0].strip()

    @property
    def name(self) -> str:
        return self.full_name.rsplit(".", 1)[-1]

    def remove(self, delete_formatting: bool = True, priority: int = 0, dedupe: bool = True) -> None:
        end_byte = self.remove_end_byte if delete_formatting else self.end_byte
        transaction = RemoveTransaction(
            self.start_byte,
            end_byte,
            self.file,
            priority=priority,
        )
        self.parent.transaction_manager.add_transaction(transaction, dedupe=dedupe)


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


def _typescript_import_module_name_for_filepath(filepath: str) -> str:
    module = filepath.replace("\\", "/")
    for suffix in (".tsx", ".ts", ".jsx", ".js"):
        if module.endswith(suffix):
            module = module[: -len(suffix)]
            break
    if module.endswith("/index"):
        module = module[: -len("/index")]
    return module


def _line_count(source: str) -> int:
    if source == "":
        return 0
    return source.count("\n") + int(not source.endswith("\n"))


def _source_range_for_content(source: str) -> RustSourceRange:
    lines = source.splitlines()
    if source.endswith("\n"):
        end_row = len(lines)
        end_column = 0
    elif lines:
        end_row = len(lines) - 1
        end_column = len(lines[-1])
    else:
        end_row = 0
        end_column = 0
    return RustSourceRange(
        start_byte=0,
        end_byte=len(source.encode("utf-8")),
        start_row=0,
        start_column=0,
        end_row=end_row,
        end_column=end_column,
    )


def _line_byte_offsets(source: str) -> list[int]:
    offsets: list[int] = []
    offset = 0
    for line in source.splitlines(keepends=True):
        offsets.append(offset)
        offset += len(line.encode("utf-8"))
    if source == "" or source.endswith(("\n", "\r")):
        offsets.append(offset)
    return offsets


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

    @property
    def transaction_manager(self):
        if self.ctx is None:
            msg = "Compact Rust handle is not bound to a CodebaseContext"
            raise RuntimeError(msg)
        return self.ctx.transaction_manager


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
        self._pending_imports: set[str] = set()

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
        if self.extension in {".ts", ".tsx", ".js", ".jsx"}:
            return self.record.module_name or _typescript_import_module_name_for_filepath(self.filepath)
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
        if self.ctx is not None:
            return self.ctx.io.read_bytes(self.path)
        return self.path.read_bytes()

    @property
    def content(self) -> str:
        return self.content_bytes.decode("utf-8")

    @property
    def source(self) -> str:
        return self.content

    def write(self, content: str | bytes, to_disk: bool = False) -> None:
        if self.ctx is None:
            msg = "Cannot write compact Rust file without a CodebaseContext"
            raise RuntimeError(msg)
        self.ctx.io.write_file(self.path, content)
        if to_disk:
            self.ctx.io.save_files({self.path})

    def write_bytes(self, content_bytes: bytes, to_disk: bool = False) -> None:
        self.write(content_bytes, to_disk=to_disk)

    def edit(self, new_src: str, fix_indentation: bool = False, priority: int = 0, dedupe: bool = True) -> None:
        if self.is_binary:
            msg = "Cannot replace content in binary files"
            raise ValueError(msg)
        transaction = EditTransaction(0, len(self.content_bytes), self, new_src, priority=priority)
        self.transaction_manager.add_transaction(transaction, dedupe=dedupe)

    def insert_at(self, insert_byte: int, new_src: str, priority: int | tuple = 0, dedupe: bool = True) -> None:
        transaction = InsertTransaction(insert_byte, self, new_src, priority=priority)
        self.transaction_manager.add_transaction(transaction, dedupe=dedupe)

    def replace(self, old: str, new: str, count: int = -1, is_regex: bool = False, priority: int = 0) -> int:
        if self.is_binary:
            msg = "Cannot replace content in binary files"
            raise ValueError(msg)
        if is_regex:
            method = "RustCompactFile.replace(is_regex=True)"
            raise self._unsupported(method)
        if old not in self.content:
            return 0
        replacement_count = self.content.count(old) if count == -1 else min(self.content.count(old), count)
        self.edit(self.content.replace(old, new, count), priority=priority)
        return replacement_count

    def remove(self) -> None:
        self.transaction_manager.add_file_remove_transaction(self)
        self.backend.unregister_file(self.record.id)

    def add_import(self, imp: RustCompactSymbol | str, *, alias: str | None = None, import_type: ImportType = ImportType.UNKNOWN, is_type_import: bool = False) -> RustCompactImport | None:
        if isinstance(imp, RustCompactSymbol):
            existing = next((import_handle for import_handle in self.imports if import_handle.imported_symbol == imp), None)
            if existing is not None:
                return existing
            import_string = imp.get_import_string(alias, import_type=import_type, is_type_import=is_type_import)
        else:
            import_string = str(imp)

        normalized = import_string.strip()
        if any(normalized in str(import_handle.source) for import_handle in self.imports):
            return None
        if normalized in self._pending_imports:
            return None

        self._pending_imports.add(normalized)
        self.transaction_manager.pending_undos.add(lambda: self._pending_imports.clear())

        insert_byte, content = self._import_insertion(normalized)
        self.insert_at(insert_byte, content, priority=1)
        return None

    def _import_insertion(self, import_string: str) -> tuple[int, str]:
        import_line = import_string.rstrip("\n")
        if not self.imports or "__future__" in import_line:
            return 0, f"{import_line}\n"

        future_imports = [import_handle for import_handle in self.imports if "__future__" in import_handle.source]
        if future_imports:
            return future_imports[-1].end_byte, f"\n{import_line}"

        return self.imports[0].start_byte, f"{import_line}\n"

    def add_symbol_from_source(self, source: str) -> None:
        symbol_source = source.rstrip("\n")
        if not symbol_source:
            return

        if not self.content:
            self.insert_at(0, f"{symbol_source}\n")
            return

        prefix = "\n\n" if self.content.endswith("\n") else "\n"
        self.insert_at(len(self.content_bytes), f"{prefix}{symbol_source}\n")

    def add_symbol(self, symbol: RustCompactSymbol, should_export: bool = True) -> RustCompactSymbol | None:
        existing_symbol = self.get_symbol(symbol.name)
        if existing_symbol is not None:
            return existing_symbol
        self.add_symbol_from_source(symbol.source)
        return None

    @property
    def imports(self) -> list[RustCompactImport]:
        return self.backend.imports_for_file(self.record.id)

    @property
    def exports(self) -> list[RustCompactExport]:
        return self.backend.exports_for_file(self.record.id)

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

    @property
    def export_statements(self) -> list[RustCompactExport]:
        export_statements: list[RustCompactExport] = []
        seen: set[tuple[int, int, str]] = set()
        for export_handle in self.exports:
            key = (export_handle.start_byte, export_handle.end_byte, export_handle.source)
            if key in seen:
                continue
            seen.add(key)
            export_statements.append(export_handle.export_statement)
        return export_statements

    @property
    def default_exports(self) -> list[RustCompactExport]:
        return [export_handle for export_handle in self.exports if export_handle.is_default_export()]

    @property
    def named_exports(self) -> list[RustCompactExport]:
        return [export_handle for export_handle in self.exports if not export_handle.is_default_export()]

    def get_export(self, export_name: str) -> RustCompactExport | None:
        return next((export_handle for export_handle in self.exports if export_handle.name == export_name), None)

    def get_nodes(self, *, sort_by_id: bool = False, sort: bool = True) -> list[RustCompactImport | RustCompactExport | RustCompactSymbol]:
        nodes: list[RustCompactImport | RustCompactExport | RustCompactSymbol] = [*self.imports, *self.exports, *self.backend.symbols_for_file(self.record.id)]
        if not sort:
            return nodes

        if sort_by_id:
            return sorted(nodes, key=lambda node: (node.node_id, int(node.node_type), node.start_byte, node.end_byte))
        return sorted(nodes, key=lambda node: (node.start_byte, node.end_byte, int(node.node_type), node.node_id))

    def find_by_byte_range(self, range: Any) -> list[RustCompactImport | RustCompactExport | RustCompactSymbol]:
        start_byte, end_byte = _byte_range_bounds(range)
        return [node for node in self.get_nodes() if _ranges_overlap(node.range, start_byte, end_byte)]

    @property
    def descendant_symbols(self) -> list[RustCompactImport | RustCompactExport | RustCompactSymbol]:
        return self.get_nodes()

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
        self._pending_decorators: set[str] = set()

    def __repr__(self) -> str:
        return f"RustCompactSymbol(name={self.name!r}, filepath={self.filepath!r})"

    @property
    def symbol_type(self) -> SymbolType:
        return {
            "class": SymbolType.Class,
            "function": SymbolType.Function,
            "global_variable": SymbolType.GlobalVar,
            "interface": SymbolType.Interface,
            "type_alias": SymbolType.Type,
            "enum": SymbolType.Enum,
            "namespace": SymbolType.Namespace,
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
        if self.record.parent_symbol_id is not None:
            parent = self.backend.symbol_handle_by_id(self.record.parent_symbol_id)
            if parent is not None:
                return f"{parent.full_name}.{self.name}"
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

    @property
    def is_decorated(self) -> bool:
        return bool(self.decorators)

    @property
    def decorators(self) -> list[RustCompactDecorator]:
        content = self.file.content
        lines = content.splitlines(keepends=True)
        line_offsets = _line_byte_offsets(content)
        decorators: list[RustCompactDecorator] = []
        for row in range(self.record.range.start_row, self.record.name_range.start_row):
            if row >= len(lines) or row >= len(line_offsets):
                break

            line = lines[row]
            if not line.lstrip().startswith("@"):
                continue

            leading_spaces = len(line) - len(line.lstrip())
            line_without_newline = line.rstrip("\r\n")
            decorators.append(
                RustCompactDecorator(
                    parent=self,
                    start_byte=line_offsets[row] + len(line[:leading_spaces].encode("utf-8")),
                    end_byte=line_offsets[row] + len(line_without_newline.encode("utf-8")),
                    remove_end_byte=line_offsets[row] + len(line.encode("utf-8")),
                )
            )
        return decorators

    def add_decorator(self, new_decorator: str, skip_if_exists: bool = False) -> bool:
        if skip_if_exists and (any(decorator.source == new_decorator for decorator in self.decorators) or new_decorator in self._pending_decorators):
            return False

        self._pending_decorators.add(new_decorator)
        self.transaction_manager.pending_undos.add(lambda: self._pending_decorators.clear())

        indentation = " " * self.start_point[1]
        self.file.insert_at(self.start_byte, f"{new_decorator}\n{indentation}")
        return True

    @proxy_property
    def methods(self, *, max_depth: int | None = 0, private: bool = True, magic: bool = True) -> list[RustCompactSymbol]:
        methods = [symbol for symbol in self.child_symbols if symbol.record.kind == "function"]
        return [method for method in methods if (private or not method.name.startswith("_")) and (magic or not (method.name.startswith("__") and method.name.endswith("__")))]

    def get_method(self, name: str) -> RustCompactSymbol | None:
        return next((method for method in self.methods if method.name == name), None)

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

    def _direct_dependencies(self) -> list[RustCompactSymbol | RustCompactImport]:
        dependencies: list[RustCompactSymbol | RustCompactImport] = []
        seen: set[RustCompactSymbol | RustCompactImport] = set()
        for dependency in self.backend.dependencies_from_symbol(self.record.id):
            target = self.backend.symbol_handle_by_id(dependency.target_symbol_id)
            if target is None:
                continue
            should_include_target = True
            if self._preserve_import_dependencies():
                should_include_target = False
                for reference_id in dependency.reference_ids:
                    reference = self.backend.reference_by_id(reference_id)
                    if reference is None or reference.import_id is None:
                        should_include_target = True
                        continue
                    import_handle = self.backend.import_handle_by_id(reference.import_id)
                    if import_handle is None or import_handle in seen:
                        continue
                    seen.add(import_handle)
                    dependencies.append(import_handle)
            if should_include_target and target not in seen:
                seen.add(target)
                dependencies.append(target)
        for reference in self.backend.external_references_from_symbol(self.record.id):
            import_handle = self.backend.import_handle_by_id(reference.import_id)
            if import_handle is None or import_handle in seen:
                continue
            seen.add(import_handle)
            dependencies.append(import_handle)
        return dependencies

    def _preserve_import_dependencies(self) -> bool:
        return self.file.extension == ".py"

    def _direct_superclasses(self) -> list[RustCompactSymbol]:
        superclasses: list[RustCompactSymbol] = []
        seen: set[RustCompactSymbol] = set()
        for edge in self.backend.subclass_edges_from_symbol(self.record.id):
            target = self.backend.symbol_handle_by_id(edge.target_symbol_id)
            if target is None or target in seen:
                continue
            seen.add(target)
            superclasses.append(target)
        return superclasses

    def _direct_subclasses(self) -> list[RustCompactSymbol]:
        subclasses: list[RustCompactSymbol] = []
        seen: set[RustCompactSymbol] = set()
        for edge in self.backend.subclass_edges_to_symbol(self.record.id):
            source = self.backend.symbol_handle_by_id(edge.source_symbol_id)
            if source is None or source in seen:
                continue
            seen.add(source)
            subclasses.append(source)
        return subclasses

    @staticmethod
    def _walk_subclass_edges(seed: list[RustCompactSymbol], next_edges: str, max_depth: int | None = None) -> list[RustCompactSymbol]:
        if max_depth is not None and max_depth <= 0:
            return []

        results: list[RustCompactSymbol] = []
        seen: set[RustCompactSymbol] = set()
        frontier = seed
        depth = 0
        while frontier and (max_depth is None or depth < max_depth):
            next_frontier: list[RustCompactSymbol] = []
            for symbol in frontier:
                for candidate in getattr(symbol, next_edges)():
                    if candidate in seen:
                        continue
                    seen.add(candidate)
                    results.append(candidate)
                    next_frontier.append(candidate)
            frontier = next_frontier
            depth += 1
        return results

    @proxy_property
    def superclasses(self, max_depth: int | None = None) -> list[RustCompactSymbol]:
        return self._walk_subclass_edges([self], "_direct_superclasses", max_depth=max_depth)

    @proxy_property
    def subclasses(self, max_depth: int | None = None) -> list[RustCompactSymbol]:
        return self._walk_subclass_edges([self], "_direct_subclasses", max_depth=max_depth)

    @proxy_property
    def implementations(self, max_depth: int | None = None) -> list[RustCompactSymbol]:
        return self.subclasses(max_depth=max_depth)

    @property
    def parent_classes(self) -> list[str] | None:
        parents = [parent.name for parent in self._direct_superclasses()]
        return parents or None

    @property
    def parent_interfaces(self) -> list[str] | None:
        parents = [parent.name for parent in self._direct_superclasses()]
        return parents or None

    @property
    def parent_class_names(self) -> list[RustCompactName]:
        return [RustCompactName(name) for name in (self.parent_classes or [])]

    @property
    def is_subclass(self) -> bool:
        return bool(self.parent_classes)

    def is_subclass_of(self, parent_class: str | RustCompactSymbol, max_depth: int | None = None) -> bool:
        for superclass in self.superclasses(max_depth=max_depth):
            if isinstance(parent_class, RustCompactSymbol):
                if superclass == parent_class:
                    return True
            elif superclass.name == parent_class or superclass.full_name == parent_class:
                return True
        return False

    def extends(self, parent_interface: str | RustCompactSymbol, max_depth: int | None = None) -> bool:
        return self.is_subclass_of(parent_interface, max_depth=max_depth)

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
        return True

    def edit(self, new_src: str, fix_indentation: bool = False, priority: int = 0, dedupe: bool = True) -> None:
        transaction = EditTransaction(
            self.start_byte,
            self.end_byte,
            self.file,
            new_src,
            priority=priority,
        )
        self.transaction_manager.add_transaction(transaction, dedupe=dedupe)

    def remove(self, priority: int = 0) -> None:
        transaction = RemoveTransaction(
            self.start_byte,
            self.end_byte,
            self.file,
            priority=priority,
        )
        self.transaction_manager.add_transaction(transaction)

    def move_to_file(
        self,
        file: RustCompactFile,
        include_dependencies: bool = True,
        strategy: Literal["add_back_edge", "update_all_imports", "duplicate_dependencies"] = "update_all_imports",
    ) -> None:
        self._move_to_file(file, {self}, include_dependencies, strategy)

    def _move_to_file(
        self,
        file: RustCompactFile,
        encountered_symbols: set[RustCompactSymbol | RustCompactImport],
        include_dependencies: bool = True,
        strategy: Literal["add_back_edge", "update_all_imports", "duplicate_dependencies"] = "update_all_imports",
    ) -> None:
        if strategy not in {"add_back_edge", "update_all_imports", "duplicate_dependencies"}:
            msg = f"Unsupported move_to_file strategy: {strategy}"
            raise AssertionError(msg)
        if file == self.file:
            return

        if existing_import := file.get_import(self.name):
            encountered_symbols.add(existing_import)
            existing_import.remove()

        for dependency in self.dependencies:
            if dependency in encountered_symbols:
                continue
            if isinstance(dependency, RustCompactSymbol) and dependency.is_top_level and include_dependencies:
                encountered_symbols.add(dependency)
                dependency._move_to_file(file, encountered_symbols, include_dependencies, strategy)
            elif isinstance(dependency, RustCompactSymbol):
                file.add_import(dependency, alias=dependency.name)
            elif isinstance(dependency, RustCompactImport):
                imported_symbol = dependency.imported_symbol
                if isinstance(imported_symbol, RustCompactSymbol):
                    file.add_import(imported_symbol, alias=self._alias_for_import_dependency(dependency, imported_symbol))
                else:
                    file.add_import(dependency.source)

        file.add_symbol(self)
        import_line = self.get_import_string(module=file.import_module_name)
        is_used_in_source_file = any(usage_symbol != self and getattr(usage_symbol, "file", None) == self.file for usage_symbol in self.symbol_usages)
        imported_usages = [usage for usage in self.usages if usage.imported_by is not None and usage.imported_by not in encountered_symbols]

        if strategy == "duplicate_dependencies":
            if not is_used_in_source_file and not imported_usages:
                self.remove()
            return

        if strategy == "add_back_edge":
            if is_used_in_source_file or imported_usages:
                self.file.add_import(import_line)
            self.remove()
            return

        for usage in imported_usages:
            imported_by = usage.imported_by
            if imported_by is not None and imported_by.file != file:
                imported_by.file.add_import(import_line)
                imported_by.remove()

        if is_used_in_source_file:
            self.file.add_import(import_line)
        self.remove()

    def _alias_for_import_dependency(self, dependency: RustCompactImport, imported_symbol: RustCompactSymbol) -> str | None:
        dependency_name = dependency.name
        if dependency_name is None:
            return None
        for symbol_dependency in self.backend.dependencies_from_symbol(self.record.id):
            if symbol_dependency.target_symbol_id != imported_symbol.record.id:
                continue
            for reference_id in symbol_dependency.reference_ids:
                reference = self.backend.reference_by_id(reference_id)
                if reference is not None and reference.import_id == dependency.record.id and reference.name == dependency_name:
                    return dependency_name
        return None

    def set_name(self, name: str, priority: int = 0) -> None:
        transaction = EditTransaction(
            self.record.name_range.start_byte,
            self.record.name_range.end_byte,
            self.file,
            name,
            priority=priority,
        )
        self.transaction_manager.add_transaction(transaction)
        self.name = name
        self._name_node = RustCompactName(name)

    def rename(self, new_name: str, priority: int = 0) -> None:
        old_name = self.name
        self.set_name(new_name, priority=priority)
        for usage in self.usages(UsageType.DIRECT | UsageType.CHAINED):
            usage.match.rename_if_matching(old_name, new_name, priority=priority)

    @property
    def parent_symbol(self) -> RustCompactSymbol:
        if self.record.parent_symbol_id is None:
            return self
        parent = self.backend.symbol_handle_by_id(self.record.parent_symbol_id)
        return self if parent is None else parent

    def get_name(self) -> RustCompactName:
        return self._name_node

    def get_import_string(self, alias: str | None = None, module: str | None = None, import_type: ImportType = ImportType.UNKNOWN, is_type_import: bool = False) -> str:
        import_module = module if module is not None else self.file.import_module_name
        if import_type == ImportType.WILDCARD:
            file_as_module = self.file.name
            return f"from {import_module} import * as {file_as_module}"
        if alias is not None and alias != self.name:
            return f"from {import_module} import {self.name} as {alias}"
        return f"from {import_module} import {self.name}"


class RustCompactExternalModule(RustCompactHandle):
    node_type = NodeType.EXTERNAL

    def __init__(self, backend: RustIndexBackend, record: RustExternalModuleRecord) -> None:
        self.record = record
        super().__init__(backend, record.id, record.range)
        self.name = record.name
        self._name_node = RustCompactName(record.name)

    def __repr__(self) -> str:
        return f"RustCompactExternalModule(name={self.name!r}, import_id={self.record.import_id})"

    @property
    def import_handle(self) -> RustCompactImport | None:
        return self.backend.import_handle_by_id(self.record.import_id)

    @property
    def file(self) -> None:
        return None

    @property
    def filepath(self) -> str:
        return ""

    @property
    def source(self) -> str:
        import_handle = self.import_handle
        if import_handle is not None:
            return import_handle.source
        return self.record.module or self.name

    @property
    def full_name(self) -> str:
        return self.name

    @property
    def parent_symbol(self) -> RustCompactExternalModule:
        return self

    @property
    def descendant_symbols(self) -> list[RustCompactExternalModule]:
        return [self]

    @property
    def names(self) -> list[tuple[str, RustCompactExternalModule]]:
        return [(self.name, self)]

    def get_name(self) -> RustCompactName:
        return self._name_node

    def get_import_string(self, alias: str | None = None, module: str | None = None, import_type: ImportType = ImportType.UNKNOWN, is_type_import: bool = False) -> str:
        return self.source

    def resolve_attribute(self, name: str) -> RustCompactExternalModule:
        return self


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
    def imported_symbol(self) -> RustCompactSymbol | RustCompactFile | RustCompactExternalModule | None:
        resolution = self.backend.import_resolution_for_import(self.record.id)
        if resolution is None:
            return self.backend.external_module_for_import(self.record.id)
        if resolution.target_symbol_id is not None:
            return self.backend.symbol_handle_by_id(resolution.target_symbol_id)
        return self.backend.file_handle_by_id(resolution.target_file_id)

    @property
    def resolved_symbol(self) -> RustCompactSymbol | RustCompactFile | RustCompactExternalModule | None:
        return self.imported_symbol

    @property
    def imported_exports(self) -> list[RustCompactSymbol | RustCompactFile | RustCompactExternalModule]:
        imported = self.imported_symbol
        if imported is None:
            return []
        if not self.is_module_import():
            return [imported]
        if isinstance(imported, RustCompactFile):
            return [*imported.symbols, *imported.imports]
        return [imported]

    def resolve_attribute(self, attribute: str) -> RustCompactImport | RustCompactSymbol | RustCompactFile | RustCompactExternalModule | None:
        imported = self.imported_symbol
        if isinstance(imported, RustCompactFile):
            return imported.valid_import_names.get(attribute)
        if isinstance(imported, RustCompactExternalModule):
            return imported.resolve_attribute(attribute)
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

        usages = [
            RustCompactUsage(self.backend, reference)
            for reference in [*self.backend.references_for_import(self.record.id), *self.backend.external_references_for_import(self.record.id)]
        ]
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

    @property
    def descendant_symbols(self) -> list[RustCompactImport]:
        return [self]

    def remove(self, priority: int = 0) -> None:
        start_byte = self.start_byte
        end_byte = self.end_byte
        content = self.file.content
        lines = content.splitlines(keepends=True)
        line_offsets = _line_byte_offsets(content)
        row = self.record.range.start_row
        if row < len(lines) and row < len(line_offsets):
            start_byte = line_offsets[row]
            end_byte = line_offsets[row] + len(lines[row].encode("utf-8"))

        transaction = RemoveTransaction(
            start_byte,
            end_byte,
            self.file,
            priority=priority,
        )
        self.transaction_manager.add_transaction(transaction)

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

    def get_name(self) -> RustCompactName | None:
        if self.alias is not None:
            return self.alias
        if self.symbol_name is not None:
            return self.symbol_name
        return self.module

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


class RustCompactExport(RustCompactHandle):
    node_type = NodeType.EXPORT

    def __init__(self, backend: RustIndexBackend, record: RustExportRecord) -> None:
        self.record = record
        super().__init__(backend, record.id, record.range)
        self.name = record.name
        self._name_node = RustCompactName(record.name) if record.name is not None else None
        self.export_statement = self

    def __repr__(self) -> str:
        return f"RustCompactExport(name={self.name!r}, filepath={self.filepath!r})"

    @property
    def file(self) -> RustCompactFile:
        file = self.backend.file_handle_by_id(self.record.file_id)
        if file is None:
            msg = f"Rust compact export {self.record.id} references missing file {self.record.file_id}"
            raise RuntimeError(msg)
        return file

    @property
    def filepath(self) -> str:
        return self.file.filepath

    @property
    def source(self) -> str:
        return self.file.content_bytes[self.start_byte : self.end_byte].decode("utf-8")

    @property
    def full_name(self) -> str | None:
        return self.name

    @property
    def exported_name(self) -> str | None:
        return self.name

    @property
    def local_name(self) -> str | None:
        return self.record.local_name

    @property
    def module(self) -> RustCompactName | None:
        if self.record.source_module is None:
            return None
        return RustCompactName(self.record.source_module)

    @property
    def symbol_name(self) -> RustCompactName | None:
        if self.record.local_name is None:
            return None
        return RustCompactName(self.record.local_name)

    @property
    def alias(self) -> RustCompactName | None:
        if self.record.name is None or self.record.name == self.record.local_name:
            return None
        return RustCompactName(self.record.name)

    @property
    def declared_symbol(self) -> RustCompactSymbol | RustCompactImport | None:
        if self.record.symbol_id is not None:
            return self.backend.symbol_handle_by_id(self.record.symbol_id)
        if self.record.import_id is not None:
            return self.backend.import_handle_by_id(self.record.import_id)
        return None

    @property
    def exported_symbol(self) -> RustCompactSymbol | RustCompactImport | RustCompactFile | None:
        declared = self.declared_symbol
        if declared is not None:
            return declared
        if self.is_wildcard_export():
            return self.file
        return None

    @property
    def resolved_symbol(self) -> RustCompactSymbol | RustCompactFile | None:
        exported = self.exported_symbol
        seen: set[object] = set()
        while exported is not None and getattr(exported, "node_type", None) in {NodeType.IMPORT, NodeType.EXPORT}:
            if exported in seen:
                return exported
            seen.add(exported)
            exported = exported.resolved_symbol if exported.node_type == NodeType.IMPORT else exported.exported_symbol
        return exported

    @property
    def parent_symbol(self) -> RustCompactExport:
        return self

    @property
    def descendant_symbols(self) -> list[RustCompactExport | RustCompactSymbol]:
        declared = self.declared_symbol
        if isinstance(declared, RustCompactSymbol):
            return [self, *declared.descendant_symbols]
        return [self]

    @property
    def names(self):
        if self.name is not None:
            yield self.name, self

    @property
    def is_external_export(self) -> bool:
        return self.record.source_module is not None and not self.record.source_module.startswith(".")

    def get_name(self) -> RustCompactName | None:
        return self._name_node

    def is_named_export(self) -> bool:
        return not self.is_default_export()

    def is_default_export(self) -> bool:
        return self.record.kind in {"default", "export_equals"} or self.name == "default"

    def is_default_symbol_export(self) -> bool:
        return self.is_default_export() and self.record.local_name is not None

    def is_type_export(self) -> bool:
        return self.source.lstrip().startswith("export type ")

    def is_reexport(self) -> bool:
        exported = self.exported_symbol
        return self.record.source_module is not None or (exported is not None and getattr(exported, "node_type", None) == NodeType.IMPORT)

    def is_wildcard_export(self) -> bool:
        return self.record.kind in {"wildcard", "namespace"}

    def is_module_export(self) -> bool:
        return self.is_wildcard_export() or (self.is_default_export() and not self.is_default_symbol_export())

    def is_aliased(self) -> bool:
        return self.record.name != self.record.local_name

    def reexport_symbol(self) -> RustCompactImport | None:
        declared = self.declared_symbol
        return declared if isinstance(declared, RustCompactImport) else None

    def to_import_string(self) -> str:
        module_path = self.record.source_module or ""
        type_prefix = "type " if self.is_type_export() else ""

        if self.is_wildcard_export():
            namespace = self.name or module_path.split("/")[-1].split(".")[0]
            return f"import * as {namespace} from '{module_path}';"

        local_name = self.record.local_name or self.name
        if self.is_default_export() and self.record.local_name == "default":
            return f"import {self.name} from '{module_path}';"
        if local_name != self.name:
            return f"import {type_prefix}{{ {local_name} as {self.name} }} from '{module_path}';"
        return f"import {type_prefix}{{ {self.name} }} from '{module_path}';"

    def get_import_string(self, alias: str | None = None, module: str | None = None, import_type: ImportType = ImportType.UNKNOWN, is_type_import: bool = False) -> str:
        if self.is_reexport():
            return self.to_import_string()

        module_path = module if module is not None else self.file.import_module_name.strip("'\"")
        type_prefix = "type " if is_type_import else ""

        if import_type == ImportType.WILDCARD:
            namespace = alias or module_path.split("/")[-1].split(".")[0]
            return f"import * as {namespace} from '{module_path}';"

        if self.is_default_export():
            name = alias or self.record.local_name or self.name
            return f"import {name} from '{module_path}';"

        original_name = self.name
        if alias and alias != original_name:
            return f"import {type_prefix}{{ {original_name} as {alias} }} from '{module_path}';"
        return f"import {type_prefix}{{ {original_name} }} from '{module_path}';"
