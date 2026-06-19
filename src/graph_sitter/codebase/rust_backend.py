from __future__ import annotations

import json
from dataclasses import dataclass, field
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


class RustBackendUnsupportedError(NotImplementedError):
    """Raised when a compact Rust handle does not implement a Python API yet."""

    def __init__(self, method: str, handle: str, reason: str | None = None) -> None:
        self.method = method
        self.handle = handle
        self.reason = reason
        details = f"{method} is not supported by compact Rust handle {handle} yet"
        if reason:
            details = f"{details}: {reason}"
        guidance = "Use CodebaseConfig(graph_backend='python') for this API, or choose a compact Rust API that is implemented without materializing the Python graph."
        super().__init__(f"{details}. {guidance}")


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
    external_modules: int
    exports: int
    references: int
    external_references: int
    dependencies: int
    subclass_edges: int
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
            data = {field: getattr(summary, field, 0) for field in cls.__dataclass_fields__}
        return cls(**{field: int(data.get(field, 0)) for field in cls.__dataclass_fields__})


@dataclass(frozen=True)
class RustFileRecord:
    id: int
    path: str
    module_name: str | None
    language: str
    content_hash: str
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
            language=str(data.get("language", "")),
            content_hash=str(data.get("content_hash", "")),
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
    _file_handles_by_path: dict[str, RustCompactFile] | None = None
    _symbol_handles_by_id: dict[int, RustCompactSymbol] | None = None
    _import_handles_by_id: dict[int, RustCompactImport] | None = None
    _external_module_handles_by_import_id: dict[int, RustCompactExternalModule] | None = None
    _export_handles_by_id: dict[int, RustCompactExport] | None = None
    _symbols_by_file_id: dict[int, list[RustCompactSymbol]] | None = None
    _symbols_by_file_id_and_byte_range: dict[tuple[int, int, int], list[RustCompactSymbol]] | None = None
    _imports_by_file_id_and_lookup: dict[tuple[int, str], list[RustCompactImport]] | None = None
    _imports_by_file_id_and_byte_range: dict[tuple[int, int, int], list[RustCompactImport]] | None = None
    _imports_by_file_id: dict[int, list[RustCompactImport]] | None = None
    _exports_by_file_id: dict[int, list[RustCompactExport]] | None = None
    _exports_by_file_id_and_name: dict[tuple[int, str], list[RustCompactExport]] | None = None
    _exports_by_file_id_and_byte_range: dict[tuple[int, int, int], list[RustCompactExport]] | None = None
    _import_resolutions_by_import_id: dict[int, RustImportResolutionRecord] | None = None
    _import_resolutions_by_target_file_id: dict[int, list[RustImportResolutionRecord]] | None = None
    _import_resolutions_by_target_symbol_id: dict[int, list[RustImportResolutionRecord]] | None = None
    _exports_by_symbol_id: dict[int, list[RustCompactExport]] | None = None
    _symbols_by_file_id_and_name: dict[tuple[int, str], list[RustCompactSymbol]] | None = None
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
    _removed_file_ids: set[int] = field(default_factory=set)
    _removed_file_paths: set[str] = field(default_factory=set)
    _added_file_records_by_id: dict[int, RustFileRecord] = field(default_factory=dict)
    _added_file_records_by_path: dict[str, RustFileRecord] = field(default_factory=dict)
    _next_added_file_id: int | None = None
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

    def _record_from_json_method(self, method_name: str, factory: Any, *args: Any) -> Any | None:
        method = getattr(self.index, method_name, None)
        if method is None:
            return None
        data = json.loads(method(*args))
        if data is None:
            return None
        return factory(data)

    def _records_from_json_method(self, method_name: str, factory: Any, *args: Any) -> list[Any] | None:
        method = getattr(self.index, method_name, None)
        if method is None:
            return None
        return [factory(record) for record in json.loads(method(*args))]

    def _bind_handle(self, handle: Any) -> Any:
        if self._ctx is not None:
            handle.ctx = self._ctx
        return handle

    def _file_record_by_id(self, file_id: int) -> RustFileRecord | None:
        if file_id in self._added_file_records_by_id:
            return self._added_file_records_by_id[file_id]
        return self._record_from_json_method("file_by_id_json", RustFileRecord.from_dict, file_id)

    def _file_record_by_path(self, filepath: str) -> RustFileRecord | None:
        if filepath in self._added_file_records_by_path:
            return self._added_file_records_by_path[filepath]
        return self._record_from_json_method("file_by_path_json", RustFileRecord.from_dict, filepath)

    def _file_record_by_path_ignore_case(self, filepath: str) -> RustFileRecord | None:
        normalized = filepath.lower()
        for added_path, record in self._added_file_records_by_path.items():
            if added_path.lower() == normalized:
                return record
        return self._record_from_json_method("file_by_path_ignore_case_json", RustFileRecord.from_dict, filepath)

    def _symbol_record_by_id(self, symbol_id: int) -> RustSymbolRecord | None:
        return self._record_from_json_method("symbol_by_id_json", RustSymbolRecord.from_dict, symbol_id)

    def _import_record_by_id(self, import_id: int) -> RustImportRecord | None:
        return self._record_from_json_method("import_by_id_json", RustImportRecord.from_dict, import_id)

    def _export_record_by_id(self, export_id: int) -> RustExportRecord | None:
        return self._record_from_json_method("export_by_id_json", RustExportRecord.from_dict, export_id)

    def _file_handle_from_record(self, record: RustFileRecord) -> RustCompactFile:
        if self._file_handles_by_id is None:
            self._file_handles_by_id = {}
        if self._file_handles_by_path is None:
            self._file_handles_by_path = {}
        handle = self._file_handles_by_id.get(record.id) or self._file_handles_by_path.get(record.path)
        if handle is None:
            handle = RustCompactFile(self, record)
        self._bind_handle(handle)
        self._file_handles_by_id[record.id] = handle
        self._file_handles_by_path[record.path] = handle
        return handle

    def _symbol_handle_from_record(self, record: RustSymbolRecord) -> RustCompactSymbol:
        if self._symbol_handles_by_id is None:
            self._symbol_handles_by_id = {}
        handle = self._symbol_handles_by_id.get(record.id)
        if handle is None:
            handle = RustCompactSymbol(self, record)
        self._bind_handle(handle)
        self._symbol_handles_by_id[record.id] = handle
        return handle

    def _import_handle_from_record(self, record: RustImportRecord) -> RustCompactImport:
        if self._import_handles_by_id is None:
            self._import_handles_by_id = {}
        handle = self._import_handles_by_id.get(record.id)
        if handle is None:
            handle = RustCompactImport(self, record)
        self._bind_handle(handle)
        self._import_handles_by_id[record.id] = handle
        return handle

    def _external_module_handle_from_record(self, record: RustExternalModuleRecord) -> RustCompactExternalModule:
        if self._external_module_handles_by_import_id is None:
            self._external_module_handles_by_import_id = {}
        handle = self._external_module_handles_by_import_id.get(record.import_id)
        if handle is None:
            handle = RustCompactExternalModule(self, record)
        self._bind_handle(handle)
        self._external_module_handles_by_import_id[record.import_id] = handle
        return handle

    def _export_handle_from_record(self, record: RustExportRecord) -> RustCompactExport:
        if self._export_handles_by_id is None:
            self._export_handles_by_id = {}
        handle = self._export_handles_by_id.get(record.id)
        if handle is None:
            handle = RustCompactExport(self, record)
        self._bind_handle(handle)
        self._export_handles_by_id[record.id] = handle
        return handle

    def compact_record_counts(self) -> dict[str, int]:
        return {
            "rust_files": self.summary.files,
            "rust_symbols": self.summary.symbols,
            "rust_classes": self.summary.classes,
            "rust_functions": self.summary.functions,
            "rust_global_vars": self.summary.global_variables,
            "rust_imports": self.summary.imports,
            "rust_import_resolutions": self.summary.import_resolutions,
            "rust_external_modules": self.summary.external_modules,
            "rust_exports": self.summary.exports,
            "rust_references": self.summary.references,
            "rust_external_references": self.summary.external_references,
            "rust_dependencies": self.summary.dependencies,
            "rust_subclass_edges": self.summary.subclass_edges,
        }

    def compact_compat_counts(self) -> dict[str, int]:
        index = self.index

        def count_attr(name: str, fallback: Any) -> int:
            value = getattr(index, name, None)
            if value is None:
                if callable(fallback):
                    return int(fallback())
                return int(fallback)
            if callable(value):
                value = value()
            return int(value)

        def id_list_count(name: str, fallback: int) -> int:
            value = getattr(index, name, None)
            if value is None:
                return fallback
            if callable(value):
                value = value()
            return len(value)

        symbols = count_attr(
            "top_level_symbol_count",
            lambda: id_list_count("top_level_symbol_ids", self.summary.symbols),
        )
        return {
            "files": self.summary.files,
            "symbols": symbols,
            "classes": count_attr("top_level_class_count", self.summary.classes),
            "functions": count_attr("top_level_function_count", self.summary.functions),
            "global_vars": count_attr("top_level_global_variable_count", self.summary.global_variables),
            "interfaces": count_attr("interface_count", lambda: id_list_count("interface_ids", 0)),
            "types": count_attr("type_count", lambda: id_list_count("type_ids", 0)),
            "imports": self.summary.imports,
            "external_modules": self.summary.external_modules,
            "exports": count_attr("export_count", self.summary.exports),
        }

    @property
    def files(self) -> list[RustFileRecord]:
        if self._files is None:
            self._files = [
                RustFileRecord.from_dict(record)
                for record in json.loads(self.index.files_json())
                if int(record["id"]) not in self._removed_file_ids
            ]
            self._files.extend(record for record in self._added_file_records_by_id.values() if record.id not in self._removed_file_ids)
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
            self._file_handles = [self._file_handle_from_record(record) for record in self.files]
        return self._file_handles

    @property
    def symbol_handles(self) -> list[RustCompactSymbol]:
        if self._symbol_handles is None:
            self._symbol_handles = [self._symbol_handle_from_record(record) for record in self.symbols]
        return self._symbol_handles

    @property
    def import_handles(self) -> list[RustCompactImport]:
        if self._import_handles is None:
            self._import_handles = [self._import_handle_from_record(record) for record in self.imports]
        return self._import_handles

    @property
    def external_module_handles(self) -> list[RustCompactExternalModule]:
        if self._external_module_handles is None:
            self._external_module_handles = [self._external_module_handle_from_record(record) for record in self.external_modules]
        return self._external_module_handles

    @property
    def export_handles(self) -> list[RustCompactExport]:
        if self._export_handles is None:
            self._export_handles = [self._export_handle_from_record(record) for record in self.exports]
        return self._export_handles

    def bind_context(self, ctx: CodebaseContext) -> None:
        self._ctx = ctx
        for handles in (self._file_handles, self._symbol_handles, self._import_handles, self._external_module_handles, self._export_handles):
            if handles is None:
                continue
            for handle in handles:
                handle.ctx = ctx
        for handles_by_key in (
            self._file_handles_by_id,
            self._file_handles_by_path,
            self._symbol_handles_by_id,
            self._import_handles_by_id,
            self._external_module_handles_by_import_id,
            self._export_handles_by_id,
        ):
            if handles_by_key is None:
                continue
            for handle in handles_by_key.values():
                handle.ctx = ctx

    def _allocate_added_file_id(self) -> int:
        if self._next_added_file_id is None:
            next_id = self.summary.files
            if self._files is not None:
                next_id = max((file.id for file in self._files), default=-1) + 1
            elif self._file_handles is not None:
                next_id = max((file.record.id for file in self._file_handles), default=-1) + 1
            self._next_added_file_id = max(next_id, self.summary.files)
        file_id = self._next_added_file_id
        self._next_added_file_id += 1
        return file_id

    def register_added_file(self, filepath: str, content: str = "") -> RustCompactFile:
        relative_path = self._normalize_relative_path(filepath)
        if existing := self.get_file_handle(relative_path):
            return existing

        content_bytes = content.encode("utf-8")
        module_name = None
        if relative_path.endswith(".py"):
            module_name = _python_import_module_name_for_filepath(relative_path)
        elif _is_typescript_like_extension(Path(relative_path).suffix):
            module_name = _typescript_import_module_name_for_filepath(relative_path)
        record = RustFileRecord(
            id=self._allocate_added_file_id(),
            path=relative_path,
            module_name=module_name,
            language=_rust_file_language_for_path(relative_path),
            content_hash=_stable_content_hash(content_bytes),
            byte_len=len(content_bytes),
            line_count=_line_count(content),
            has_error=False,
            root_range=_source_range_for_content(content),
        )
        self._added_file_records_by_id[record.id] = record
        self._added_file_records_by_path[record.path] = record
        if self._files is not None:
            self._files.append(record)
        file = self._file_handle_from_record(record)
        if self._file_handles is not None:
            self._file_handles.append(file)
        self._removed_file_ids.discard(record.id)
        self._removed_file_paths.discard(record.path)
        if self._symbols_by_file_id is not None:
            self._symbols_by_file_id[record.id] = []
        if self._imports_by_file_id is not None:
            self._imports_by_file_id[record.id] = []
        if self._exports_by_file_id is not None:
            self._exports_by_file_id[record.id] = []
        return file

    def unregister_file(self, file_id: int, filepath: str | None = None) -> None:
        if filepath is None:
            if self._file_handles_by_id is not None and file_id in self._file_handles_by_id:
                filepath = self._file_handles_by_id[file_id].record.path
            elif self._files is not None:
                filepath = next((file.path for file in self._files if file.id == file_id), None)
            elif record := self._file_record_by_id(file_id):
                filepath = record.path
        self._removed_file_ids.add(file_id)
        if filepath is not None:
            self._removed_file_paths.add(filepath)
        self._added_file_records_by_id.pop(file_id, None)
        if filepath is not None:
            self._added_file_records_by_path.pop(filepath, None)

        if self._files is not None:
            self._files = [file for file in self._files if file.id != file_id]
        if self._file_handles is not None:
            self._file_handles = [file for file in self._file_handles if file.record.id != file_id]
        if self._symbols is not None:
            self._symbols = [symbol for symbol in self._symbols if symbol.file_id != file_id]
        if self._imports is not None:
            self._imports = [import_record for import_record in self._imports if import_record.file_id != file_id]
        if self._import_resolutions is not None:
            self._import_resolutions = [resolution for resolution in self._import_resolutions if resolution.source_file_id != file_id and resolution.target_file_id != file_id]
        if self._external_modules is not None:
            self._external_modules = [external_module for external_module in self._external_modules if external_module.file_id != file_id]
        if self._exports is not None:
            self._exports = [export for export in self._exports if export.file_id != file_id]
        if self._references is not None:
            self._references = [reference for reference in self._references if reference.source_file_id != file_id]
        if self._external_references is not None:
            self._external_references = [reference for reference in self._external_references if reference.source_file_id != file_id]
        if self._dependencies is not None:
            self._dependencies = [dependency for dependency in self._dependencies if dependency.source_file_id != file_id and dependency.target_file_id != file_id]
        if self._subclass_edges is not None:
            self._subclass_edges = [edge for edge in self._subclass_edges if edge.source_file_id != file_id and edge.target_file_id != file_id]
        self._file_handles_by_id = None
        self._file_handles_by_path = None
        self._symbol_handles = None
        self._import_handles = None
        self._external_module_handles = None
        self._export_handles = None
        self._external_module_handles_by_import_id = None
        self._export_handles_by_id = None
        self._symbols_by_file_id = None
        self._symbols_by_file_id_and_byte_range = None
        self._imports_by_file_id_and_lookup = None
        self._imports_by_file_id_and_byte_range = None
        self._imports_by_file_id = None
        self._exports_by_file_id = None
        self._exports_by_file_id_and_name = None
        self._exports_by_file_id_and_byte_range = None
        self._import_resolutions_by_import_id = None
        self._import_resolutions_by_target_file_id = None
        self._import_resolutions_by_target_symbol_id = None
        self._exports_by_symbol_id = None
        self._symbols_by_file_id_and_name = None
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
        normalized_for_lookup = normalized.lower() if ignore_case else normalized
        removed_paths = {path.lower() for path in self._removed_file_paths} if ignore_case else self._removed_file_paths
        if normalized_for_lookup in removed_paths:
            return None
        if not ignore_case and self._file_handles is None and hasattr(self.index, "file_by_path_json"):
            if self._file_handles_by_path is not None and normalized in self._file_handles_by_path:
                return self._file_handles_by_path[normalized]
            record = self._file_record_by_path(normalized)
            if record is not None:
                if record.id in self._removed_file_ids:
                    return None
                return self._file_handle_from_record(record)
            return None
        if ignore_case and self._file_handles is None and hasattr(self.index, "file_by_path_ignore_case_json"):
            if self._file_handles_by_path is not None:
                for existing_path, handle in self._file_handles_by_path.items():
                    if existing_path.lower() == normalized_for_lookup:
                        return handle
            record = self._file_record_by_path_ignore_case(normalized)
            if record is not None:
                if record.id in self._removed_file_ids or record.path.lower() in removed_paths:
                    return None
                return self._file_handle_from_record(record)
            return None
        if ignore_case:
            normalized = normalized.lower()
            return next((file for file in self.file_handles if file.filepath.lower() == normalized), None)
        return next((file for file in self.file_handles if file.filepath == normalized), None)

    def symbols_for_file(self, file_id: int) -> list[RustCompactSymbol]:
        if self._symbol_handles is None and hasattr(self.index, "symbols_for_file_json"):
            if self._symbols_by_file_id is None:
                self._symbols_by_file_id = {}
            if file_id not in self._symbols_by_file_id:
                records = self._records_from_json_method("symbols_for_file_json", RustSymbolRecord.from_dict, file_id)
                if records is not None:
                    self._symbols_by_file_id[file_id] = [self._symbol_handle_from_record(record) for record in records]
                else:
                    self._symbol_handles = [self._symbol_handle_from_record(record) for record in self.symbols]
            if file_id in self._symbols_by_file_id:
                return self._symbols_by_file_id[file_id]
        if self._symbols_by_file_id is None:
            symbols_by_file_id: dict[int, list[RustCompactSymbol]] = {}
            for symbol in self.symbol_handles:
                symbols_by_file_id.setdefault(symbol.record.file_id, []).append(symbol)
            self._symbols_by_file_id = symbols_by_file_id
        return self._symbols_by_file_id.get(file_id, [])

    def symbols_for_file_by_name(self, file_id: int, name: str) -> list[RustCompactSymbol]:
        if self._symbol_handles is None and hasattr(self.index, "symbols_for_file_by_name_json"):
            if self._symbols_by_file_id_and_name is None:
                self._symbols_by_file_id_and_name = {}
            key = (file_id, name)
            if key not in self._symbols_by_file_id_and_name:
                records = self._records_from_json_method("symbols_for_file_by_name_json", RustSymbolRecord.from_dict, file_id, name)
                if records is not None:
                    self._symbols_by_file_id_and_name[key] = [self._symbol_handle_from_record(record) for record in records]
                else:
                    self._symbol_handles = [self._symbol_handle_from_record(record) for record in self.symbols]
            if key in self._symbols_by_file_id_and_name:
                return self._symbols_by_file_id_and_name[key]
        return [symbol for symbol in self.symbols_for_file(file_id) if symbol.name == name]

    def symbols_for_file_by_byte_range(self, file_id: int, start_byte: int, end_byte: int) -> list[RustCompactSymbol]:
        if self._symbol_handles is None and hasattr(self.index, "symbols_for_file_by_byte_range_json"):
            if self._symbols_by_file_id_and_byte_range is None:
                self._symbols_by_file_id_and_byte_range = {}
            key = (file_id, start_byte, end_byte)
            if key not in self._symbols_by_file_id_and_byte_range:
                records = self._records_from_json_method("symbols_for_file_by_byte_range_json", RustSymbolRecord.from_dict, file_id, start_byte, end_byte)
                if records is not None:
                    self._symbols_by_file_id_and_byte_range[key] = [self._symbol_handle_from_record(record) for record in records]
                else:
                    self._symbol_handles = [self._symbol_handle_from_record(record) for record in self.symbols]
            if key in self._symbols_by_file_id_and_byte_range:
                return self._symbols_by_file_id_and_byte_range[key]
        return [symbol for symbol in self.symbols_for_file(file_id) if _ranges_overlap(symbol.range, start_byte, end_byte)]

    def symbols_for_parent(self, parent_symbol_id: int) -> list[RustCompactSymbol]:
        if self._symbol_handles is None and hasattr(self.index, "symbols_for_parent_json"):
            if self._symbols_by_parent_symbol_id is None:
                self._symbols_by_parent_symbol_id = {}
            if parent_symbol_id not in self._symbols_by_parent_symbol_id:
                records = self._records_from_json_method("symbols_for_parent_json", RustSymbolRecord.from_dict, parent_symbol_id)
                if records is not None:
                    self._symbols_by_parent_symbol_id[parent_symbol_id] = [self._symbol_handle_from_record(record) for record in records]
                else:
                    self._symbol_handles = [self._symbol_handle_from_record(record) for record in self.symbols]
            if parent_symbol_id in self._symbols_by_parent_symbol_id:
                return self._symbols_by_parent_symbol_id[parent_symbol_id]
        if self._symbols_by_parent_symbol_id is None:
            symbols_by_parent_symbol_id: dict[int, list[RustCompactSymbol]] = {}
            for symbol in self.symbol_handles:
                if symbol.record.parent_symbol_id is not None:
                    symbols_by_parent_symbol_id.setdefault(symbol.record.parent_symbol_id, []).append(symbol)
            self._symbols_by_parent_symbol_id = symbols_by_parent_symbol_id
        return self._symbols_by_parent_symbol_id.get(parent_symbol_id, [])

    def top_level_symbols_by_name(self, name: str) -> list[RustCompactSymbol]:
        records = self._records_from_json_method("top_level_symbols_by_name_json", RustSymbolRecord.from_dict, name)
        if records is None:
            return [symbol for symbol in self.symbol_handles if symbol.is_top_level and symbol.name == name]
        return [self._symbol_handle_from_record(record) for record in records]

    def imports_for_file(self, file_id: int) -> list[RustCompactImport]:
        if self._import_handles is None and hasattr(self.index, "imports_for_file_json"):
            if self._imports_by_file_id is None:
                self._imports_by_file_id = {}
            if file_id not in self._imports_by_file_id:
                records = self._records_from_json_method("imports_for_file_json", RustImportRecord.from_dict, file_id)
                if records is not None:
                    self._imports_by_file_id[file_id] = [self._import_handle_from_record(record) for record in records]
                else:
                    self._import_handles = [self._import_handle_from_record(record) for record in self.imports]
            if file_id in self._imports_by_file_id:
                return self._imports_by_file_id[file_id]
        if self._imports_by_file_id is None:
            imports_by_file_id: dict[int, list[RustCompactImport]] = {}
            for import_handle in self.import_handles:
                imports_by_file_id.setdefault(import_handle.record.file_id, []).append(import_handle)
            self._imports_by_file_id = imports_by_file_id
        return self._imports_by_file_id.get(file_id, [])

    def imports_for_file_by_lookup(self, file_id: int, lookup: str) -> list[RustCompactImport]:
        if self._import_handles is None and hasattr(self.index, "imports_for_file_by_lookup_json"):
            if self._imports_by_file_id_and_lookup is None:
                self._imports_by_file_id_and_lookup = {}
            key = (file_id, lookup)
            if key not in self._imports_by_file_id_and_lookup:
                records = self._records_from_json_method("imports_for_file_by_lookup_json", RustImportRecord.from_dict, file_id, lookup)
                if records is not None:
                    self._imports_by_file_id_and_lookup[key] = [self._import_handle_from_record(record) for record in records]
                else:
                    self._import_handles = [self._import_handle_from_record(record) for record in self.imports]
            if key in self._imports_by_file_id_and_lookup:
                return self._imports_by_file_id_and_lookup[key]
        return [import_handle for import_handle in self.imports_for_file(file_id) if import_handle.matches_lookup(lookup)]

    def imports_for_file_by_byte_range(self, file_id: int, start_byte: int, end_byte: int) -> list[RustCompactImport]:
        if self._import_handles is None and hasattr(self.index, "imports_for_file_by_byte_range_json"):
            if self._imports_by_file_id_and_byte_range is None:
                self._imports_by_file_id_and_byte_range = {}
            key = (file_id, start_byte, end_byte)
            if key not in self._imports_by_file_id_and_byte_range:
                records = self._records_from_json_method("imports_for_file_by_byte_range_json", RustImportRecord.from_dict, file_id, start_byte, end_byte)
                if records is not None:
                    self._imports_by_file_id_and_byte_range[key] = [self._import_handle_from_record(record) for record in records]
                else:
                    self._import_handles = [self._import_handle_from_record(record) for record in self.imports]
            if key in self._imports_by_file_id_and_byte_range:
                return self._imports_by_file_id_and_byte_range[key]
        return [import_handle for import_handle in self.imports_for_file(file_id) if _ranges_overlap(import_handle.range, start_byte, end_byte)]

    def exports_for_file(self, file_id: int) -> list[RustCompactExport]:
        if self._export_handles is None and hasattr(self.index, "exports_for_file_json"):
            if self._exports_by_file_id is None:
                self._exports_by_file_id = {}
            if file_id not in self._exports_by_file_id:
                records = self._records_from_json_method("exports_for_file_json", RustExportRecord.from_dict, file_id)
                if records is not None:
                    self._exports_by_file_id[file_id] = [self._export_handle_from_record(record) for record in records]
                else:
                    self._export_handles = [self._export_handle_from_record(record) for record in self.exports]
            if file_id in self._exports_by_file_id:
                return self._exports_by_file_id[file_id]
        if self._exports_by_file_id is None:
            exports_by_file_id: dict[int, list[RustCompactExport]] = {}
            for export_handle in self.export_handles:
                exports_by_file_id.setdefault(export_handle.record.file_id, []).append(export_handle)
            self._exports_by_file_id = exports_by_file_id
        return self._exports_by_file_id.get(file_id, [])

    def exports_for_file_by_name(self, file_id: int, name: str) -> list[RustCompactExport]:
        if self._export_handles is None and hasattr(self.index, "exports_for_file_by_name_json"):
            if self._exports_by_file_id_and_name is None:
                self._exports_by_file_id_and_name = {}
            key = (file_id, name)
            if key not in self._exports_by_file_id_and_name:
                records = self._records_from_json_method("exports_for_file_by_name_json", RustExportRecord.from_dict, file_id, name)
                if records is not None:
                    self._exports_by_file_id_and_name[key] = [self._export_handle_from_record(record) for record in records]
                else:
                    self._export_handles = [self._export_handle_from_record(record) for record in self.exports]
            if key in self._exports_by_file_id_and_name:
                return self._exports_by_file_id_and_name[key]
        return [export_handle for export_handle in self.exports_for_file(file_id) if export_handle.name == name]

    def exports_for_file_by_byte_range(self, file_id: int, start_byte: int, end_byte: int) -> list[RustCompactExport]:
        if self.summary.exports == 0:
            return []
        if self._export_handles is None and hasattr(self.index, "exports_for_file_by_byte_range_json"):
            if self._exports_by_file_id_and_byte_range is None:
                self._exports_by_file_id_and_byte_range = {}
            key = (file_id, start_byte, end_byte)
            if key not in self._exports_by_file_id_and_byte_range:
                records = self._records_from_json_method("exports_for_file_by_byte_range_json", RustExportRecord.from_dict, file_id, start_byte, end_byte)
                if records is not None:
                    self._exports_by_file_id_and_byte_range[key] = [self._export_handle_from_record(record) for record in records]
                else:
                    self._export_handles = [self._export_handle_from_record(record) for record in self.exports]
            if key in self._exports_by_file_id_and_byte_range:
                return self._exports_by_file_id_and_byte_range[key]
        return [export_handle for export_handle in self.exports_for_file(file_id) if _ranges_overlap(export_handle.range, start_byte, end_byte)]

    def exports_for_symbol(self, symbol_id: int) -> list[RustCompactExport]:
        if self.summary.exports == 0:
            return []
        if self._export_handles is None and hasattr(self.index, "exports_for_symbol_json"):
            if self._exports_by_symbol_id is None:
                self._exports_by_symbol_id = {}
            if symbol_id not in self._exports_by_symbol_id:
                records = self._records_from_json_method("exports_for_symbol_json", RustExportRecord.from_dict, symbol_id)
                if records is not None:
                    self._exports_by_symbol_id[symbol_id] = [self._export_handle_from_record(record) for record in records]
                else:
                    self._export_handles = [self._export_handle_from_record(record) for record in self.exports]
            if symbol_id in self._exports_by_symbol_id:
                return self._exports_by_symbol_id[symbol_id]
        if self._exports_by_symbol_id is None:
            exports_by_symbol_id: dict[int, list[RustCompactExport]] = {}
            for export_handle in self.export_handles:
                if export_handle.record.symbol_id is not None:
                    exports_by_symbol_id.setdefault(export_handle.record.symbol_id, []).append(export_handle)
            self._exports_by_symbol_id = exports_by_symbol_id
        return self._exports_by_symbol_id.get(symbol_id, [])

    def nodes_for_file_by_byte_range(self, file_id: int, start_byte: int, end_byte: int) -> list[RustCompactImport | RustCompactExport | RustCompactSymbol]:
        nodes: list[RustCompactImport | RustCompactExport | RustCompactSymbol] = [
            *self.imports_for_file_by_byte_range(file_id, start_byte, end_byte),
            *self.exports_for_file_by_byte_range(file_id, start_byte, end_byte),
            *self.symbols_for_file_by_byte_range(file_id, start_byte, end_byte),
        ]
        return sorted(nodes, key=lambda node: (node.start_byte, node.end_byte, int(node.node_type), node.node_id))

    def file_handle_by_id(self, file_id: int) -> RustCompactFile | None:
        if file_id in self._removed_file_ids:
            return None
        if self._file_handles is None and hasattr(self.index, "file_by_id_json"):
            if self._file_handles_by_id is None:
                self._file_handles_by_id = {}
            if file_id not in self._file_handles_by_id:
                record = self._file_record_by_id(file_id)
                if record is not None:
                    return self._file_handle_from_record(record)
                return None
            if file_id in self._file_handles_by_id:
                return self._file_handles_by_id[file_id]
        if self._file_handles_by_id is None or file_id not in self._file_handles_by_id:
            self._file_handles_by_id = {file.record.id: file for file in self.file_handles}
        return self._file_handles_by_id.get(file_id)

    def symbol_handle_by_id(self, symbol_id: int) -> RustCompactSymbol | None:
        if self._symbol_handles is None and hasattr(self.index, "symbol_by_id_json"):
            if self._symbol_handles_by_id is None:
                self._symbol_handles_by_id = {}
            if symbol_id not in self._symbol_handles_by_id:
                record = self._symbol_record_by_id(symbol_id)
                if record is not None:
                    return self._symbol_handle_from_record(record)
                return None
            if symbol_id in self._symbol_handles_by_id:
                return self._symbol_handles_by_id[symbol_id]
        if self._symbol_handles_by_id is None or symbol_id not in self._symbol_handles_by_id:
            self._symbol_handles_by_id = {symbol.record.id: symbol for symbol in self.symbol_handles}
        return self._symbol_handles_by_id.get(symbol_id)

    def import_handle_by_id(self, import_id: int) -> RustCompactImport | None:
        if self._import_handles is None and hasattr(self.index, "import_by_id_json"):
            if self._import_handles_by_id is None:
                self._import_handles_by_id = {}
            if import_id not in self._import_handles_by_id:
                record = self._import_record_by_id(import_id)
                if record is not None:
                    return self._import_handle_from_record(record)
                return None
            if import_id in self._import_handles_by_id:
                return self._import_handles_by_id[import_id]
        if self._import_handles_by_id is None or import_id not in self._import_handles_by_id:
            self._import_handles_by_id = {import_handle.record.id: import_handle for import_handle in self.import_handles}
        return self._import_handles_by_id.get(import_id)

    def external_module_for_import(self, import_id: int) -> RustCompactExternalModule | None:
        if self._external_module_handles is None and hasattr(self.index, "external_module_for_import_json"):
            if self._external_module_handles_by_import_id is None:
                self._external_module_handles_by_import_id = {}
            if import_id not in self._external_module_handles_by_import_id:
                record = self._record_from_json_method("external_module_for_import_json", RustExternalModuleRecord.from_dict, import_id)
                if record is not None:
                    return self._external_module_handle_from_record(record)
                return None
            if import_id in self._external_module_handles_by_import_id:
                return self._external_module_handles_by_import_id[import_id]
        if self._external_module_handles_by_import_id is None or import_id not in self._external_module_handles_by_import_id:
            self._external_module_handles_by_import_id = {external_module.record.import_id: external_module for external_module in self.external_module_handles}
        return self._external_module_handles_by_import_id.get(import_id)

    def export_handle_by_id(self, export_id: int) -> RustCompactExport | None:
        if self._export_handles is None and hasattr(self.index, "export_by_id_json"):
            if self._export_handles_by_id is None:
                self._export_handles_by_id = {}
            if export_id not in self._export_handles_by_id:
                record = self._export_record_by_id(export_id)
                if record is not None:
                    return self._export_handle_from_record(record)
                return None
            if export_id in self._export_handles_by_id:
                return self._export_handles_by_id[export_id]
        if self._export_handles_by_id is None or export_id not in self._export_handles_by_id:
            self._export_handles_by_id = {export_handle.record.id: export_handle for export_handle in self.export_handles}
        return self._export_handles_by_id.get(export_id)

    def import_resolution_for_import(self, import_id: int) -> RustImportResolutionRecord | None:
        if self._import_resolutions is None and hasattr(self.index, "import_resolution_for_import_json"):
            if self._import_resolutions_by_import_id is None:
                self._import_resolutions_by_import_id = {}
            if import_id not in self._import_resolutions_by_import_id:
                record = self._record_from_json_method("import_resolution_for_import_json", RustImportResolutionRecord.from_dict, import_id)
                if record is not None:
                    self._import_resolutions_by_import_id[record.import_id] = record
                else:
                    return None
            if import_id in self._import_resolutions_by_import_id:
                return self._import_resolutions_by_import_id[import_id]
        if self._import_resolutions_by_import_id is None:
            self._import_resolutions_by_import_id = {resolution.import_id: resolution for resolution in self.import_resolutions}
        return self._import_resolutions_by_import_id.get(import_id)

    def import_resolutions_to_file(self, file_id: int) -> list[RustImportResolutionRecord]:
        if self._import_resolutions is None and hasattr(self.index, "import_resolutions_to_file_json"):
            if self._import_resolutions_by_target_file_id is None:
                self._import_resolutions_by_target_file_id = {}
            if file_id not in self._import_resolutions_by_target_file_id:
                records = self._records_from_json_method("import_resolutions_to_file_json", RustImportResolutionRecord.from_dict, file_id)
                if records is not None:
                    self._import_resolutions_by_target_file_id[file_id] = records
            if file_id in self._import_resolutions_by_target_file_id:
                return self._import_resolutions_by_target_file_id[file_id]
        if self._import_resolutions_by_target_file_id is None:
            import_resolutions_by_target_file_id: dict[int, list[RustImportResolutionRecord]] = {}
            for resolution in self.import_resolutions:
                import_resolutions_by_target_file_id.setdefault(resolution.target_file_id, []).append(resolution)
            self._import_resolutions_by_target_file_id = import_resolutions_by_target_file_id
        return self._import_resolutions_by_target_file_id.get(file_id, [])

    def import_resolutions_to_symbol(self, symbol_id: int) -> list[RustImportResolutionRecord]:
        if self._import_resolutions is None and hasattr(self.index, "import_resolutions_to_symbol_json"):
            if self._import_resolutions_by_target_symbol_id is None:
                self._import_resolutions_by_target_symbol_id = {}
            if symbol_id not in self._import_resolutions_by_target_symbol_id:
                records = self._records_from_json_method("import_resolutions_to_symbol_json", RustImportResolutionRecord.from_dict, symbol_id)
                if records is not None:
                    self._import_resolutions_by_target_symbol_id[symbol_id] = records
            if symbol_id in self._import_resolutions_by_target_symbol_id:
                return self._import_resolutions_by_target_symbol_id[symbol_id]
        if self._import_resolutions_by_target_symbol_id is None:
            import_resolutions_by_target_symbol_id: dict[int, list[RustImportResolutionRecord]] = {}
            for resolution in self.import_resolutions:
                if resolution.target_symbol_id is not None:
                    import_resolutions_by_target_symbol_id.setdefault(resolution.target_symbol_id, []).append(resolution)
            self._import_resolutions_by_target_symbol_id = import_resolutions_by_target_symbol_id
        return self._import_resolutions_by_target_symbol_id.get(symbol_id, [])

    def references_to_symbol(self, symbol_id: int) -> list[RustReferenceRecord]:
        if self._references is None and hasattr(self.index, "references_to_symbol_json"):
            if self._references_by_target_symbol_id is None:
                self._references_by_target_symbol_id = {}
            if symbol_id not in self._references_by_target_symbol_id:
                records = self._records_from_json_method("references_to_symbol_json", RustReferenceRecord.from_dict, symbol_id)
                if records is not None:
                    self._references_by_target_symbol_id[symbol_id] = records
            if symbol_id in self._references_by_target_symbol_id:
                return self._references_by_target_symbol_id[symbol_id]
        if self._references_by_target_symbol_id is None:
            references_by_target_symbol_id: dict[int, list[RustReferenceRecord]] = {}
            for reference in self.references:
                references_by_target_symbol_id.setdefault(reference.target_symbol_id, []).append(reference)
            self._references_by_target_symbol_id = references_by_target_symbol_id
        return self._references_by_target_symbol_id.get(symbol_id, [])

    def references_from_symbol(self, symbol_id: int) -> list[RustReferenceRecord]:
        if self._references is None and hasattr(self.index, "references_from_symbol_json"):
            if self._references_by_source_symbol_id is None:
                self._references_by_source_symbol_id = {}
            if symbol_id not in self._references_by_source_symbol_id:
                records = self._records_from_json_method("references_from_symbol_json", RustReferenceRecord.from_dict, symbol_id)
                if records is not None:
                    self._references_by_source_symbol_id[symbol_id] = records
            if symbol_id in self._references_by_source_symbol_id:
                return self._references_by_source_symbol_id[symbol_id]
        if self._references_by_source_symbol_id is None:
            references_by_source_symbol_id: dict[int, list[RustReferenceRecord]] = {}
            for reference in self.references:
                if reference.source_symbol_id is not None:
                    references_by_source_symbol_id.setdefault(reference.source_symbol_id, []).append(reference)
            self._references_by_source_symbol_id = references_by_source_symbol_id
        return self._references_by_source_symbol_id.get(symbol_id, [])

    def references_for_import(self, import_id: int) -> list[RustReferenceRecord]:
        if self._references is None and hasattr(self.index, "references_for_import_json"):
            if self._references_by_import_id is None:
                self._references_by_import_id = {}
            if import_id not in self._references_by_import_id:
                records = self._records_from_json_method("references_for_import_json", RustReferenceRecord.from_dict, import_id)
                if records is not None:
                    self._references_by_import_id[import_id] = records
            if import_id in self._references_by_import_id:
                return self._references_by_import_id[import_id]
        if self._references_by_import_id is None:
            references_by_import_id: dict[int, list[RustReferenceRecord]] = {}
            for reference in self.references:
                if reference.import_id is not None:
                    references_by_import_id.setdefault(reference.import_id, []).append(reference)
            self._references_by_import_id = references_by_import_id
        return self._references_by_import_id.get(import_id, [])

    def reference_by_id(self, reference_id: int) -> RustReferenceRecord | None:
        if self._references is None and hasattr(self.index, "reference_by_id_json"):
            if self._references_by_id is None:
                self._references_by_id = {}
            if reference_id not in self._references_by_id:
                record = self._record_from_json_method("reference_by_id_json", RustReferenceRecord.from_dict, reference_id)
                if record is not None:
                    self._references_by_id[record.id] = record
                else:
                    return None
            if reference_id in self._references_by_id:
                return self._references_by_id[reference_id]
        if self._references_by_id is None:
            self._references_by_id = {reference.id: reference for reference in self.references}
        return self._references_by_id.get(reference_id)

    def external_references_from_symbol(self, symbol_id: int) -> list[RustExternalReferenceRecord]:
        if self._external_references is None and hasattr(self.index, "external_references_from_symbol_json"):
            if self._external_references_by_source_symbol_id is None:
                self._external_references_by_source_symbol_id = {}
            if symbol_id not in self._external_references_by_source_symbol_id:
                records = self._records_from_json_method("external_references_from_symbol_json", RustExternalReferenceRecord.from_dict, symbol_id)
                if records is not None:
                    self._external_references_by_source_symbol_id[symbol_id] = records
            if symbol_id in self._external_references_by_source_symbol_id:
                return self._external_references_by_source_symbol_id[symbol_id]
        if self._external_references_by_source_symbol_id is None:
            references_by_source_symbol_id: dict[int, list[RustExternalReferenceRecord]] = {}
            for reference in self.external_references:
                if reference.source_symbol_id is not None:
                    references_by_source_symbol_id.setdefault(reference.source_symbol_id, []).append(reference)
            self._external_references_by_source_symbol_id = references_by_source_symbol_id
        return self._external_references_by_source_symbol_id.get(symbol_id, [])

    def external_references_for_import(self, import_id: int) -> list[RustExternalReferenceRecord]:
        if self._external_references is None and hasattr(self.index, "external_references_for_import_json"):
            if self._external_references_by_import_id is None:
                self._external_references_by_import_id = {}
            if import_id not in self._external_references_by_import_id:
                records = self._records_from_json_method("external_references_for_import_json", RustExternalReferenceRecord.from_dict, import_id)
                if records is not None:
                    self._external_references_by_import_id[import_id] = records
            if import_id in self._external_references_by_import_id:
                return self._external_references_by_import_id[import_id]
        if self._external_references_by_import_id is None:
            references_by_import_id: dict[int, list[RustExternalReferenceRecord]] = {}
            for reference in self.external_references:
                references_by_import_id.setdefault(reference.import_id, []).append(reference)
            self._external_references_by_import_id = references_by_import_id
        return self._external_references_by_import_id.get(import_id, [])

    def dependencies_from_symbol(self, symbol_id: int) -> list[RustDependencyRecord]:
        if self._dependencies is None and hasattr(self.index, "dependencies_from_symbol_json"):
            if self._dependencies_by_source_symbol_id is None:
                self._dependencies_by_source_symbol_id = {}
            if symbol_id not in self._dependencies_by_source_symbol_id:
                records = self._records_from_json_method("dependencies_from_symbol_json", RustDependencyRecord.from_dict, symbol_id)
                if records is not None:
                    self._dependencies_by_source_symbol_id[symbol_id] = records
            if symbol_id in self._dependencies_by_source_symbol_id:
                return self._dependencies_by_source_symbol_id[symbol_id]
        if self._dependencies_by_source_symbol_id is None:
            dependencies_by_source_symbol_id: dict[int, list[RustDependencyRecord]] = {}
            for dependency in self.dependencies:
                dependencies_by_source_symbol_id.setdefault(dependency.source_symbol_id, []).append(dependency)
            self._dependencies_by_source_symbol_id = dependencies_by_source_symbol_id
        return self._dependencies_by_source_symbol_id.get(symbol_id, [])

    def dependencies_to_symbol(self, symbol_id: int) -> list[RustDependencyRecord]:
        if self._dependencies is None and hasattr(self.index, "dependencies_to_symbol_json"):
            if self._dependencies_by_target_symbol_id is None:
                self._dependencies_by_target_symbol_id = {}
            if symbol_id not in self._dependencies_by_target_symbol_id:
                records = self._records_from_json_method("dependencies_to_symbol_json", RustDependencyRecord.from_dict, symbol_id)
                if records is not None:
                    self._dependencies_by_target_symbol_id[symbol_id] = records
            if symbol_id in self._dependencies_by_target_symbol_id:
                return self._dependencies_by_target_symbol_id[symbol_id]
        if self._dependencies_by_target_symbol_id is None:
            dependencies_by_target_symbol_id: dict[int, list[RustDependencyRecord]] = {}
            for dependency in self.dependencies:
                dependencies_by_target_symbol_id.setdefault(dependency.target_symbol_id, []).append(dependency)
            self._dependencies_by_target_symbol_id = dependencies_by_target_symbol_id
        return self._dependencies_by_target_symbol_id.get(symbol_id, [])

    def subclass_edges_from_symbol(self, symbol_id: int) -> list[RustSubclassRecord]:
        if self._subclass_edges is None and hasattr(self.index, "subclass_edges_from_symbol_json"):
            if self._subclass_edges_by_source_symbol_id is None:
                self._subclass_edges_by_source_symbol_id = {}
            if symbol_id not in self._subclass_edges_by_source_symbol_id:
                records = self._records_from_json_method("subclass_edges_from_symbol_json", RustSubclassRecord.from_dict, symbol_id)
                if records is not None:
                    self._subclass_edges_by_source_symbol_id[symbol_id] = records
            if symbol_id in self._subclass_edges_by_source_symbol_id:
                return self._subclass_edges_by_source_symbol_id[symbol_id]
        if self._subclass_edges_by_source_symbol_id is None:
            subclass_edges_by_source_symbol_id: dict[int, list[RustSubclassRecord]] = {}
            for edge in self.subclass_edges:
                subclass_edges_by_source_symbol_id.setdefault(edge.source_symbol_id, []).append(edge)
            self._subclass_edges_by_source_symbol_id = subclass_edges_by_source_symbol_id
        return self._subclass_edges_by_source_symbol_id.get(symbol_id, [])

    def subclass_edges_to_symbol(self, symbol_id: int) -> list[RustSubclassRecord]:
        if self._subclass_edges is None and hasattr(self.index, "subclass_edges_to_symbol_json"):
            if self._subclass_edges_by_target_symbol_id is None:
                self._subclass_edges_by_target_symbol_id = {}
            if symbol_id not in self._subclass_edges_by_target_symbol_id:
                records = self._records_from_json_method("subclass_edges_to_symbol_json", RustSubclassRecord.from_dict, symbol_id)
                if records is not None:
                    self._subclass_edges_by_target_symbol_id[symbol_id] = records
            if symbol_id in self._subclass_edges_by_target_symbol_id:
                return self._subclass_edges_by_target_symbol_id[symbol_id]
        if self._subclass_edges_by_target_symbol_id is None:
            subclass_edges_by_target_symbol_id: dict[int, list[RustSubclassRecord]] = {}
            for edge in self.subclass_edges:
                subclass_edges_by_target_symbol_id.setdefault(edge.target_symbol_id, []).append(edge)
            self._subclass_edges_by_target_symbol_id = subclass_edges_by_target_symbol_id
        return self._subclass_edges_by_target_symbol_id.get(symbol_id, [])

    def to_json(self) -> str:
        return str(self.index.to_json())

    def debug_graph_json(self) -> str:
        debug_graph_json = getattr(self.index, "debug_graph_json", None)
        if debug_graph_json is None:
            return self.to_json()
        return str(debug_graph_json())


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
        current_span = self._current_span(old_name)
        if current_span is None:
            return

        start_byte, end_byte = current_span
        transaction = EditTransaction(
            start_byte,
            end_byte,
            self.file,
            new_name,
            priority=priority,
        )
        self.file.transaction_manager.add_transaction(transaction)

    def _current_span(self, name: str) -> tuple[int, int] | None:
        content_bytes = self.file.content_bytes
        start_byte = self.record.range.start_byte
        end_byte = self.record.range.end_byte
        if content_bytes[start_byte:end_byte].decode("utf-8", errors="ignore") == name:
            return start_byte, end_byte
        return _find_identifier_span_near(self.file.content, name, start_byte)


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


