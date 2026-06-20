# Rust Data Model Proposal

## Scope

This document proposes the compact Rust-side storage model for replacing the current Python object graph while preserving the Python API as a lazy compatibility layer. It is based on inspection of:

- `CodebaseContext`: `PyDiGraph[Importable, Edge]`, `filepath_idx`, external module index, graph build/reparse flow.
- `SourceFile`: eager file node plus per-file `_nodes`, `_range_index`, import/symbol/export query helpers.
- `Editable` and `Importable`: persistent `ts_node`, `ctx`, `parent`, `file_node_id`, `node_id`, `range`, and edit helpers.
- `Usage`, `RangeIndex`, `ResolutionStack`, `Import`, `Export`, and edge construction paths.

The important constraint is to avoid translating every Python semantic node into a PyO3-owned object. Rust should own compact records and return IDs; Python objects should be handles created only when user code asks for them.

## Current Shape To Preserve

The current graph endpoints are only semantic `Importable` objects:

- files
- symbols
- imports
- exports
- external modules

General expressions/statements are usually not graph endpoints, but many are still materialized as Python `Editable` objects for parent traversal, source/range access, edits, and dependency extraction. `RangeIndex` can additionally keep all parsed editables when `full_range_index` is enabled.

Current graph edge kinds are:

- `IMPORT_SYMBOL_RESOLUTION`: import to resolved symbol/import/export/file/external module.
- `EXPORT`: export to declared/exported symbol, import, file, or other export target.
- `SUBCLASS`: class/interface symbol to resolved superclass/interface.
- `SYMBOL_USAGE`: symbol/import/export/file owner to used symbol/import/export/file/external module, with `Usage` metadata.

The Rust model should preserve those graph semantics, not the Python object ownership model.

## Core Storage

```rust
pub struct EngineStore {
    pub schema_version: u16,
    pub engine_epoch: u32,

    pub strings: StringInterner,
    pub paths: PathInterner,
    pub modules: StringInterner,
    pub ts_kinds: StringInterner,

    pub files: Arena<FileRecord>,
    pub syntax: Arena<SyntaxRecord>,
    pub symbols: Arena<SymbolRecord>,
    pub imports: Arena<ImportRecord>,
    pub exports: Arena<ExportRecord>,
    pub externals: Arena<ExternalRecord>,
    pub scopes: Arena<ScopeRecord>,
    pub usages: Arena<UsageRecord>,

    pub nodes: NodeTable,
    pub graph: GraphStore,
    pub indexes: IndexStore,
}
```

`EngineStore` is the sole owner of canonical codebase state. Records store IDs and interned keys, never Python object references, Rust references into other arenas, or persistent `tree_sitter::Node` wrappers.

`Arena<T>` should be a dense `Vec<Slot<T>>` with tombstones and a per-slot generation, or an equivalent slotmap. Dense vectors keep scans and dumps cache-friendly; generations let lazy Python handles fail clearly after invalidation instead of reading a reused slot.

## IDs

Use typed IDs internally:

```rust
pub struct FileId(u32);
pub struct SyntaxId(u32);
pub struct SymbolId(u32);
pub struct ImportId(u32);
pub struct ExportId(u32);
pub struct ExternalId(u32);
pub struct ScopeId(u32);
pub struct UsageId(u32);
pub struct EdgeId(u32);
pub struct StringId(u32);
pub struct PathId(u32);
pub struct TsKindId(u16);
pub struct LineIndexId(u32);

pub enum NodeRef {
    File(FileId),
    Symbol(SymbolId),
    Import(ImportId),
    Export(ExportId),
    External(ExternalId),
}

pub struct HandleKey {
    pub node: NodeRef,
    pub generation: u32,
}
```

The Python-facing `node_id` compatibility value should be an encoded `u64` or a `NodeId(u32)` lookup in `NodeTable`. The preferred shape is:

```rust
pub struct NodeId(u32);

pub struct NodeSlot {
    pub node: NodeRef,
    pub generation: u32,
    pub alive: bool,
}
```

Compatibility handles store both `NodeId` and generation. `NodeId` values are not reused during a live engine epoch. On full rebuild, `engine_epoch` changes; on file reparse/delete, affected node generations change. A handle is valid only if `(engine_epoch, node_id, generation)` still matches.

Future incremental stable IDs can be layered on top with `StableKey` fingerprints:

```rust
pub enum StableKey {
    File { normalized_path: PathId },
    Symbol { file: FileId, full_name: StringId, kind: SymbolKind, declaration_range_hash: u64 },
    Import { file: FileId, statement_range_hash: u64, local_index: u32 },
    Export { file: FileId, exported_name: Option<StringId>, statement_range_hash: u64, local_index: u32 },
}
```

Do not make stable keys the primary storage key in the first slice. Keep arena IDs compact, and use stable keys only to remap handles across reparses later.

## Interning

Intern these values:

- normalized relative paths
- absolute paths only when needed for IO/debug
- module specifiers and import sources
- symbol names and full names
- aliases, exported names, namespaces
- tree-sitter kind strings
- language-specific small strings that appear many times

Content is not string-interned. Each parsed file owns an `Arc<[u8]>` or equivalent immutable byte buffer for the current revision. Source slices are `(FileId, ByteRange)` views into that buffer.

Path normalization invariants:

- `FileRecord.path` is the repo-relative path used by public APIs.
- A separate absolute path cache can exist for IO, but graph identity uses the relative path.
- Case-insensitive lookups are an auxiliary index and must not change canonical path IDs.

## Ranges

All canonical ranges are byte ranges in UTF-8 file content:

```rust
pub struct ByteRange {
    pub start: u32,
    pub end: u32,
}

pub struct Point {
    pub row: u32,
    pub column: u32,
}

pub struct SourceRange {
    pub bytes: ByteRange,
    pub start_point: Point,
    pub end_point: Point,
}
```

`Point.column` must match tree-sitter semantics for the grammar bindings, which are byte columns, not Unicode scalar columns. Keep a per-file line index so byte to point and point to byte conversions are cheap and deterministic.

Range invariants:

- `start <= end <= file.content.len()`.
- A record's `file_id` owns every range it stores.
- Ranges are half-open byte ranges.
- Public line ranges keep current behavior: `start_point.row..=end_point.row`.
- Edit transactions operate on byte ranges, matching today's `Editable.edit`, `insert_at`, and `remove_byte_range`.

## Syntax Anchors

Rust should not store one Python `Editable` per syntax node. Store compact syntax anchors instead:

```rust
pub struct SyntaxRecord {
    pub file: FileId,
    pub parent: Option<SyntaxId>,
    pub kind: TsKindId,
    pub range: SourceRange,
    pub flags: SyntaxFlags,
    pub first_child: Option<SyntaxId>,
    pub next_sibling: Option<SyntaxId>,
}

bitflags! {
    pub struct SyntaxFlags: u16 {
        const NAMED = 1 << 0;
        const ERROR = 1 << 1;
        const MISSING = 1 << 2;
        const CANONICAL = 1 << 3;
        const SEMANTIC_ANCHOR = 1 << 4;
    }
}
```

Default mode should store only anchors required by semantic records and usage matches:

- file root
- symbol declaration/name/body/extended ranges
- import statement/specifier/module/name/alias ranges
- export statement/name/value ranges
- usage match ranges
- edit anchors needed by P0 methods

When `full_range_index` or LSP mode is enabled, store all named syntax nodes and the parent/child links required for `ast()`, cursor lookup, and range lookup. This preserves compatibility without paying that cost for every normal codebase load.

## File Records

```rust
pub struct FileRecord {
    pub path: PathId,
    pub language: LanguageKind,
    pub content_hash: u64,
    pub content_len: u32,
    pub content: Arc<[u8]>,
    pub line_index: LineIndexId,
    pub root: SyntaxId,
    pub root_range: SourceRange,
    pub parse_status: ParseStatus,
    pub file_epoch: u32,

    pub symbols: IdSpan<SymbolId>,
    pub imports: IdSpan<ImportId>,
    pub exports: IdSpan<ExportId>,
    pub syntax_nodes: IdSpan<SyntaxId>,
}
```

Per-file ID spans point into sorted side arrays in `IndexStore`, not embedded `Vec`s in every file. This keeps `FileRecord` small and allows bulk rebuild of file indexes after parse.

File invariants:

- `path` is unique among live files.
- Per-file symbols/imports/exports are sorted by `(start_byte, end_byte, local_order)`.
- Deleting a file tombstones all semantic records owned by the file and removes graph edges touching those records.
- Reparsing a file increments `file_epoch`; lazy handles with old epoch become stale.

## Symbol Records

