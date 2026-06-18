# Resolution And Dependency Algorithm Inventory

## Scope

This inventory maps the current Python implementation that needs parity in the Rust rewrite. It focuses on:

- Import resolution: `src/graph_sitter/core/import_resolution.py`, `src/graph_sitter/python/import_resolution.py`, `src/graph_sitter/typescript/import_resolution.py`, `src/graph_sitter/typescript/ts_config.py`
- Export resolution: `src/graph_sitter/core/export.py`, `src/graph_sitter/typescript/export.py`, `src/graph_sitter/core/statements/export_statement.py`, `src/graph_sitter/typescript/file.py`
- Name/scope and type-frame resolution: `src/graph_sitter/core/file.py`, `src/graph_sitter/core/function.py`, `src/graph_sitter/core/expressions/name.py`, `src/graph_sitter/core/expressions/chained_attribute.py`, `src/graph_sitter/compiled/resolution.pyx`
- Usage metadata and dependency edges: `src/graph_sitter/core/dataclasses/usage.py`, `src/graph_sitter/core/interfaces/importable.py`, `src/graph_sitter/core/interfaces/usable.py`
- Subclass/interface dependencies: `src/graph_sitter/core/interfaces/inherits.py`, `src/graph_sitter/core/symbol_groups/parents.py`, `src/graph_sitter/core/class_definition.py`, `src/graph_sitter/core/interface.py`
- Incremental recomputation: `src/graph_sitter/codebase/codebase_context.py`, especially `_process_diff_files` and `_compute_dependencies`

## Current Graph Model

The Python backend stores graph nodes as live Python objects in `rustworkx.PyDiGraph`. The resolver/dependency graph uses:

| Concept | Current node/record | Important fields |
| --- | --- | --- |
| File | `SourceFile` | `node_id`, `filepath`, `_nodes`, `code_block`, `valid_symbol_names`, `valid_import_names` |
| Symbol | `Symbol` subclasses | `name`, `full_name`, `symbol_type`, `parent_symbol`, code ranges, nested `code_block` |
| Import | `Import` subclasses | `module`, `symbol_name`, `alias`, `import_type`, `_unique_node`, `to_file_id` |
| Export | `TSExport` | `name`, `exported_name`, `_declared_symbol`, `_exported_symbol`, `_value_node` |
| External module | `ExternalModule` | module/source name, originating import |
| Usage | `Usage` dataclass | `match`, `usage_symbol`, `imported_by`, `usage_type`, `kind` |

Graph edges:

| Edge kind | Direction | Meaning |
| --- | --- | --- |
| `IMPORT_SYMBOL_RESOLUTION` | import -> symbol/file/external | Import path/specifier resolution |
| `EXPORT` | export -> symbol/import/file | Export target resolution |
| `SUBCLASS` | class/interface -> class/interface/external | Resolved inheritance/implements relation |
| `SYMBOL_USAGE` | usage owner -> target | Dependency edge with `Usage` metadata |

`UsageType` is an `IntFlag` with `DIRECT`, `CHAINED`, `INDIRECT`, and `ALIASED`. `UsageKind` records where the reference came from: subclass, typed parameter, type annotation, body, decorator, return type, type definition, exported symbol, wildcard export, generic, imported, wildcard import, or default value.

## Build And Recomputation Pipeline

`CodebaseContext._process_diff_files` is the orchestrator:

1. Clear caches unless this is an incremental add-only update.
2. Start and wait for dependency manager/language engine if configured.
3. Normalize missing `ADD`/`REPARSE` paths into `DELETE`.
4. For deleted files, remove internal edges, unparse nodes, remove graph nodes, and collect predecessor nodes of removed nodes into `to_resolve`.
5. For reparsed files, remove internal edges, unparse children, reparse the same file node from disk, and enqueue the file plus all new nodes.
6. For added files, parse and enqueue the file plus all new nodes.
7. Rebuild directory tree and TypeScript configs.
8. For every import in `to_resolve`, remove old import-resolution edges, add new ones, and append `node.symbol_usages` to `to_resolve`.
9. For every export in `to_resolve`, remove old export edges, compute export edges, and append `node.symbol_usages` to `to_resolve`.
10. For every inherited symbol in `to_resolve`, remove old subclass edges and compute superclass dependencies.
11. Run `_compute_dependencies(to_resolve, incremental)`.

