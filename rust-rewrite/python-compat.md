# Python/PyO3 Compatibility Plan

## Objective

Preserve the current Python shell and codemod API while allowing a Rust engine to own canonical graph storage. The compatibility layer must not recreate today's full Python object graph when the Rust backend is selected. Python objects should be lightweight handles over Rust IDs and should only be created for files, symbols, imports, exports, or usages that user code actually accesses.

## Current Python Shape

Key findings from the current code:

- `Codebase` is the user facade. Public list properties such as `files`, `symbols`, `classes`, `functions`, `imports`, and `exports` mostly call `CodebaseContext.get_nodes(...)`, then sort/filter Python objects.
- `CodebaseContext` owns a `rustworkx.PyDiGraph` whose node payloads are Python objects. It also owns `filepath_idx`, directory state, parser/config/dependency managers, transaction state, and import/export/dependency graph mutation helpers.
- `SourceFile.__init__` immediately adds itself to the graph, parses the tree-sitter root, fills `file._nodes`, and registers the file path.
- `Importable.__init__` adds most child nodes to the graph and appends each child to `file._nodes`.
- `Editable` assumes a persistent `tree_sitter.Node`, `ctx`, `parent`, and `file_node_id`. Many inherited methods rely on `ts_node`, `parent`, and a populated Python graph.
- The compiled setup is Cython-based today under `graph_sitter.compiled`; wheel builds use a Hatch Cython hook. `cibuildwheel` already installs Rust toolchains, but no Rust extension build hook is active.

These constructors make "subclass the current objects and call `super().__init__`" the wrong default for Rust-backed objects. The Rust path needs separate lazy handle initialization that bypasses eager graph insertion and only materializes the Python tree on explicit fallback.

## Backend Flag Shape

Add a first-class graph backend setting to `CodebaseConfig` without changing the default behavior:

```python
class GraphBackend(StrEnum):
    PYTHON = "python"
    RUST = "rust"
    AUTO = "auto"


class RustFallbackMode(StrEnum):
    PYTHON = "python"
    ERROR = "error"


class CodebaseConfig(BaseConfig):
    graph_backend: GraphBackend = GraphBackend.PYTHON
    rust_fallback: RustFallbackMode = RustFallbackMode.PYTHON
```

Environment variables follow the existing `BaseConfig` prefix behavior:

- `CODEBASE_GRAPH_BACKEND=python|rust|auto`
- `CODEBASE_RUST_FALLBACK=python|error`

Selection policy:

- `python`: always use the current `PyDiGraph` backend.
- `rust`: require the PyO3 extension and supported language/config. If unavailable or unsupported, obey `rust_fallback`.
- `auto`: try Rust only when the language and config are known supported; otherwise use Python without warning unless debug logging is enabled.

`use_pink` should remain separate from `graph_backend`. Pink currently acts as an alternate file listing/file IO path for some modes, not as the graph engine. Initial Rust graph work should reject or fall back when `use_pink == PinkMode.ALL_FILES`, because `Codebase.files` is already delegated to `codegen_sdk_pink` in that mode.

## Backend Facade

Introduce a narrow internal facade owned by `CodebaseContext`:

```python
class GraphBackendFacade(Protocol):
    kind: Literal["python", "rust"]
    generation: int

    def build(self, repo_operator: RepoOperator) -> None: ...
    def apply_diffs(self, diff_list: list[DiffLite]) -> None: ...

    def get_file(self, file_path: os.PathLike, *, ignore_case: bool = False) -> SourceFile | None: ...
    def get_node(self, node_id: int) -> Importable: ...
    def get_nodes(self, node_type: NodeType | None = None, exclude_type: NodeType | None = None) -> list[Importable]: ...

    def successors(self, node_id: int, *, edge_type: EdgeType | None = None, sort: bool = True) -> Sequence[Importable]: ...
    def predecessors(self, node_id: int, edge_type: EdgeType | None = None) -> Sequence[Importable]: ...
    def in_edges(self, node_id: int) -> list[EdgeRecord]: ...
    def out_edges(self, node_id: int) -> list[EdgeRecord]: ...
```

Implementation split:

- `PythonGraphBackend` wraps the existing `CodebaseContext` graph fields and behavior. This is a mechanical extraction target and keeps default behavior identical.
- `RustGraphBackend` wraps a PyO3 `Engine` object and exposes the same query surface by converting Rust IDs into lazy Python handles.

Migration order:

1. Add the config flag and facade with `PythonGraphBackend` only.
2. Add PyO3 import smoke test and `RustGraphBackend.engine_version()`.
3. Route only read/list APIs through the facade.
4. Add Rust-backed query methods one family at a time.
5. Keep graph mutation and transaction-heavy APIs on Python or explicit fallback until Rust patch intents exist.

