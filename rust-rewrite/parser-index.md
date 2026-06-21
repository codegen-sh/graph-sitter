# Rust Parser And Compact Index Plan

## Purpose

Phase 2 should replace the current eager Python AST/object construction with a Rust parser/indexer that emits a compact, snapshot-friendly IR. The IR should preserve enough structure for `files`, `symbols`, `classes`, `functions`, `imports`, and TypeScript `exports` queries, while leaving dependency resolution, expression modeling, edits, and Python object compatibility to later phases.

Current behavior to match where relevant:

- Parser setup maps `.py` to tree-sitter Python and `.js`, `.jsx`, `.ts`, `.tsx` to the TSX grammar (`src/graph_sitter/tree_sitter_parser.py`).
- Language semantic maps live in `PyNodeClasses` and `TSNodeClasses` (`src/graph_sitter/codebase/node_classes/*_node_classes.py`).
- Statement classification is currently custom code in `Parser.parse_py_statements` and `Parser.parse_ts_statements` (`src/graph_sitter/core/parser.py`).
- `SourceFile.parse` eagerly creates a `CodeBlock`, recursively parses statements, populates `file._nodes`, and stores Python payload objects in `rustworkx.PyDiGraph` (`src/graph_sitter/core/file.py`).
- Import/export resolution edges are separate graph phases after parse (`src/graph_sitter/codebase/codebase_context.py`), so the Rust parser slice should only extract unresolved import/export facts.

## Compact IR

Use append-only arenas plus interners. IDs are opaque integers scoped to the engine.

### Shared Primitives

- `FileId`, `SymbolId`, `ImportId`, `ExportId`, `ScopeId`, `StatementId`, `StringId`, `PathId`.
- `Range`: `start_byte`, `end_byte`, `start_point { row, column }`, `end_point { row, column }`.
- `NodeRef`: `file_id`, tree-sitter kind enum/string ID, `range`. Store this only for retained declarations/statements, not every tree-sitter node.
- `Language`: `Python`, `TypeScript`, `TSX`, `JavaScript`, `JSX`. Parser grammar may still be TSX for all JS/TS files to match the Python backend, while the file language should keep the extension-derived source kind.

### Records

`FileRecord`

- `file_id`
- `path_id`, `name_id`, extension-derived `language`
- `content_hash`
- `root_range`
- `parse_status`: `ok`, `tree_sitter_error`, `skipped_binary`, `skipped_minified`
- ordered lists: `top_level_symbols`, `imports`, `exports`, `scopes`

`SymbolRecord`

- `symbol_id`
- `file_id`
- `name_id`
- `full_name_id`
- `kind`: `Function`, `Class`, `GlobalVar`, `Interface`, `TypeAlias`, `Enum`, `Namespace`
- `parent_symbol_id: Option<SymbolId>`; the first parser/index slice should normally be `None` because only top-level symbols are emitted
- `scope_id`
- `range`: extended source range when the current Python API would include decorators/export keywords
- `declaration_range`: actual declaration node range
- `name_range`
- `body_range: Option<Range>`
- flags: `decorated`, `async`, `default_exported`, `named_exported`, `type_only`

`ImportRecord`

- `import_id`
- `file_id`
- `scope_id`
- `statement_id`
- `kind`: reuse current `ImportType` shape: `DefaultExport`, `NamedExport`, `Wildcard`, `Module`, `SideEffect`, `Unknown`
- `module_id: Option<StringId>`: raw module/source text, including Python leading dots or TS quotes stripped in a separate normalized field
- `imported_name_id: Option<StringId>`
- `local_name_id: Option<StringId>`
- `namespace_id: Option<StringId>`
- `is_type_only`
- `is_future_import`
- `is_dynamic`
- `from_export`
- ranges: `statement_range`, `import_range`, `module_range`, `name_range`, `alias_range`

`ExportRecord` (TypeScript/JS only in the first parser/index slice)

- `export_id`
- `file_id`
- `scope_id`
- `statement_id`
- `kind`: `Named`, `Default`, `Wildcard`, `Namespace`, `ExportEquals`, `Unknown`
- `exported_name_id: Option<StringId>`
- `local_name_id: Option<StringId>`
- `source_module_id: Option<StringId>` for re-exports
- `declared_symbol_id: Option<SymbolId>` when the export declares a top-level symbol in the same statement
- `import_id: Option<ImportId>` when the export is a direct re-export modeled through an import fact
- `is_type_only`
- ranges: `statement_range`, `export_range`, `name_range`, `source_range`

`ScopeRecord`

- `scope_id`
- `file_id`
- `parent_scope_id: Option<ScopeId>`
- `owner`: `File(FileId)` or `Symbol(SymbolId)`
- `kind`: `File`, `ClassBody`, `FunctionBody`, `ModuleBlock`
- `range`
- ordered child IDs for top-level symbols/imports/exports owned by this scope