`_compute_dependencies` is a fixed-point queue over Python objects. Each node recomputes outgoing `SYMBOL_USAGE` edges. In incremental mode, `Importable.recompute` removes old usage edges, calls `_compute_dependencies`, and returns `descendant_symbols + file.get_nodes(sort=False)`. In non-incremental mode, each fixed-point round appends every graph node not yet seen. This is correct enough for the object model, but it fans out far beyond the semantic delta.

## Import Resolution Algorithms

### Shared Import Flow

`Import.add_symbol_resolution_edge` calls the language-specific `resolve_import`:

- If it returns `None`, the import is unresolved internally and gets an `ExternalModule` target keyed by module/source.
- If it returns `symbol`, add `IMPORT_SYMBOL_RESOLUTION` import -> symbol unless it is a self-loop.
- If it returns `imports_file=True`, add `IMPORT_SYMBOL_RESOLUTION` import -> source file.
- `imported_symbol` follows a direct import-resolution edge and, for exports, follows `EXPORT` edges until a non-export target.
- `resolved_symbol` follows chains of imports and stops on cycles.
- `names` yields one binding for normal imports, expands wildcard imports through the resolved file's `valid_import_names`, and invalidates importer files when wildcard expansion changes.

### Python

`PyImport.resolve_import` resolves from `module`, `symbol_name`, `alias`, and `ImportType`:

1. Pick `base_path` from the first project or an explicit retry.
2. Convert relative dot imports to absolute dotted paths based on the current file directory.
3. For module and wildcard imports, try `base_path/module/path.py`.
4. For named imports, first try `base_path/module/path/symbol.py` to support importing a submodule as the symbol.
5. Try configured `import_resolution_paths` and optionally `sys.path` before the default graph lookup.
6. Try direct file paths, then package `__init__.py`.
7. For `module.py` or `module/__init__.py`, look up `symbol_name` through `get_node_by_name`.
8. If a symbol is missing but a wildcard import chain can provide it, return the file as `imports_file=True`.
9. If unresolved from repo root, retry with `src`, then `test` if those directories exist.
10. Otherwise return `None` and let the shared layer create/reuse an external module node.

Python `valid_import_names` extends the base file map for `__init__.py`: child files in the package directory are importable by file stem.

### TypeScript And JavaScript

`TSImport` parses static imports, re-export imports, side-effect imports, namespace imports, CommonJS `require`, and dynamic `import()` forms into the same import record shape.

`TSImport.resolve_import`:

1. Strip quotes from the import source.
2. Translate aliases through the nearest `TSConfig` if available.
3. Mark relative imports, prepend the project base path for non-prefixed sources, and normalize relative paths against the importing file directory.
4. If the path has no extension and an index file exists, prefer `index.ts`, `index.js`, `index.tsx`, then `index.jsx`.
5. Try both the import source and its extensionless stem with extensions: empty, `.ts`, `.d.ts`, `.tsx`, `.d.tsx`, `.js`, `.jsx`.
6. If the target file exists and the import is module-like (`MODULE`, `WILDCARD`, `DEFAULT_EXPORT`, or non-type `SIDE_EFFECT`), resolve to the file.
7. For named imports, resolve to `file.get_export(symbol_name)`. If the export is missing, return the file as `imports_file=True` so module re-export search can resolve later.
8. If no file matches, return `None` for external module handling.

`TSImport.resolved_symbol` adds TypeScript-specific hops:

- Default imports can collapse to the single default export's resolved symbol.
- Named imports that initially resolve to a file search module imports in that file with BFS to find re-exported named exports.
- Import chains are followed until a non-import target or a cycle.

`TSConfig` precomputes alias maps from `extends`, `compilerOptions.baseUrl`, `paths`, `rootDirs`, `outDir`, project `references`, and explicit `import_resolution_overrides`. Alias lookup uses longest-prefix matching and has an optimization to skip non-`@`/`~` imports when all aliases use those prefixes.

## Export Resolution Algorithms

Only TypeScript has explicit export nodes.

`ExportStatement` parses:

- Declaration exports: exported function, class, variable, interface, type alias, enum, namespace.
- Value exports: `export default value`, `export = value`, object literals, assignment expressions, detached expression values.
- Source re-exports: `export { x as y } from "./m"`, `export * from "./m"`, `export * as ns from "./m"`.
- Local named exports: `export { local as public }`.

`TSExport.compute_export_dependencies` creates `EXPORT` edges:

- If the export declared a symbol, export -> declared symbol.
- If it names an existing local/imported symbol, export -> resolved local/import node.
- If it exports a value expression that is `Chainable`, export -> each resolved value target.
- If it is a bare wildcard export, export -> current file.
- Wildcard exports invalidate import-name caches in importer files.