## PyO3 Surface

Expose a private extension module, for example `graph_sitter._rust`, with one main PyO3 class:

```python
class Engine:
    @staticmethod
    def version() -> str: ...

    def build(input: BuildInput) -> BuildReport: ...
    def apply_diffs(diffs: list[DiffRecord]) -> InvalidationReport: ...

    def files() -> list[int]: ...
    def symbols(kind: SymbolKind | None = None, top_level_only: bool = True) -> list[int]: ...
    def imports() -> list[int]: ...
    def exports() -> list[int]: ...

    def file_record(id: int) -> FileRecord: ...
    def symbol_record(id: int) -> SymbolRecord: ...
    def import_record(id: int) -> ImportRecord: ...
    def export_record(id: int) -> ExportRecord: ...

    def successors(object_ref: ObjectRef, edge_type: EdgeType | None) -> list[ObjectRef]: ...
    def predecessors(object_ref: ObjectRef, edge_type: EdgeType | None) -> list[ObjectRef]: ...
    def source_slice(file_id: int, start_byte: int, end_byte: int) -> str: ...
```

Current implemented bridge status:

- `crates/graph-sitter-py` builds a PyO3 module named `graph_sitter_py` behind the `extension-module` feature.
- `Engine.index_python_path(repo_path)` and module-level `index_python_path(repo_path)` return a compact `PythonIndex` for Python files.
- `Engine.index_python_paths(repo_path, file_paths)` and module-level `index_python_paths(repo_path, file_paths)` index an explicit Python file list. The Python shell integration uses this path so Rust sees the same `RepoOperator.iter_files(...)` selection as the current Python backend.
- `PythonIndex.summary()` returns `IndexSummary` with file, symbol, class, function, global-variable, import, import-resolution, reference, dependency, byte, line, and error counts.
- `PythonIndex.to_json()` serializes the compact Rust records for debug and benchmark use.
- `PythonIndex.files_json()`, `symbols_json()`, `imports_json()`, and `import_resolutions_json()` expose each record family without forcing callers to deserialize the full index payload.
- `PythonIndex.references_json()` exposes compact symbol reference records.
- `PythonIndex.dependencies_json()` exposes compact dependency edge records.
- `RustIndexBackend.files`, `.symbols`, `.imports`, `.import_resolutions`, `.references`, and `.dependencies` parse those record-family payloads into typed Python dataclasses for shell/debug/golden-test use.
- Rust currently emits compact `ImportResolutionRecord` rows for indexed internal Python modules: direct `import pkg.mod`, absolute `from pkg.mod import Symbol`, and relative `from .mod import Symbol` forms. Target symbols now include top-level classes, functions, and simple top-level globals.
- Rust currently emits compact `ReferenceRecord` rows for same-file and imported top-level symbol references inside Python symbols. Nested class/function records are used as source symbols when an identifier appears inside a method or nested function. Parameters, lambda parameters, local assignment targets, local imports, `for` targets, `with ... as ...` targets, `except ... as ...` targets, comprehension targets, match-pattern captures, and nested definitions shadow imported/top-level names in this pass. Full lexical scoping, attributes, and module references remain future work.
- Rust currently emits compact `DependencyRecord` rows by de-duplicating reference records into source-symbol to target-symbol edges with contributing reference IDs. Full lexical/reference coverage, external modules, and TypeScript remain future work.
- `CodebaseConfig(graph_backend="rust" | "auto")` builds a `CodebaseContext.rust_index` compact index when the extension is available and the codebase is Python.
- `CodebaseConfig(graph_backend="rust")` now keeps the eager Python graph unbuilt when the compact index succeeds. Raw Python graph APIs such as `CodebaseContext.nodes` remain blocked in that mode.
- `Codebase.rust_index_summary`, `.rust_files`, `.rust_symbols`, `.rust_classes`, `.rust_functions`, `.rust_global_vars`, `.rust_imports`, `.rust_import_resolutions`, `.rust_references`, and `.rust_dependencies` expose the attached compact records for shell smoke checks and golden tests.
- `Codebase.files`, `.symbols`, `.classes`, `.functions`, `.global_vars`, `.imports`, `get_file(...)`, `get_symbol(...)`, `get_class(...)`, and `get_function(...)` now return lightweight compact handles in strict Rust mode for Python codebases.
- Compact file handles expose basic identity/content plus file-local top-level `symbols`, `classes`, `functions`, `global_vars`, and `imports`; `file.symbols(nested=True)` exposes nested compact records. Compact symbol and import handles expose basic identity/source and implemented import-resolution targets. Edit-heavy and dependency/reference graph methods are still unsupported until the full lazy engine facade exists.
- This surface is a bridge for the compact-index vertical slice. It is not yet the final lazy `CodebaseContext` backend facade and it does not yet provide full P0 `SourceFile`, `Symbol`, or `Import` parity.