```rust
pub struct SymbolRecord {
    pub node_id: NodeId,
    pub file: FileId,
    pub kind: SymbolKind,
    pub language_kind: LanguageSymbolKind,
    pub name: StringId,
    pub full_name: StringId,
    pub parent_symbol: Option<SymbolId>,
    pub parent_scope: ScopeId,
    pub declaration: SyntaxId,
    pub name_syntax: Option<SyntaxId>,
    pub body: Option<SyntaxId>,
    pub extended_range: SourceRange,
    pub declaration_range: SourceRange,
    pub name_range: Option<SourceRange>,
    pub flags: SymbolFlags,
    pub local_order: u32,
}
```

Symbol invariants:

- `node_id` maps back to `NodeRef::Symbol(self_id)`.
- `parent_symbol` is in the same file and must not form a cycle.
- `full_name` is the language-specific qualified name used by current public APIs.
- `is_top_level` is a flag derived during extraction, not recomputed by climbing Python parents.
- `descendant_symbols` is answered by a symbol tree index.

## Import Records

```rust
pub struct ImportRecord {
    pub node_id: NodeId,
    pub file: FileId,
    pub import_type: ImportType,
    pub statement: SyntaxId,
    pub specifier: SyntaxId,
    pub module: Option<StringId>,
    pub symbol_name: Option<StringId>,
    pub alias: Option<StringId>,
    pub namespace: Option<StringId>,
    pub is_type_only: bool,
    pub is_dynamic: bool,
    pub unique_range: SourceRange,
    pub statement_range: SourceRange,
    pub specifier_range: SourceRange,
    pub module_range: Option<SourceRange>,
    pub symbol_range: Option<SourceRange>,
    pub alias_range: Option<SourceRange>,
    pub resolved: Option<NodeRef>,
    pub local_order: u32,
}
```

Import invariants:

- `node_id` maps back to `NodeRef::Import(self_id)`.
- `unique_range` preserves current equality/hash behavior for multi-import statements.
- `resolved` is mirrored by one `IMPORT_SYMBOL_RESOLUTION` edge when resolution succeeds or an external module record is created.
- External module records are keyed by `(import.source, unique_import_name)`, matching the current `module::import_name` index.
- Wildcard imports expose `names` through a wildcard expansion index, not by materializing `WildcardImport` Python objects up front.

## Export Records

```rust
pub struct ExportRecord {
    pub node_id: NodeId,
    pub file: FileId,
    pub export_kind: ExportKind,
    pub name: Option<StringId>,
    pub exported_name: Option<StringId>,
    pub declared_symbol: Option<SymbolId>,
    pub statement: SyntaxId,
    pub name_syntax: Option<SyntaxId>,
    pub value_syntax: Option<SyntaxId>,
    pub statement_range: SourceRange,
    pub name_range: Option<SourceRange>,
    pub target: Option<NodeRef>,
    pub flags: ExportFlags,
    pub local_order: u32,
}
```

Export invariants:

- `node_id` maps back to `NodeRef::Export(self_id)`.
- `target` is mirrored by an `EXPORT` edge when known.
- Wildcard exports target the source file node when current behavior does.
- `resolved_symbol` follows export/import edges with a visited set to preserve circular-chain behavior.

## External Records

```rust
pub struct ExternalRecord {
    pub node_id: NodeId,
    pub module: StringId,
    pub import_name: StringId,
    pub display_name: StringId,
    pub first_import: ImportId,
}
```

External modules do not own file ranges. Any source/range shown for compatibility should come from `first_import` or the usage/import that reached the external.

## Usage Records

```rust
pub struct UsageRecord {
    pub source: NodeRef,
    pub target: NodeRef,
    pub usage_symbol: NodeRef,
    pub match_syntax: SyntaxId,
    pub imported_by: Option<ImportId>,
    pub usage_type: UsageType,
    pub usage_kind: UsageKind,
    pub match_range: SourceRange,
}
```

`source` is the graph edge source, matching the current `dest.node_id` emitted by `ResolutionStack.get_edges`. `usage_symbol` mirrors the current `Usage.usage_symbol` payload, which is usually `dest.parent_symbol` and may differ from `source` for nested symbols. `target` is the used node. `match_syntax` is the `Name`, `ChainedAttribute`, or `FunctionCall` anchor used for renames and source display.

Usage invariants:

- Every `SYMBOL_USAGE` edge has exactly one `UsageId`.
- `UsageRecord.source == edge.source`.
- `UsageRecord.target == edge.target`.
- `UsageRecord.usage_symbol` is a live graph node.
- `match_syntax.file == source.file` when the source has a file.
- `usage_type` preserves `DIRECT`, `CHAINED`, `INDIRECT`, and `ALIASED` resolution stack semantics.
- `usage_kind` preserves body/type/decorator/import/export/subclass context.