`TSFile.valid_import_names` is export-centric:

- A single default export is stored under `default`.
- Each export contributes `export.names`: explicit exported names or expanded wildcard-export names.
- TypeScript imports therefore resolve importable names through file exports, not raw file symbols.

`TSExport.resolved_symbol` follows export/import chains until it reaches a symbol, file, or external module, while tracking cycles. `TSExport._compute_dependencies` separately records usage edges for exported symbols or exported values using `UsageKind.EXPORTED_SYMBOL`.

## Name, Scope, And Resolution Frames

### Lexical Lookup

The core lookup path is recursive and object-centric:

- `Name._resolved_types` calls `resolve_name(self.source, self.start_byte)`.
- `Editable.resolve_name` delegates to the parent scope, falling back to the file.
- `SourceFile.resolve_name` looks in `valid_symbol_names`, which combines top-level symbols keyed by full name and imports keyed by import names/wildcards. If a candidate starts after the usage byte, it scans previous file symbols backward for the closest visible definition.
- `Function.resolve_name` checks function parameters and descendant symbols in reverse source order before delegating to the parent scope.
- `PyFunction.resolve_name` special-cases method receivers: the first parameter and `super()` resolve to the parent class for non-static methods.
- `TSFunction.resolve_name` special-cases `this` to the parent class.
- `ForLoopStatement.resolve_name` can bind loop variables from the iterable's resolved generic frames.
- `Name.resolve_name` optionally expands conditional-block alternatives when `conditional_type_resolution` is enabled.

### Resolution Frames

`Chainable.resolved_type_frames` returns one or more `ResolutionStack` frames with cycle protection. Frames carry:

- `node`: current target or intermediate node
- `parent_frame`: next target in the chain
- `direct`, `aliased`, `chained`: usage classification flags
- `generics`: generic substitutions discovered along the way

`ResolutionStack.get_edges` emits `SYMBOL_USAGE` edges from the destination owner to every graph node in the resolution stack. This preserves current API behavior where a symbol can be used by an import/export intermediary and by the final callsite. The edge's `Usage` stores the exact match node, owner symbol, usage type, usage kind, and optional importer.

### Chained Attributes And Calls

`ChainedAttribute._resolved_types`:

- Resolves full names directly from `file.valid_import_names` for module-style imports.
- Otherwise resolves the object, then asks the top target to `resolve_attribute(attribute)`.
- If the top target has no attributes, it still yields the top target as a chained dependency and may adjust dict generics for common methods.
- `_compute_dependencies` records chained usage edges and also computes dependencies for the object unless it is `self` or `this`.

`FunctionCall._resolved_types` resolves calls through the function name. Constructors resolve to their parent class. Functions with return types resolve to the return type, with generic substitution where possible. Unresolved calls still yield a frame for the call itself so dependency computation can continue. `_compute_dependencies` computes argument dependencies, generic type arguments, and then either adds usages for resolved function definitions or computes the name dependency directly.

## Subclass And Interface Dependencies

Classes and interfaces implement `Inherits`.

- Python classes parse `superclasses` into a `Parents` collection.
- TypeScript classes parse `extends_clause` and `implements_clause` from `class_heritage`.
- TypeScript interfaces parse `extends_type_clause` into `parent_interfaces`.
- `Parents._compute_dependencies` records normal usage dependencies for parent type expressions and generic type arguments.
- `Parents.compute_superclass_dependencies` resolves each parent expression. If exactly one resolved target is on the graph, it adds a `SUBCLASS` edge from the class/interface to that target. Ambiguous or missing parents are logged and do not get `SUBCLASS` edges.
- `Inherits._get_superclasses` and `_get_subclasses` perform BFS over `SUBCLASS` successors/predecessors, matching the current Python MRO-like traversal.

Parity requires both edge families: `SYMBOL_USAGE` for the inheritance expression and `SUBCLASS` for inheritance traversal APIs.

## Where The Current Algorithm Fans Out

The main fan-out points to avoid in Rust are:

1. `to_resolve.extend(node.symbol_usages)` during import and export passes. A changed import/export pulls all current users of that object into the recompute queue, even if only one name or target changed.
2. `Importable.recompute(incremental=True)` returns `descendant_symbols + file.get_nodes(sort=False)`. Any changed node schedules the whole file's graph nodes plus nested descendants.
3. Non-incremental `_compute_dependencies` appends every graph node not yet seen on every fixed-point round.
4. Cache invalidation is coarse: `uncache_all()` and file-level `invalidate()` drop broad Python cached properties instead of specific name/export/import indexes.
5. Wildcard imports and exports invalidate importer files by object traversal, not by changed exported-name sets.
6. TypeScript re-export search uses BFS through module imports at query time, so a missing named export can repeatedly search the same module-import frontier.
7. `valid_symbol_names` and `valid_import_names` are derived from live object lists and can expand wildcard imports into many object wrappers.

The Rust engine should compute semantic deltas first and only enqueue relations whose inputs changed.

## Required Rust Tables And Indexes

### Canonical Records

| Record | Required fields |
| --- | --- |
| `FileRecord` | `FileId`, path ID, language, content hash, parser generation, tsconfig ID, root range |
| `ScopeRecord` | `ScopeId`, file ID, parent scope, owner node, kind, range, hoist behavior |
| `SymbolRecord` | `SymbolId`, file ID, scope ID, name ID, full-name ID, kind, parent symbol, declaration range, body range |
| `ImportRecord` | `ImportId`, file ID, scope ID, module specifier ID, symbol name ID, alias ID, import type, statement range, specifier range |
| `ExportRecord` | `ExportId`, file ID, export name ID, declared symbol/import ID, local exported symbol name ID, value expression ID, export kind, statement range |
| `UsageSiteRecord` | `UsageSiteId`, file ID, scope ID, owner node ID, expression node ID, name/full-name IDs, match range, usage kind |
| `ExternalModuleRecord` | `ExternalId`, module specifier ID, import name ID |
| `GraphEdge` | source ID, target ID, edge kind, optional usage ID |
| `UsageRecord` | usage site, owner node, target node, imported-by import ID, usage type, usage kind, match range |

### Lookup Indexes

| Index | Purpose |
| --- | --- |
| `path_to_file` and `module_key_to_file` | O(1) candidate file lookup for Python/TS import paths and package/index files |
| `file_to_nodes`, `file_to_imports`, `file_to_exports`, `file_to_scopes` | Fast deletion/reparse and debug dumps |
| `scope_parent`, `scope_children`, `binding_by_scope_name` | Lexical name lookup without parent object recursion |
| `binding_visibility_by_name` | Resolve nearest visible binding before a usage byte |
| `file_importable_name` | `valid_import_names` equivalent for each file |
| `wildcard_import_expansion` and `wildcard_export_expansion` | Cache expanded names with source file/export generation |
| `import_resolution` | Import -> target file/symbol/export/external and reverse target -> imports |
| `export_target` | Export -> symbol/import/file/external and reverse target -> exports |
| `usage_by_owner`, `usage_by_target`, `usage_by_match` | Dependency queries, usages API, rename callsites |
| `edge_by_source_kind`, `edge_by_target_kind` | Efficient graph deletes and parity dumps |
| `subclass_succ`, `subclass_pred` | Superclass/subclass APIs |
| `tsconfig_for_file`, `alias_prefix_to_imports` | Narrow TypeScript alias invalidation |
| `unresolved_by_name`, `external_by_key` | Revisit unresolved references only when matching names/modules appear |

## Compact Frontier And Invalidation Rules

### Semantic Deltas

For each changed file, compute deltas before invalidating dependents:

- `PathDelta`: file added/deleted/moved or extension/index/package status changed.
- `ConfigDelta`: nearest tsconfig, alias map, baseUrl, paths, or references changed.
- `ImportDelta`: import specifier/module/type/alias changed, added, or removed.
- `ExportNameDelta`: importable names added/removed/retargeted for a file.
- `BindingDelta`: lexical bindings added/removed/renamed/retargeted by `(scope, name, visibility range)`.
- `UsageSiteDelta`: identifier/chained-attribute/function-call sites added/removed/changed owner or range.
- `InheritanceDelta`: parent type expressions or generic args changed.

### Work Queues

Use separate queues instead of one object queue:

1. `ResolveImports`: import IDs whose module candidate set or specifier fields changed.
2. `ResolveExports`: export IDs whose declared/local/import target changed, plus wildcard re-exporters of changed export names.
3. `ResolveNames`: usage sites whose lexical binding candidates changed by name/scope/range.
4. `BuildUsageEdges`: usage sites whose resolution stack changed.
5. `BuildSubclassEdges`: inheritance expressions whose resolved target changed.
6. `PropagateNameExports`: files whose `file_importable_name` set changed.