Rust can keep typed IDs internally. Python needs a compatibility `node_id: int`, so `RustGraphBackend` should maintain a per-context mapping between Python node IDs and typed Rust refs:

- `python_node_id -> ObjectRef(kind, rust_id)`
- `ObjectRef(kind, rust_id) -> python_node_id`

This preserves current APIs that pass `node_id` back to `ctx.get_node(...)` while avoiding assumptions that Rust IDs are globally interchangeable with today's `PyDiGraph` IDs.

## Lazy Handle Classes

Use a handle mixin plus concrete public-class subclasses to preserve `isinstance` behavior where practical:

```python
class RustHandleMixin:
    _ctx: CodebaseContext
    _backend: RustGraphBackend
    _ref: ObjectRef
    _node_id: int
    _generation: int
    _record_cache: object | None
    _materialized: Importable | None

    @property
    def node_id(self) -> int: ...
    def _record(self): ...
    def _ensure_current(self) -> None: ...
    def _materialize(self, reason: str) -> Importable: ...
```

Concrete handle classes:

- `RustSourceFile(RustHandleMixin, SourceFile)`
- `RustPyFile(RustSourceFile, PyFile)`
- `RustTSFile(RustSourceFile, TSFile)`
- `RustSymbol(RustHandleMixin, Symbol)`
- `RustPySymbol`, `RustTSSymbol`, plus class/function/interface/type/global-var variants as needed for user-visible type checks
- `RustImport(RustHandleMixin, Import)`
- `RustPyImport`, `RustTSImport`
- `RustExport(RustHandleMixin, Export)`, TypeScript only at first

These classes must not call the eager base constructors. Construction happens through a factory:

```python
handle = backend.handle_for(ObjectRef(kind="symbol", id=42))
```

The factory should use a `WeakValueDictionary` keyed by `(generation, kind, rust_id)` so repeated access can preserve object identity while alive without pinning every graph node in memory.

Field-backed P0 properties should read from Rust records and avoid materialization:

- common: `node_id`, `node_type`, `filepath`, `file_path`, `path`, `name`, `source`, `start_byte`, `end_byte`, `start_point`, `end_point`, `range`
- files: `content`, `content_bytes`, `extension`, `imports`, `symbols`, TypeScript `exports`
- symbols: `symbol_type`, `full_name`, `is_top_level`, `file`, `parent_symbol` when Rust has parent IDs
- imports: `module`, `symbol_name`, `alias`, `import_type`, `from_file`, `to_file`, `imported_symbol`, `resolved_symbol`
- exports: `name`, `exported_name`, `exported_symbol`, `resolved_symbol`, `is_named_export`, `is_module_export`

Properties that need `ts_node`, `code_block`, arbitrary parent traversal, formatting-specific edit behavior, or Python-only resolver details should call `_materialize(...)` or raise in strict mode.

## Lazy Object Lifecycle

1. `Codebase` construction creates `CodebaseContext`.
2. `CodebaseContext` resolves the backend from config.
3. Python backend follows the existing eager graph path.
4. Rust backend builds Rust indexes and records, but no Python `SourceFile`, `Symbol`, `Import`, or `Export` objects are created during build.
5. Public list queries ask the engine for sorted IDs and wrap only those returned IDs in handles.
6. Handle metadata is loaded on first property access and cached per handle.
7. Nested queries are also ID based. For example, `file.symbols` asks Rust for symbol IDs in that file and wraps only those IDs.
8. A handle records the backend generation. After `apply_diffs`, handles either rebind through stable IDs or become outdated and follow the existing stale-node semantics.
9. If user code requests unsupported Python behavior, the handle uses the fallback policy below.

Avoiding full materialization:

- Do not keep `file._nodes` for Rust-backed files. Expose `get_nodes(...)` by querying Rust for IDs.
- Do not create persistent Python `tree_sitter.Node` wrappers for every record. Use ranges and source slices.
- Do not back Rust handles with `PyDiGraph` node payloads. If a compatibility `node_id` is needed, it is a facade ID, not a graph index.
- Do not call `sort_editables` on a hidden eager graph. Either engine returns stable sorted IDs, or handles expose the small set of sort fields needed by existing callers.

## Fallback Policy

Fallback has two levels.

Cold fallback:

- Used when the Rust extension is missing, the language/config is unsupported, engine build fails, or `use_pink == PinkMode.ALL_FILES`.
- If `rust_fallback == "python"` or `graph_backend == "auto"`, log the reason and build the current Python backend.
- If `rust_fallback == "error"` and `graph_backend == "rust"`, raise a `RustBackendUnavailableError` with the exact unsupported feature or import/build failure.

Method fallback:

- Read-only, file-local unsupported behavior can materialize one file through the current parser, locate the matching Python object by `(kind, range, name)`, and delegate the method.
- Graph-wide unsupported behavior, dependency recomputation, and resolver operations that require a populated `PyDiGraph` should promote the whole context to the Python backend unless strict mode is enabled.
- Mutations should initially prefer Python promotion. Direct Rust-handle range edits can come later as patch intents, but structural helpers such as `move_to_file`, `add_import`, `remove_unused_exports`, or usage-based `rename` need Python graph semantics until Rust owns those flows.
- On any promotion, clear Rust handle caches, increment context generation, and make old handles outdated rather than half-valid.

Strict behavior:

- In `rust_fallback == "error"`, unsupported method access raises `RustBackendUnsupportedError(method=..., handle=..., reason=...)`.
- Tests should run some parity slices in strict mode to catch accidental Python promotion.

## Packaging Impact

Current packaging state:

- `hatch.toml` uses a Hatch Cython hook to compile selected `graph_sitter.compiled` modules.
- `pyproject.toml` uses `hatchling.build`.
- `cibuildwheel` already installs Rust on Linux and macOS, but no PyO3 build hook is configured.

Recommended packaging path:

- Add a Rust workspace with `graph_sitter_engine` and `graph_sitter_py`.
- Publish the PyO3 module as `graph_sitter._rust` so the public package namespace stays stable.
- Keep the extension optional at import time. Default `graph_backend="python"` must work without the Rust binary.
- Use a Hatch-compatible Rust build hook or a small custom Hatch hook that invokes `maturin` for the PyO3 crate and adds the built extension to wheel artifacts.
- Add `maturin` or the selected hook to `build-system.requires` and build hook dependencies when implementation starts.
- Ensure `sdist` includes `Cargo.toml`, `Cargo.lock` if policy chooses locked builds, crate sources, and any tree-sitter grammar inputs required by Rust.
- Keep Cython modules in place. The Rust handle layer can still import `graph_sitter.compiled.sort`, `autocommit`, and `utils` for the Python backend and fallback paths.
- Start with CPython-version-specific wheels rather than `abi3` unless PyO3 and tree-sitter dependencies are confirmed compatible with `abi3`.
- Add a CI smoke job that imports `graph_sitter._rust`, checks `Engine.version()`, and builds a minimal Python fixture with `CODEBASE_GRAPH_BACKEND=rust`.

## Initial Tests

Config and selection:

- `CodebaseConfig().graph_backend == "python"` keeps current behavior.
- `CODEBASE_GRAPH_BACKEND=rust` selects Rust when the extension is importable.
- `graph_backend="auto"` falls back to Python for unsupported languages/config without changing user-facing `Codebase` construction.
- `graph_backend="rust", rust_fallback="error"` raises on missing extension or unsupported feature.

Facade parity:

- Existing small Python fixtures: compare `files`, `symbols`, `classes`, `functions`, and `imports` names, paths, ranges, and sort order between Python and Rust backends.
- Existing small TypeScript fixtures: compare `files`, `symbols`, `classes`, `functions`, `imports`, and `exports` names, paths, ranges, and sort order.
- `get_file`, `has_file`, `get_symbol`, `get_class`, and `get_function` return compatible results.

Lazy behavior:

- Rust backend construction does not call eager `SourceFile.__init__`, `Symbol.__init__`, `Import.__init__`, or `Export.__init__`.
- `codebase.files` creates handles only for returned files and does not populate `ctx._graph` with Python file payloads.
- `codebase.symbols` creates top-level symbol handles only, not every parsed AST node.
- `file.symbols`, `file.imports`, and TypeScript `file.exports` only wrap IDs for that file.
- Handle properties `name`, `filepath`, `source`, `start_byte`, and `end_byte` do not materialize Python tree-sitter nodes.

Fallback:

- Accessing an unsupported file-local property materializes only the containing file in non-strict fallback mode.
- Accessing an unsupported graph-wide mutation promotes to Python backend in non-strict fallback mode.
- The same unsupported accesses raise `RustBackendUnsupportedError` in strict mode.
- Old handles become outdated after promotion or `apply_diffs`.

Packaging:

- Wheel build includes both existing Cython extensions and `graph_sitter._rust`.
- Importing `graph_sitter` with `graph_backend="python"` succeeds if `graph_sitter._rust` is absent.
- Importing `graph_sitter._rust` succeeds in CI wheels for supported Python versions and platforms.