First-slice scopes are lookup boundaries and ownership containers, not full lexical environments.

## Python Extraction Rules

Current implemented Rust status:

- Files, top-level classes/functions, top-level simple global assignments, Python imports, and compact internal import-resolution records are implemented for Python.
- Global extraction currently covers simple identifier targets in top-level `assignment` and `annotated_assignment` nodes, including identifiers nested in tuple/list/pattern lists. Attribute and subscript assignment targets remain intentionally skipped.

### Files

- Parse only `.py`.
- Emit one `FileRecord` per readable, non-skipped file.
- The file scope owns top-level declarations and top-level imports. Nested import statements can be emitted with the nearest top-level symbol scope when found cheaply by range containment.

### Top-Level Symbols

Walk direct named children of the root `module`.

- `decorated_definition`
  - Read child field `definition`.
  - If definition is `function_definition`, emit `Function`.
  - If definition is `class_definition`, emit `Class`.
  - `range` is the `decorated_definition`; `declaration_range` is the nested definition.
  - `name_range` is the nested definition's `name` field.
  - Set `decorated = true`.
- `function_definition`
  - Emit `Function`.
  - `name_range` is field `name`.
  - `body_range` is field `body`.
- `class_definition`
  - Emit `Class`.
  - `name_range` is field `name`.
  - `body_range` is field `body`.
- `expression_statement` containing top-level `assignment` or `augmented_assignment`
  - Emit `GlobalVar` records for simple identifier names on the left side.
  - For `pattern_list`, emit one `GlobalVar` per identifier in source order.
  - For attribute/subscript left sides, store no phase-1 symbol; those are not importable globals in the same way and require expression modeling.
  - Preserve the assignment statement range and the specific name range.

Do not emit nested functions/classes/methods as `SymbolRecord` in the first vertical slice. Current Python can materialize them through recursive `CodeBlock` parsing, but the phase-1 query target is top-level symbols.

### Imports

Emit one `ImportRecord` per imported binding. Store raw syntax facts only; do not resolve to files or symbols.

- `import_statement`
  - For each `dotted_name`, emit `Module` with `module = name = alias = dotted_name`.
  - For each `aliased_import`, emit `Module` with `module/name` from field `name` and `local_name` from field `alias`.
- `import_from_statement`
  - `module` is field `module_name`; keep leading dots as raw text and also store `relative_level` if practical.
  - For each `dotted_name`, emit `NamedExport` with `imported_name = local_name = dotted_name`.
  - For each `aliased_import`, emit `NamedExport` with `imported_name` from field `name` and `local_name` from field `alias`.
  - For `wildcard_import`, emit `Wildcard`; keep the current Python-backend-compatible local name empty or `*` in a dedicated wildcard field, not as a normal binding.
- `future_import_statement`
  - Emit imports with `kind = SideEffect` and `is_future_import = true`, matching current backend behavior.

### Python Exports

Do not emit `ExportRecord` for Python in the first parser/index slice. Python importability is represented by top-level symbols, module imports, wildcard chains, and `__init__.py` rules in the resolver phase.

## TypeScript, TSX, JavaScript Extraction Rules

### Files

- Include `.ts`, `.tsx`, `.js`, `.jsx`.
- For parity with the existing backend, parse all four extensions with the TSX grammar initially. Keep `FileRecord.language` extension-specific so a later parser split does not change public file identity.

### Top-Level Symbols

Walk direct named children of `program`, plus declarations wrapped by top-level `export_statement`.

Emit direct top-level declarations:

- `function_declaration`, `generator_function_declaration` -> `Function`
- `class_declaration`, `abstract_class_declaration` -> `Class`
- `interface_declaration` -> `Interface`
- `type_alias_declaration` -> `TypeAlias`
- `enum_declaration` -> `Enum`
- `internal_module` -> `Namespace`
- `lexical_declaration` or `variable_declaration`
  - If a `variable_declarator` value contains a top-level `arrow_function`, `function_expression`, or `generator_function` at depth \<= 2, emit a `Function` named from the declarator's `name` field.
  - Otherwise emit `GlobalVar` records for simple identifier declarator names.
  - For object/array patterns, emit one `GlobalVar` per simple bound identifier in source order. Defer type-aware destructuring semantics.

For `export_statement` with field `declaration`, emit the same symbol kinds from the declaration and attach `named_exported` or `default_exported` flags through the paired `ExportRecord`.

Do not emit class methods, private fields, JSX elements, object-literal properties, call expressions, promise chains, or nested declarations in the first parser/index slice.

### Static Imports

For `import_statement`, emit one `ImportRecord` per current backend import object:

- No `import_clause`: `import "./setup";`
  - Emit `SideEffect`, `module = source`, no local binding.