## Graph Storage

```rust
pub struct EdgeRecord {
    pub source: NodeRef,
    pub target: NodeRef,
    pub kind: EdgeKind,
    pub usage: Option<UsageId>,
}

pub struct GraphStore {
    pub edges: Vec<EdgeRecord>,
    pub out_offsets: Vec<u32>,
    pub out_edges: Vec<EdgeId>,
    pub in_offsets: Vec<u32>,
    pub in_edges: Vec<EdgeId>,
}
```

During parsing/resolution, use mutable per-node edge vectors plus a dedupe set. After a phase completes, freeze into CSR-style adjacency arrays. Incremental reparses can rebuild adjacency for affected nodes first; whole-graph CSR rebuild is acceptable for the first vertical slice if it is simpler.

Edge invariants:

- Edge endpoints are live `NodeRef`s.
- Multi-edges are allowed only when their full edge key differs.
- Full edge key is `(source, target, kind, usage_key)`.
- `IMPORT_SYMBOL_RESOLUTION` source is always `Import`.
- `EXPORT` source is always `Export`.
- `SUBCLASS` source is always `Symbol`.
- `SYMBOL_USAGE` has `usage.is_some()`.
- Non-`SYMBOL_USAGE` edges have `usage.is_none()`.

## Indexes

```rust
pub struct IndexStore {
    pub path_to_file: HashMap<PathId, FileId>,
    pub casefold_path_to_file: HashMap<StringId, FileId>,
    pub external_by_key: HashMap<(StringId, StringId), ExternalId>,

    pub file_symbols: Vec<SymbolId>,
    pub file_imports: Vec<ImportId>,
    pub file_exports: Vec<ExportId>,
    pub file_syntax: Vec<SyntaxId>,

    pub symbol_children: Vec<SymbolId>,
    pub scope_bindings: ScopeBindingIndex,
    pub import_names_by_file: NameBindingIndex,
    pub exported_names_by_file: NameBindingIndex,

    pub range_index_by_file: HashMap<FileId, RangeIndex>,
}
```

`RangeIndex` should be compact and optional:

```rust
pub struct RangeIndex {
    pub by_start: Vec<SyntaxId>,
    pub exact: HashMap<(ByteRange, TsKindId), SyntaxId>,
    pub all_for_range: HashMap<ByteRange, IdSpan<SyntaxId>>,
}
```

Query patterns:

- `Codebase.files`: scan live `FileRecord`s sorted by path, return lazy file handles.
- `Codebase.symbols/classes/functions`: scan `symbols`, filter flags/kind/top-level, return handles sorted by file and range.
- `Codebase.imports/exports`: scan arenas or per-file spans.
- `SourceFile.imports/symbols/exports`: use file spans in `IndexStore`; no graph scan required.
- `Import.imported_symbol`: follow the one import resolution edge, then optionally follow export edges.
- `Export.exported_symbol`: follow the one export edge.
- `Symbol.usages`: inspect incoming edges for the target node, filter `SYMBOL_USAGE`, load usage records, sort by match start byte descending.
- `Importable.dependencies`: inspect outgoing `SYMBOL_USAGE` edges from descendant symbol IDs, filter usage type, dedupe, and sort by file/range.
- `find_by_byte_range`: use `RangeIndex.exact` or `all_for_range`.
- Cursor lookup: binary search `RangeIndex.by_start`, then choose the smallest containing range.

## Lazy Python Compatibility

Python classes remain compatibility handles:

```text
PySourceFile  -> EngineHandle<FileId>
PySymbol      -> EngineHandle<SymbolId>
PyImport      -> EngineHandle<ImportId>
PyExport      -> EngineHandle<ExportId>
PyExternal    -> EngineHandle<ExternalId>
PyEditable    -> EngineSyntaxHandle<SyntaxId>
PyUsage       -> EngineHandle<UsageId>
```

Each handle stores:

- `Arc<PyEngine>` or equivalent engine owner
- typed ID or `NodeId`
- slot generation
- file epoch if the handle depends on file ranges/content

Handle methods delegate to Rust for source, ranges, relationships, and graph queries. Python lists are built from returned IDs, not from prebuilt objects.

Compatibility notes:

- A weak handle cache can preserve object identity for repeated access without materializing the full graph. The cache is optional and must not be part of canonical state.
- `source`, `start_byte`, `end_byte`, `range`, `span`, and `github_url` are computed from records and file content.
- `file`, `parent_symbol`, `parent`, and `descendant_symbols` are ID lookups.
- Unsupported deep AST methods can reparse one file and build transient Python editables for that call. Those transient objects must not be inserted into canonical graph storage.
- Existing writer methods can initially emit byte-range edit intents using stored ranges, then let the Python transaction manager apply them.
- Stale handles should raise a clear invalidation error or fall back to resolving by `StableKey` once stable remap exists.

## Debug Dumps

Add Rust debug APIs early:

```text
debug_dump_ir(format="jsonl", include_strings=true, include_snippets=false)
debug_dump_graph(format="jsonl")
debug_dump_ranges(file_id)
debug_check_invariants()
```

Dump format requirements:

- Include `schema_version`, engine version, repo root hash/path, and language.
- Sort files by path, records by `(file, start_byte, local_order)`, and edges by `(source, kind, target, usage)`.
- Resolve interned strings in human-readable dumps.
- Include raw content hashes and byte ranges by default, not full file content.
- Include optional snippets only when requested.
- Emit enough usage data to compare with the Python backend: edge kind, source node, target node, usage symbol, usage type, usage kind, match range, imported_by.

Invariant checker should validate:

- live IDs and node table round trips
- path uniqueness
- range bounds
- edge endpoint kinds
- usage/edge consistency
- per-file sorted spans
- scope parent cycles
- duplicate edge keys
- external module key uniqueness

## Memory Rationale

The current model pays for:

- Python object headers and dicts for semantic nodes and many expressions.
- Persistent tree-sitter node wrappers on `Editable`.
- Backrefs from every object to context, parent, and file.
- The same Python objects stored as rustworkx graph payloads.
- Per-file `_nodes` and optional range indexes containing Python object references.
- `Usage` objects that hold Python object references to match nodes, owner symbols, and imports.

The proposed model replaces that with:

- `u32` IDs and small enums instead of object pointers.
- interned strings instead of repeated Python strings.
- contiguous arenas for cache-friendly scans.
- edge payloads as `EdgeRecord` plus optional `UsageId`.
- syntax anchors as byte ranges rather than Python wrappers.
- optional full syntax/range tables only for debug/LSP modes.

Expected record sizes should be in the tens of bytes for edges/usages and under roughly 100 bytes for most symbols/imports, before interned strings and content. The exact target should be validated by the benchmark agent, but the design removes the multiplicative Python object and graph payload overhead.

## Migration Risks

- Python identity and hashing: current equality relies on filepath, range, kind ID, and import unique ranges. Handles must reproduce that behavior even though canonical state is ID based.
- Sorting parity: public APIs rely on file/range/node ID order. Rust queries need explicit stable sort keys.
- Tree-sitter node access: any API exposing or depending on `ts_node` needs either a Rust-backed compatibility surface or a transient per-file reparse fallback.
- Range columns: tree-sitter points use byte columns. Accidentally switching to Unicode columns will break LSP and edit behavior for non-ASCII files.
- Wildcard imports and exports: current code lazily expands and invalidates wildcard-derived names. Rust needs explicit invalidation for files importing from wildcard providers.
- Conditional scope resolution: current `Name.resolve_name` has special conditional-block behavior. Scope tables need tests before Rust becomes authoritative.
- External modules: current identity is tied to import source plus unique node source. The Rust key must match enough behavior to avoid duplicate external nodes.
- Edits and stale handles: any committed edit invalidates ranges for at least one file. Handles must check file epoch before applying edits.
- Full range index memory: enabling all syntax anchors can be expensive. It must remain opt-in and visible in debug stats.
- Fallback materialization: unsupported APIs may temporarily materialize Python objects. This must be per-call/per-file and never recreate the full Python object graph behind PyO3.

## First Slice Recommendation

Implement the Rust data model in this order:

1. Interners, typed IDs, arenas, node table, and file records.
1. Symbol/import/export/external records for Python and TypeScript top-level extraction.
1. Graph edge table with import/export/subclass/symbol usage edge kinds and debug dumps.
1. Per-file query indexes for files, symbols, imports, and exports.
1. Lazy Python handles returning source/ranges and ID-backed relationships.
1. Optional full range index for debug/LSP parity.

This gives the resolver and PyO3 agents a stable contract while keeping the first engine slice focused on compact canonical state rather than Python object emulation.