def _is_identifier_char(char: str) -> bool:
    return char.isalnum() or char in {"_", "$"}


def _find_identifier_span_near(content: str, name: str, preferred_start_byte: int) -> tuple[int, int] | None:
    if not name:
        return None

    spans: list[tuple[int, int]] = []
    start_index = 0
    while True:
        index = content.find(name, start_index)
        if index == -1:
            break

        before = content[index - 1] if index > 0 else ""
        after_index = index + len(name)
        after = content[after_index] if after_index < len(content) else ""
        if not _is_identifier_char(before) and not _is_identifier_char(after):
            start_byte = len(content[:index].encode("utf-8"))
            end_byte = start_byte + len(name.encode("utf-8"))
            spans.append((start_byte, end_byte))
        start_index = index + len(name)

    if not spans:
        return None
    return min(spans, key=lambda span: (abs(span[0] - preferred_start_byte), span[0]))


def _find_prefixed_identifier_span(content: str, name: str, prefix: str) -> tuple[int, int] | None:
    pattern = f"{prefix}{name}"
    start_index = 0
    while True:
        index = content.find(pattern, start_index)
        if index == -1:
            return None

        name_index = index + len(prefix)
        after_index = name_index + len(name)
        after = content[after_index] if after_index < len(content) else ""
        if not _is_identifier_char(after):
            start_byte = len(content[:name_index].encode("utf-8"))
            end_byte = start_byte + len(name.encode("utf-8"))
            return start_byte, end_byte
        start_index = index + len(pattern)


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