- Identifier child of `import_clause`: `import Foo from "./m";`
  - Emit `DefaultExport`, `imported_name = local_name = Foo`.
- `named_imports`: `import { a, b as c } from "./m";`
  - Emit one `NamedExport` per `import_specifier`.
  - `imported_name` is field `name`; `local_name` is field `alias` or `name`.
  - Skip `comment` children.
- `namespace_import`: `import * as ns from "./m";`
  - Emit `Wildcard`, `namespace/local_name = ns`.
- Type imports: `import type { T } from "./m";`, `import { type T } from "./m";`
  - Set `is_type_only` on the statement-wide or specifier-specific import. If specifier-level detection is initially awkward in tree-sitter, snapshot it as a known gap rather than resolving incorrectly.

### Dynamic Imports And Require

The first vertical slice should include a small, syntax-only subset because existing file import tests expect `require` and dynamic `import()` to surface as imports:

- Side-effect calls: `require("./m")`, `import("./m")`, `await import("./m")` in expression statements -> `SideEffect`, `is_dynamic = true`.
- Named module binding: `const pkg = require("./m")` or `const pkg = await import("./m")` -> `Module`, `local_name = pkg`, `is_dynamic = true`.
- Destructured binding: `const { a, b: c } = require("./m")` -> one `NamedExport` per simple property binding.
- Member access type/value import: `import("./m").SomeType` or `(await import("./m")).default` -> `NamedExport` or `DefaultExport` when the property is a simple identifier.

Defer dynamic imports with computed module paths, conditional module expressions, nested object patterns, and non-literal source arguments.

### Exports

Emit unresolved `ExportRecord` facts and any directly declared symbols.

- Declaration exports:
  - `export function f() {}`, `export class C {}`, `export interface I {}`, `export type T = ...`, `export enum E {}`, `export namespace N {}`, `export const x = ...`
  - Emit the declared `SymbolRecord`.
  - Emit `ExportRecord(kind = Named, exported_name = symbol name, declared_symbol_id = symbol_id)`.
- Default declaration/value exports:
  - `export default function f() {}`, `export default class C {}`, `export default foo`, `export = foo`
  - Emit `ExportRecord(kind = Default)` or `ExportEquals`.
  - If the statement declares a named top-level function/class/assignment, link `declared_symbol_id`.
  - If anonymous/default value has no durable name, do not invent a `SymbolRecord`; keep only the export fact and value range.
- Named export clauses:
  - `export { a, b as c };`
  - Emit one `ExportRecord(kind = Named)` per `export_specifier`.
  - `local_name = name`, `exported_name = alias or name`.
- Re-exports:
  - `export { a, b as c } from "./m";`
  - Emit one `ImportRecord(from_export = true)` per imported binding and one `ExportRecord` linked to that import.
  - `source_module = "./m"`.
  - `export { default as Foo } from "./m"` should set the import kind to `DefaultExport`.
- Wildcard re-exports:
  - `export * from "./m";` -> `ExportRecord(kind = Wildcard, source_module = "./m")` plus a `Wildcard` import fact from the source.
  - `export * as ns from "./m";` -> `ExportRecord(kind = Namespace, exported_name = ns, source_module = "./m")` plus a `Wildcard` import fact with namespace/local name `ns`.
- Type exports:
  - `export type { T } from "./types";`, `export type T = ...`
  - Set `is_type_only = true`.

Do not resolve `ExportRecord` targets across files in the first parser/index slice. That belongs to Phase 3.

## Ranges And Scopes

Every retained record should be reconstructible from byte ranges against file content:

- Store byte ranges for file root, declaration, full/extended source, names, module strings, aliases, and statement boundaries.
- Store point ranges for user-facing diagnostics and snapshots.
- Keep both `statement_range` and focused binding/export ranges because current `Import` and `ExportStatement` APIs distinguish a single binding from the whole statement.
- Ranges must be byte offsets from UTF-8 source bytes. Do not derive offsets from Python string indices.

Minimal phase-1 scope rules:

- Create one `File` scope per file.
- Create one owned body scope for each top-level class/function/namespace.
- Assign each import/export to the narrowest retained scope by range containment: file scope or nearest top-level symbol body scope.
- Do not create scopes for every `if`, `for`, `while`, `try`, match/switch case, lambda/arrow expression, or nested block in the first parser/index slice.
- Do not compute name lookup tables, hoisting, `global`/`nonlocal`, closure captures, or TypeScript block scoping in the first parser/index slice.

## What The First Parser/Index Slice Must Not Eagerly Materialize