### Frontier Rules

- A changed import spec enqueues only that import for path resolution, then only usage sites bound to that import alias/name.
- A changed file path enqueues imports whose precomputed candidate path set includes the old or new path, plus unresolved imports with matching module suffix.
- A tsconfig change enqueues imports in files covered by that config and imports whose specifier matches changed alias prefixes.
- A file's `ExportNameDelta` enqueues imports targeting that file/name, wildcard imports from that file, and wildcard re-exporters whose expansion includes changed names.
- A `BindingDelta(scope, name)` enqueues usage sites with the same name in descendant scopes whose lookup path crosses the changed scope and whose usage byte is after the binding visibility point.
- A local symbol body change with no binding/import/export/name-set delta only enqueues usage sites inside that symbol owner.
- A parent class/interface expression change enqueues only that class/interface for `SUBCLASS` rebuild and its inheritance-expression usage edges.
- A target deletion enqueues reverse dependents from `usage_by_target`, `import_resolution` reverse index, `export_target` reverse index, and `subclass_pred`, but filtered by changed names where possible.

The Rust fixed point should operate on relation generations: if a queue item recomputes to the same normalized output tuple, do not enqueue its dependents.

## Rust Port Plan

1. Extract compact import/export/scope/usage IR alongside the Python backend and produce debug snapshots without changing behavior.
2. Implement Python import path resolution in Rust with a candidate-path trace for parity debugging.
3. Implement TypeScript import path resolution, including tsconfig alias maps, index files, extension permutations, dynamic imports, and external module records.
4. Implement TypeScript export target resolution and file importable-name tables, including wildcard re-export expansion.
5. Implement lexical scope tables and name lookup for file, function, class, parameter, loop, `self`/`super()`, `this`, and conditional-resolution cases.
6. Implement resolution-stack edge emission so normalized `SYMBOL_USAGE` edges include intermediate import/export nodes and the current `UsageType`/`UsageKind`.
7. Implement `SUBCLASS` edge construction from parent/interface expressions and BFS query indexes for superclass/subclass APIs.
8. Add incremental relation generations and the compact work queues above.
9. Expose graph debug dumps through PyO3: nodes, imports, exports, usage sites, resolution stacks, and normalized edges.
10. Keep Python object APIs as wrappers over IDs only after graph edge parity is proven.

## Edge Parity Tests

Add Rust-vs-Python golden snapshots using normalized tuples:

```text
(source_kind, source_file, source_range, source_name,
 edge_kind,
 target_kind, target_file, target_range, target_name,
 usage_type, usage_kind, match_file, match_range, match_text, imported_by_key)
```

Required parity categories:

| Category | Fixtures to cover |
| --- | --- |
| Python imports | module, named, aliased, wildcard, relative dots, package `__init__.py`, custom resolve paths, `src`/`test` fallback, external modules |
| TypeScript imports | default, named, alias, namespace, side-effect, `require`, dynamic import, directory index, extension fallback, tsconfig paths/baseUrl/references, external modules |
| TypeScript exports | declaration exports, default exports, `export =`, object value exports, named local exports, named re-exports, wildcard re-exports, aliased wildcard exports, type-only exports |
| Usage types | direct same-file references, imported references, indirect re-export chains, aliased imports/exports, chained module/class/namespace references |
| Usage kinds | body, decorator, subclass, generic, type annotation, typed parameter, return type, type definition, exported symbol, imported, default value |
| Name/scope | nested functions, parameter shadowing, definitions after usage, class methods, Python `self` and `super()`, TypeScript `this`, loop variables, conditional blocks |
| Subclass/interface | Python class bases, TS `extends`, TS `implements`, interface `extends`, generic parent types, external/ambiguous parents |
| Incremental | add file, delete file, reparse no-op, rename import target, change exported name, wildcard export name delta, tsconfig alias delta |

Existing tests already cover many behavior assertions under `tests/unit/sdk/python/import_resolution`, `tests/unit/sdk/typescript/import_resolution`, `tests/unit/sdk/typescript/export`, `tests/unit/sdk/python/class_definition/test_class_dependencies.py`, `tests/unit/sdk/typescript/class_definition/test_class_dependencies.py`, `tests/unit/sdk/typescript/interface/test_interface_dependencies.py`, `tests/unit/sdk/python/file/test_file_reparse.py`, and `tests/unit/sdk/python/codebase/test_codebase_reset.py`. The Rust parity layer should reuse those fixture shapes and compare graph-edge snapshots directly.