def _is_typescript_like_extension(extension: str) -> bool:
    return extension in {".ts", ".tsx", ".js", ".jsx"}


def _typescript_module_literal(module: str) -> str:
    stripped = module.strip("\"'")
    return f"'{stripped}'"


def _typescript_import_string(
    *,
    name: str | None,
    file_name: str,
    module: str,
    alias: str | None = None,
    import_type: ImportType = ImportType.UNKNOWN,
    is_type_import: bool = False,
) -> str:
    module_literal = _typescript_module_literal(module)
    type_prefix = "type " if is_type_import else ""

    if import_type == ImportType.WILDCARD:
        namespace = alias or file_name
        return f"import {type_prefix}* as {namespace} from {module_literal};"
    if import_type == ImportType.DEFAULT_EXPORT:
        import_name = alias or name or file_name
        return f"import {type_prefix}{import_name} from {module_literal};"

    import_name = name or file_name
    if alias is not None and alias != import_name:
        return f"import {type_prefix}{{ {import_name} as {alias} }} from {module_literal};"
    return f"import {type_prefix}{{ {import_name} }} from {module_literal};"


def _line_count(source: str) -> int:
    if source == "":
        return 0
    return source.count("\n") + int(not source.endswith("\n"))


def _stable_content_hash(content: bytes) -> str:
    hash_value = 0xCBF29CE484222325
    for byte in content:
        hash_value ^= byte
        hash_value = (hash_value * 0x00000100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{hash_value:016x}"


def _rust_file_language_for_path(filepath: str) -> str:
    extension = Path(filepath).suffix
    if extension == ".py":
        return "python"
    if extension == ".ts":
        return "typescript"
    if extension == ".tsx":
        return "tsx"
    if extension == ".js":
        return "javascript"
    if extension == ".jsx":
        return "jsx"
    return ""


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
        return RustBackendUnsupportedError(method=method, handle=type(self).__name__)

    def _fallback_to_python(self, method: str, reason: str | None = None) -> None:
        if self.ctx is None:
            raise self._unsupported(method)
        self.ctx.promote_rust_compact_to_python(method=method, handle=type(self).__name__, reason=reason)

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
        if _is_typescript_like_extension(self.extension):
            return _typescript_import_string(
                name=symbol_name,
                file_name=symbol_name,
                module=import_module,
                alias=alias,
                import_type=ImportType.WILDCARD,
                is_type_import=is_type_import,
            )

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
            python_file = self._python_file_after_fallback(method)
            return python_file.replace(old, new, count=count, is_regex=is_regex, priority=priority)
        if old not in self.content:
            return 0
        replacement_count = self.content.count(old) if count == -1 else min(self.content.count(old), count)
        self.edit(self.content.replace(old, new, count), priority=priority)
        return replacement_count

    def _python_file_after_fallback(self, method: str) -> Any:
        self._fallback_to_python(method)
        if self.ctx is None:
            raise self._unsupported(method)
        file = self.ctx.get_file(self.filepath)
        if file is None:
            msg = f"File {self.filepath} was not found after falling back to the Python graph backend"
            raise RuntimeError(msg)
        return file

    def remove(self) -> None:
        self.transaction_manager.add_file_remove_transaction(self)
        self.backend.unregister_file(self.record.id, self.record.path)

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

        return self._line_start_byte(self.imports[0].record.range.start_row), f"{import_line}\n"

    def _line_start_byte(self, row: int) -> int:
        offsets = _line_byte_offsets(self.content)
        if not offsets:
            return 0
        if row >= len(offsets):
            return len(self.content_bytes)
        return offsets[row]

    def add_symbol_from_source(self, source: str) -> None:
        symbol_source = source.rstrip("\n")
        if not symbol_source:
            return

        if not self.content:
            if not self._pending_imports:
                self.insert_at(0, f"\n\n{symbol_source}")
                return
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
        return next(iter(self.backend.exports_for_file_by_name(self.record.id, export_name)), None)

    def get_nodes(self, *, sort_by_id: bool = False, sort: bool = True) -> list[RustCompactImport | RustCompactExport | RustCompactSymbol]:
        nodes: list[RustCompactImport | RustCompactExport | RustCompactSymbol] = [*self.imports, *self.exports, *self.backend.symbols_for_file(self.record.id)]
        if not sort:
            return nodes

        if sort_by_id:
            return sorted(nodes, key=lambda node: (node.node_id, int(node.node_type), node.start_byte, node.end_byte))
        return sorted(nodes, key=lambda node: (node.start_byte, node.end_byte, int(node.node_type), node.node_id))

    def find_by_byte_range(self, range: Any) -> list[RustCompactImport | RustCompactExport | RustCompactSymbol]:
        start_byte, end_byte = _byte_range_bounds(range)
        return self.backend.nodes_for_file_by_byte_range(self.record.id, start_byte, end_byte)

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

    def _resolve_valid_symbol_name(self, name: str) -> RustCompactImport | RustCompactSymbol | None:
        for import_handle in self.backend.imports_for_file_by_lookup(self.record.id, name):
            for import_name, destination in import_handle.names:
                if import_name == name:
                    return destination
        return next(
            (symbol for symbol in self.backend.symbols_for_file_by_name(self.record.id, name) if symbol.is_top_level and symbol.full_name == name),
            None,
        )

    def resolve_name(self, name: str, start_byte: int | None = None, strict: bool = True) -> Any:
        resolved = self._resolve_valid_symbol_name(name)
        if resolved is None:
            return

        if start_byte is not None and resolved.end_byte > start_byte:
            symbols = sorted(
                self.backend.symbols_for_file_by_name(self.record.id, name),
                key=lambda symbol: (symbol.start_byte, symbol.end_byte, symbol.node_id),
                reverse=True,
            )
            for symbol in symbols:
                symbol_boundary = symbol.start_byte if symbol.symbol_type in {SymbolType.Class, SymbolType.Function} else symbol.end_byte
                if symbol.name == name and symbol_boundary <= start_byte:
                    yield symbol
                    return
            if not strict:
                return
            return

        yield resolved

    def resolve_attribute(self, name: str) -> RustCompactImport | RustCompactSymbol | None:
        return self._resolve_valid_symbol_name(name)

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
        return next((symbol for symbol in self.backend.symbols_for_file_by_name(self.record.id, name) if symbol.is_top_level), None)

    def get_global_var(self, name: str) -> RustCompactSymbol | None:
        return next((symbol for symbol in self.backend.symbols_for_file_by_name(self.record.id, name) if symbol.is_top_level and symbol.symbol_type == SymbolType.GlobalVar), None)

    def get_class(self, name: str) -> RustCompactSymbol | None:
        return next((symbol for symbol in self.backend.symbols_for_file_by_name(self.record.id, name) if symbol.is_top_level and symbol.symbol_type == SymbolType.Class), None)

    def get_function(self, name: str) -> RustCompactSymbol | None:
        return next((symbol for symbol in self.backend.symbols_for_file_by_name(self.record.id, name) if symbol.is_top_level and symbol.symbol_type == SymbolType.Function), None)

    def has_import(self, symbol_alias: str) -> bool:
        return self.get_import(symbol_alias) is not None

    def get_import(self, symbol_alias: str) -> RustCompactImport | None:
        return next((import_handle for import_handle in self.backend.imports_for_file_by_lookup(self.record.id, symbol_alias) if import_handle.matches_lookup(symbol_alias)), None)

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
        self._name_start_byte = record.name_range.start_byte
        self._name_end_byte = record.name_range.end_byte
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
            if self._preserve_import_dependencies(target):
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

    def _preserve_import_dependencies(self, target: RustCompactSymbol) -> bool:
        if self.file.extension == ".py":
            return True
        return _is_typescript_like_extension(Path(self.filepath).suffix) and target.record.kind in {"interface", "type_alias"}

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

        def add_usage(handle: object | None) -> None:
            if handle is None or handle in seen:
                return
            seen.add(handle)
            symbol_usages.append(handle)

        if _is_typescript_like_extension(Path(self.filepath).suffix):
            for export_handle in self.backend.exports_for_symbol(self.record.id):
                add_usage(export_handle)

            for resolution in self.backend.import_resolutions_to_symbol(self.record.id):
                add_usage(self.backend.import_handle_by_id(resolution.import_id))

        for usage in self.usages(usage_types=usage_types):
            add_usage(usage.usage_symbol.parent_symbol)
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
                self._remove_after_move()
            return

        if strategy == "add_back_edge":
            if is_used_in_source_file or imported_usages:
                self.file.add_import(import_line)
            self._remove_after_move()
            return

        for usage in imported_usages:
            imported_by = usage.imported_by
            if imported_by is not None and imported_by.file != file:
                imported_by.file.add_import(import_line)
                imported_by.remove(delete_following_blank_line=True)

        if is_used_in_source_file:
            self.file.add_import(import_line)
        self._remove_after_move()

    def _remove_after_move(self) -> None:
        content_bytes = self.file.content_bytes
        suffix = content_bytes[self.end_byte :]
        if self.start_byte == 0 and suffix.strip() == b"":
            transaction = EditTransaction(0, len(content_bytes), self.file, "\n")
            self.transaction_manager.add_transaction(transaction)
            return
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
        start_byte, end_byte = self._current_name_span()
        transaction = EditTransaction(
            start_byte,
            end_byte,
            self.file,
            name,
            priority=priority,
        )
        self.transaction_manager.add_transaction(transaction)
        self.name = name
        self._name_node = RustCompactName(name)
        self._name_start_byte = start_byte
        self._name_end_byte = start_byte + len(name.encode("utf-8"))

    def rename(self, new_name: str, priority: int = 0) -> None:
        old_name = self.name
        self.set_name(new_name, priority=priority)
        for usage in self.usages(UsageType.DIRECT | UsageType.CHAINED):
            usage.match.rename_if_matching(old_name, new_name, priority=priority)

    def _current_name_span(self) -> tuple[int, int]:
        content_bytes = self.file.content_bytes
        if content_bytes[self._name_start_byte : self._name_end_byte].decode("utf-8", errors="ignore") == self.name:
            return self._name_start_byte, self._name_end_byte

        if content_bytes[self.record.name_range.start_byte : self.record.name_range.end_byte].decode("utf-8", errors="ignore") == self.name:
            return self.record.name_range.start_byte, self.record.name_range.end_byte

        if span := self._declaration_name_span():
            return span

        if span := _find_identifier_span_near(self.file.content, self.name, self.record.name_range.start_byte):
            return span

        msg = f"Cannot locate compact symbol name {self.name!r} in {self.filepath}"
        raise RuntimeError(msg)

    def _declaration_name_span(self) -> tuple[int, int] | None:
        prefixes_by_kind = {
            "class": ("class ",),
            "function": ("def ", "function "),
            "global_variable": ("",),
            "interface": ("interface ",),
            "type_alias": ("type ",),
            "enum": ("enum ",),
            "namespace": ("namespace ",),
        }
        for prefix in prefixes_by_kind.get(self.record.kind, ("",)):
            if not prefix:
                continue
            if span := _find_prefixed_identifier_span(self.file.content, self.name, prefix):
                return span
        return None

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
        if _is_typescript_like_extension(self.file.extension):
            return _typescript_import_string(
                name=self.name,
                file_name=self.file.name,
                module=import_module,
                alias=alias,
                import_type=import_type,
                is_type_import=is_type_import,
            )

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
        if _is_typescript_like_extension(self.file.extension):
            return self._statement_line()[0]
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
            return imported.resolve_attribute(attribute)
        if isinstance(imported, RustCompactExternalModule):
            return imported.resolve_attribute(attribute)
        return None

    def get_import_string(self, alias: str | None = None, module: str | None = None, import_type: ImportType = ImportType.UNKNOWN, is_type_import: bool = False) -> str:
        import_module = module if module is not None else self.file.import_module_name
        if _is_typescript_like_extension(self.file.extension):
            effective_import_type = self.import_type if import_type == ImportType.UNKNOWN else import_type
            return _typescript_import_string(
                name=self.name or self.import_specifier,
                file_name=self.file.name,
                module=import_module,
                alias=alias,
                import_type=effective_import_type,
                is_type_import=is_type_import,
            )

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
        return self.record.kind == "dynamic_import"

    @property
    def is_reexport(self) -> bool:
        return False

    def set_import_module(self, new_module: str) -> None:
        current_module = self._current_module_source()
        if current_module is None:
            return

        if _is_typescript_like_extension(self.file.extension):
            replacement = self._typescript_module_replacement(new_module)
            unquoted_module = current_module.strip("'\"`")
            quoted_candidates = [f"'{unquoted_module}'", f'"{unquoted_module}"', f"`{unquoted_module}`"]
            candidates = [current_module, *quoted_candidates, unquoted_module] if current_module[:1] in {"'", '"', "`"} else [*quoted_candidates, current_module]
        else:
            replacement = new_module
            candidates = [current_module]

        self._replace_first_line_fragment(candidates, replacement)
        self.module = RustCompactName(replacement if _is_typescript_like_extension(self.file.extension) else new_module)

    def set_import_symbol_alias(self, new_alias: str) -> None:
        if not self.is_aliased_import():
            self.rename(new_alias)
            return

        old_alias = self.alias.source if self.alias is not None else self.record.alias
        if old_alias is None:
            self.rename(new_alias)
            return

        self._replace_import_binding(old_alias, new_alias, imported_name=False)
        for imported_usage in self.usages:
            if imported_usage.match is not None:
                imported_usage.match.rename_if_matching(old_alias, new_alias)
        self.alias = RustCompactName(new_alias)

    def rename(self, new_name: str, priority: int = 0) -> None:
        old_name = self.import_specifier or self.name
        if old_name is None:
            return

        self._replace_import_binding(old_name, new_name, imported_name=True, priority=priority)
        if not self.is_aliased_import():
            for usage in self.usages:
                usage.match.rename_if_matching(old_name, new_name, priority=priority)
            self.alias = RustCompactName(new_name)
        self.symbol_name = RustCompactName(new_name)

    def _current_module_source(self) -> str | None:
        if self.module is not None:
            return self.module.source
        return self.record.module or (self.record.name if self.record.kind == "import" else None)

    @property
    def parent_symbol(self) -> RustCompactImport:
        return self

    @property
    def descendant_symbols(self) -> list[RustCompactImport]:
        return [self]

    def remove(self, priority: int = 0, *, delete_following_blank_line: bool = False) -> None:
        start_byte = self.start_byte
        end_byte = self.end_byte
        content = self.file.content
        lines = content.splitlines(keepends=True)
        line_offsets = _line_byte_offsets(content)
        row = self.record.range.start_row
        if row < len(lines) and row < len(line_offsets):
            start_byte = line_offsets[row]
            end_byte = line_offsets[row] + len(lines[row].encode("utf-8"))
            if delete_following_blank_line and row + 1 < len(lines) and not lines[row + 1].strip():
                end_byte += len(lines[row + 1].encode("utf-8"))

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

    def _statement_line(self) -> tuple[str, int]:
        content = self.file.content
        lines = content.splitlines(keepends=True)
        offsets = _line_byte_offsets(content)
        row = self.record.range.start_row
        if row < len(lines) and row < len(offsets):
            line = lines[row].rstrip("\r\n")
            if self._line_matches_import(line):
                return line, offsets[row]

        for line, offset in zip(lines, offsets, strict=False):
            stripped_line = line.rstrip("\r\n")
            if self._line_matches_import(stripped_line):
                return stripped_line, offset

        msg = f"Cannot locate import statement line for compact import {self.record.id}"
        raise RuntimeError(msg)

    def _line_matches_import(self, line: str) -> bool:
        if "import" not in line:
            return False

        fragments = {
            self.record.name,
            self.record.module,
            self.import_specifier,
            self.name,
            self.module.source if self.module is not None else None,
        }
        for fragment in list(fragments):
            if fragment is None:
                continue
            fragments.add(fragment.strip("'\"`"))

        return any(fragment and fragment in line for fragment in fragments)

    def _replace_first_line_fragment(self, candidates: list[str], replacement: str, *, priority: int = 0) -> None:
        line, line_start_byte = self._statement_line()
        for candidate in candidates:
            if not candidate:
                continue
            start_column = line.find(candidate)
            if start_column == -1:
                continue
            self._replace_line_span(line, line_start_byte, start_column, start_column + len(candidate), replacement, priority=priority)
            return

        msg = f"Cannot locate import fragment {candidates!r} in compact import line: {line!r}"
        raise RuntimeError(msg)

    def _replace_import_binding(self, old_name: str, new_name: str, *, imported_name: bool, priority: int = 0) -> None:
        line, line_start_byte = self._statement_line()
        start_column = self._find_import_binding_column(line, old_name, imported_name=imported_name)
        if start_column is None:
            msg = f"Cannot locate import binding {old_name!r} in compact import line: {line!r}"
            raise RuntimeError(msg)
        self._replace_line_span(line, line_start_byte, start_column, start_column + len(old_name), new_name, priority=priority)

    def _find_import_binding_column(self, line: str, name: str, *, imported_name: bool) -> int | None:
        current_alias = self.alias.source if self.alias is not None else self.record.alias
        current_symbol = self.symbol_name.source if self.symbol_name is not None else self.record.name

        if imported_name and current_alias and current_alias != current_symbol:
            pattern = f"{name} as {current_alias}"
            pattern_start = line.find(pattern)
            if pattern_start != -1:
                return pattern_start

        if not imported_name and current_symbol and current_alias and current_alias != current_symbol:
            pattern = f"{current_symbol} as {name}"
            pattern_start = line.find(pattern)
            if pattern_start != -1:
                return pattern_start + len(f"{current_symbol} as ")

        if imported_name and self.record.kind == "import":
            pattern = f"import {name}"
            pattern_start = line.find(pattern)
            if pattern_start != -1:
                return pattern_start + len("import ")

        if imported_name and self.record.kind == "default_import":
            pattern = f"import {name}"
            pattern_start = line.find(pattern)
            if pattern_start != -1:
                return pattern_start + len("import ")

        return line.find(name) if line.find(name) != -1 else None

    def _replace_line_span(self, line: str, line_start_byte: int, start_column: int, end_column: int, replacement: str, *, priority: int = 0) -> None:
        start_byte = line_start_byte + len(line[:start_column].encode("utf-8"))
        end_byte = line_start_byte + len(line[:end_column].encode("utf-8"))
        transaction = EditTransaction(
            start_byte,
            end_byte,
            self.file,
            replacement,
            priority=priority,
        )
        self.transaction_manager.add_transaction(transaction)

    @staticmethod
    def _typescript_module_replacement(new_module: str) -> str:
        if (new_module.startswith('"') and new_module.endswith('"')) or (new_module.startswith("'") and new_module.endswith("'")):
            return new_module
        quote = '"' if "'" in new_module else "'"
        return f"{quote}{new_module}{quote}"

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
        if _is_typescript_like_extension(self.file.extension):
            return {
                "default_import": ImportType.DEFAULT_EXPORT,
                "dynamic_import": ImportType.DEFAULT_EXPORT,
                "named_import": ImportType.NAMED_EXPORT,
                "namespace_import": ImportType.WILDCARD,
                "side_effect": ImportType.SIDE_EFFECT,
            }.get(self.record.kind, ImportType.UNKNOWN)
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