- Python wrapper objects for every node.
- Persistent tree-sitter node handles after extraction.
- `CodeBlock`, `Statement`, `Expression`, `FunctionCall`, JSX, type-expression, decorator, comment, and docstring objects.
- `rustworkx` graph payloads or Python object graph edges.
- Dependency edges, symbol usage records, superclass/interface edges, import resolution edges, or export resolution edges.
- Full local-variable indexes inside functions/classes.
- External module records beyond unresolved import module strings.
- Directory tree, tsconfig path expansion, sys.path/import override resolution, and package `__init__.py` wildcard semantics.
- Edit/formatting metadata beyond source ranges needed by later lazy handles.

## Golden Snapshots

Add Rust IR snapshot tests that compare stable JSON, sorted by `(file_path, range_start, kind, name)` and using interned string values in the debug dump for readability.

### Python Fixtures

- `py_symbols_basic.py`
  - module imports, `from` imports, aliases, wildcard import
  - top-level decorated function, async function, class, simple globals, tuple assignment
  - nested function/class/assignment present but absent from phase-1 symbols
- `py_relative_imports.py`
  - `from . import x`, `from ..pkg.mod import A as B`, `from __future__ import annotations`
  - verify raw module text, relative level, future flag
- `py_scopes.py`
  - top-level import, import inside a function, import inside a class method
  - verify import scope assignment without full nested statement materialization

### TypeScript/TSX Fixtures

- `ts_symbols_basic.ts`
  - function, generator, class, abstract class, interface, type alias, enum, namespace, const global, arrow-function const
- `ts_imports.ts`
  - default, named, aliased named, namespace, side-effect, type-only import
- `ts_dynamic_imports.js`
  - `require`, `await import`, destructured require, side-effect require
- `ts_exports.ts`
  - declaration exports, default exports, named export clause, re-export clause, wildcard re-export, namespace re-export, type export, export equals
- `tsx_component.tsx`
  - JSX in a function component and exported component; verify parser accepts JSX but does not materialize JSX records
- `ts_scopes.ts`
  - imports inside top-level function/class body plus top-level exports; verify minimal scope owners

### Existing Tests To Mine For Source Cases

- Python import cases: `tests/unit/sdk/python/import_resolution/`
- Python globals: `tests/unit/sdk/python/global_var/`
- TypeScript import cases: `tests/unit/sdk/typescript/file/test_file_import_statemets.py`, `tests/unit/sdk/typescript/import_resolution/`
- TypeScript export cases: `tests/unit/sdk/typescript/file/test_file_export_statements.py`, `tests/unit/sdk/typescript/export/`
- TypeScript globals and arrow functions: `tests/unit/sdk/typescript/global_var/`, `tests/unit/sdk/typescript/function/test_function_arrow.py`

## Proposed First Vertical Slice

1. Add Rust parser crate module boundaries and tree-sitter setup.
   - `parser::language` maps paths to parser grammar and `Language`.
   - `parser::parse_file(path, bytes)` returns parse status and root range.
1. Add arena records and interners.
   - `Index` owns files, symbols, imports, exports, scopes, strings, paths.
   - JSON debug dump exposes stable, string-expanded snapshots.
1. Implement file discovery input from Python.
   - Python passes `(relative_path, absolute_path, language, content bytes/hash)` or a repo-operator file list.
   - Rust does not walk the filesystem independently in the first slice.
1. Implement Python extraction.
   - File records, top-level class/function/global symbols, imports, ranges, file/top-level symbol scopes.
   - Snapshot `py_symbols_basic.py`, `py_relative_imports.py`, and `py_scopes.py`.
1. Implement TypeScript/TSX extraction.
   - File records, top-level declaration/global/function symbols, static imports, direct export facts, ranges, scopes.
   - Snapshot `ts_symbols_basic.ts`, `ts_imports.ts`, `ts_exports.ts`, and `tsx_component.tsx`.
1. Add dynamic import/require subset.
   - Snapshot `ts_dynamic_imports.js`.
1. Expose PyO3 debug/query APIs.
   - `files() -> Vec<FileId>`
   - `symbols(file_id?) -> Vec<SymbolId>`
   - `classes()`, `functions()`, `imports()`, `exports()`
   - record lookup APIs returning compact structs or JSON for tests
1. Add parity smoke tests against the Python backend counts/names for the fixture set.
   - Compare file paths, symbol names/kinds, import local names/kinds/modules, export names/kinds/modules.
   - Do not compare dependency edges or wrapper behavior in this phase.

## Acceptance For The First Parser/Index Slice

- Building the Rust index for fixture repos does not instantiate Python `SourceFile`, `Symbol`, `Import`, `Export`, `CodeBlock`, `Statement`, or expression objects.
- Snapshot debug output is deterministic across runs.
- Python and Rust backends agree on top-level file/symbol/import/export counts and names for the selected fixtures.
- Unsupported syntax is represented as an omitted record plus parse warning/debug gap, not as a placeholder Python object.
- All records have byte ranges and point ranges sufficient to reconstruct source substrings from file bytes.
