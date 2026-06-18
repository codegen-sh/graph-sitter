# Rust Rewrite API Inventory

Inventory date: 2026-06-18

Scope: Python-facing public APIs that the Rust backend must preserve for `Codebase`, `File`/`SourceFile`, `Symbol`, `Import`, `Export`, and `Directory`. This inventory prioritizes APIs referenced by API docs, unit tests, and codemod examples/workflows. Source references point to the current Python implementation.

Priority meanings:

- P0: First Rust backend slice must preserve behavior and return shapes. It may still return Python compatibility handles, but query results, ordering, exceptions, and basic resolution semantics must match.
- P1: Public and used enough to preserve, but can initially fall back to the Python backend or existing transaction manager. Most edit/search/AST-manipulation APIs are here.
- P2: Preserve as explicit fallback, compatibility shim, or documented unsupported behavior for the Rust backend. These are Git/GitHub, AI, visualization, diagnostics, or low-level/internal APIs.

## P0 Compatibility Surface

### Codebase

Source references: `src/graph_sitter/core/codebase.py:259`, `src/graph_sitter/core/codebase.py:286`, `src/graph_sitter/core/codebase.py:338`, `src/graph_sitter/core/codebase.py:351`, `src/graph_sitter/core/codebase.py:366`, `src/graph_sitter/core/codebase.py:399`, `src/graph_sitter/core/codebase.py:409`, `src/graph_sitter/core/codebase.py:421`, `src/graph_sitter/core/codebase.py:432`, `src/graph_sitter/core/codebase.py:443`, `src/graph_sitter/core/codebase.py:455`, `src/graph_sitter/core/codebase.py:529`, `src/graph_sitter/core/codebase.py:551`, `src/graph_sitter/core/codebase.py:596`, `src/graph_sitter/core/codebase.py:609`, `src/graph_sitter/core/codebase.py:631`, `src/graph_sitter/core/codebase.py:644`, `src/graph_sitter/core/codebase.py:671`, `src/graph_sitter/core/codebase.py:687`, `src/graph_sitter/core/codebase.py:711`, `src/graph_sitter/core/codebase.py:803`, `src/graph_sitter/core/codebase.py:846`, `src/graph_sitter/core/codebase.py:1331`, `src/graph_sitter/core/codebase.py:1405`, `src/graph_sitter/core/codebase.py:1452`.

Docs/tests/codemods evidence: `docs/api-reference/core/Codebase.mdx`, `tests/unit/sdk/core/test_codebase.py`, `tests/unit/sdk/python/codebase/test_codebase.py`, `src/codemods/**`, `docs/tutorials/**`.

- Construction and metadata:
  - `Codebase(...)` constructor surface and config behavior.
  - `Codebase.from_files(...)` and `Codebase.from_string(...)` for fixture/test construction.
  - `Codebase.from_repo(...)` should keep its Python checkout/setup behavior; the Rust engine can start after the repo path and config are resolved.
  - `codebase.name` and `codebase.language`.
- File and directory queries:
  - `codebase.files(...)`, including `extensions=None`, `extensions="*"`, `extensions=[...]`, source-file-only default behavior, and alphabetical sorting.
  - `codebase.has_file(filepath, ignore_case=False)` and `codebase.get_file(filepath, optional=False, ignore_case=False)`.
  - `codebase.directories`, `codebase.has_directory(dir_path, ignore_case=False)`, and `codebase.get_directory(dir_path, optional=False, ignore_case=False)`.
- Graph-level node queries:
  - `codebase.imports`.
  - `codebase.exports` for TypeScript, including `NotImplementedError` on Python codebases.
  - `codebase.symbols`, `codebase.classes`, `codebase.functions`, `codebase.global_vars`, `codebase.interfaces`, `codebase.types`.
  - `codebase.has_symbol(name)`, `codebase.get_symbol(name, optional=False)`, `codebase.get_symbols(name)`, `codebase.get_class(name, optional=False)`, `codebase.get_function(name, optional=False)`.
  - Ambiguity and missing-result errors for `get_symbol`, `get_class`, and `get_function`.
- Transaction compatibility:
  - `codebase.commit(...)` and `codebase.reset(...)` must remain callable for codemod workflows. The first Rust slice should delegate to the existing Python transaction manager rather than porting edit application.

### File and SourceFile

Source references: `src/graph_sitter/core/file.py:50`, `src/graph_sitter/core/file.py:121`, `src/graph_sitter/core/file.py:131`, `src/graph_sitter/core/file.py:168`, `src/graph_sitter/core/file.py:180`, `src/graph_sitter/core/file.py:191`, `src/graph_sitter/core/file.py:253`, `src/graph_sitter/core/file.py:411`, `src/graph_sitter/core/file.py:613`, `src/graph_sitter/core/file.py:633`, `src/graph_sitter/core/file.py:647`, `src/graph_sitter/core/file.py:669`, `src/graph_sitter/core/file.py:681`, `src/graph_sitter/core/file.py:696`, `src/graph_sitter/core/file.py:708`, `src/graph_sitter/core/file.py:734`, `src/graph_sitter/core/file.py:752`, `src/graph_sitter/core/file.py:773`, `src/graph_sitter/core/file.py:785`, `src/graph_sitter/core/file.py:797`, `src/graph_sitter/core/file.py:810`, `src/graph_sitter/core/file.py:826`, `src/graph_sitter/core/file.py:839`, `src/graph_sitter/core/file.py:921`, `src/graph_sitter/core/file.py:1174`, `src/graph_sitter/python/file.py:38`, `src/graph_sitter/python/file.py:85`, `src/graph_sitter/typescript/file.py:47`, `src/graph_sitter/typescript/file.py:61`, `src/graph_sitter/typescript/file.py:79`, `src/graph_sitter/typescript/file.py:91`, `src/graph_sitter/typescript/file.py:107`, `src/graph_sitter/typescript/file.py:121`, `src/graph_sitter/typescript/file.py:136`, `src/graph_sitter/typescript/file.py:148`, `src/graph_sitter/typescript/file.py:160`, `src/graph_sitter/typescript/file.py:174`, `src/graph_sitter/typescript/file.py:426`.

Docs/tests/codemods evidence: `docs/api-reference/core/File.mdx`, `docs/api-reference/core/SourceFile.mdx`, `docs/api-reference/python/PyFile.mdx`, `docs/api-reference/typescript/TSFile.mdx`, `tests/unit/sdk/python/file/test_file_properties.py`, `tests/unit/sdk/typescript/file/test_file_import_statemets.py`, `tests/unit/sdk/typescript/export/test_export_resolve_export.py`.

- File identity and content:
  - `file.name`, `file.file_path`, `file.filepath`, `file.path`.
  - `file.content`, `file.content_bytes`, `file.source`.
  - `file.directory`, `file.extension`, `file.is_binary`.
  - `File.get_extensions()`, `PyFile.get_extensions()`, `TSFile.get_extensions()`.
  - Class constructors used in tests: `File.from_content(...)`, language-specific `from_content(...)`, and `create_from_filepath(...)`.
- Source-file graph queries:
  - `file.imports`, `file.import_statements`, `file.inbound_imports`, `file.importers`.
  - `file.has_import(name_or_source)` and `file.get_import(name_or_source, optional=False)`.
  - `file.symbols(...)`, including nested filtering behavior.
  - `file.symbols_sorted_topologically`.
  - `file.get_symbol(name, optional=False)`.
  - `file.global_vars`, `file.get_global_var(name, optional=False)`.
  - `file.classes`, `file.get_class(name, optional=False)`.
  - `file.functions`, `file.get_function(name, optional=False)`.
  - `file.find_by_byte_range(...)`.
- TypeScript-specific source-file queries:
  - `file.exports`, `file.export_statements`, `file.default_exports`, `file.named_exports`, `file.get_export(name, optional=False)`.
  - `file.interfaces`, `file.get_interface(name, optional=False)`.
  - `file.types`, `file.get_type(name, optional=False)`.
  - `file.get_namespace(name, optional=False)`.
  - `file.promise_chains` should return the same shape if the Rust slice exposes TS expression indexes; otherwise route to Python initially.
- Import string helpers:
  - `file.import_module_name(...)`.
  - `PyFile.get_import_string(...)`.
  - `TSFile.get_import_string(...)`.

### Symbol and Inherited Editable/Usable APIs

Source references: `src/graph_sitter/core/symbol.py:41`, `src/graph_sitter/core/symbol.py:96`, `src/graph_sitter/core/symbol.py:141`, `src/graph_sitter/core/symbol.py:435`, `src/graph_sitter/core/interfaces/has_name.py:17`, `src/graph_sitter/core/interfaces/has_name.py:29`, `src/graph_sitter/core/interfaces/usable.py:25`, `src/graph_sitter/core/interfaces/usable.py:44`, `src/graph_sitter/core/interfaces/importable.py:44`, `src/graph_sitter/core/interfaces/editable.py:236`, `src/graph_sitter/core/interfaces/editable.py:372`, `src/graph_sitter/core/interfaces/editable.py:383`, `src/graph_sitter/core/interfaces/editable.py:1048`, `src/graph_sitter/python/symbol.py:33`, `src/graph_sitter/python/symbol.py:45`, `src/graph_sitter/typescript/symbol.py:35`, `src/graph_sitter/typescript/symbol.py:130`, `src/graph_sitter/typescript/symbol.py:407`.

Docs/tests/codemods evidence: `docs/api-reference/core/Symbol.mdx`, `docs/api-reference/core/Editable.mdx`, `docs/api-reference/core/Usable.mdx`, `docs/api-reference/core/HasName.mdx`, `docs/api-reference/python/PySymbol.mdx`, `docs/api-reference/typescript/TSSymbol.mdx`, codemods under `src/codemods/`.

- Symbol identity and source:
  - `symbol.name`, `symbol.full_name`, `symbol.symbol_type`.
  - `symbol.file`, `symbol.filepath`, `symbol.source`, `symbol.extended_source`, `symbol.extended_nodes`.
  - Python `symbol.is_exported`.
  - TypeScript export-facing metadata such as `symbol.export`, `symbol.exported_name`, `symbol.has_semicolon`, and `symbol.semicolon_node` where used by TS export/edit helpers.
- Graph relationships:
  - `symbol.dependencies`.
  - `symbol.usages` and `symbol.symbol_usages`.
  - `symbol.descendant_symbols`.
  - `symbol.function_calls`.
- Name/source helpers that must still work on compatibility handles:
  - `symbol.get_name()`.
  - `symbol.get_import_string(...)` for Python and TypeScript language subclasses.

### Import

Source references: `src/graph_sitter/core/import_resolution.py:60`, `src/graph_sitter/core/import_resolution.py:165`, `src/graph_sitter/core/import_resolution.py:184`, `src/graph_sitter/core/import_resolution.py:202`, `src/graph_sitter/core/import_resolution.py:213`, `src/graph_sitter/core/import_resolution.py:224`, `src/graph_sitter/core/import_resolution.py:237`, `src/graph_sitter/core/import_resolution.py:252`, `src/graph_sitter/core/import_resolution.py:278`, `src/graph_sitter/core/import_resolution.py:291`, `src/graph_sitter/core/import_resolution.py:356`, `src/graph_sitter/core/import_resolution.py:379`, `src/graph_sitter/core/import_resolution.py:392`, `src/graph_sitter/core/import_resolution.py:526`, `src/graph_sitter/core/import_resolution.py:545`, `src/graph_sitter/python/import_resolution.py:33`, `src/graph_sitter/python/import_resolution.py:44`, `src/graph_sitter/python/import_resolution.py:63`, `src/graph_sitter/python/import_resolution.py:87`, `src/graph_sitter/python/import_resolution.py:331`, `src/graph_sitter/typescript/import_resolution.py:35`, `src/graph_sitter/typescript/import_resolution.py:58`, `src/graph_sitter/typescript/import_resolution.py:78`, `src/graph_sitter/typescript/import_resolution.py:93`, `src/graph_sitter/typescript/import_resolution.py:110`, `src/graph_sitter/typescript/import_resolution.py:137`, `src/graph_sitter/typescript/import_resolution.py:200`, `src/graph_sitter/typescript/import_resolution.py:548`, `src/graph_sitter/typescript/import_resolution.py:582`, `src/graph_sitter/typescript/import_resolution.py:603`.

Docs/tests/codemods evidence: `docs/api-reference/core/Import.mdx`, `docs/api-reference/python/PyImport.mdx`, `docs/api-reference/typescript/TSImport.mdx`, `tests/unit/sdk/typescript/file/test_file_import_statemets.py`, TS export/import resolution tests, codemods under `src/codemods/`.

- Import identity:
  - `import.name`, `import.source`, `import.module`, `import.symbol_name`, `import.alias`, `import.import_type`.
  - `import.import_specifier`.
- Import predicates:
  - `import.is_aliased_import`, `import.is_module_import`, `import.is_symbol_import`, `import.is_wildcard_import`, `import.is_dynamic`, `import.is_reexport`.
  - TypeScript `import.is_type_import`, `import.is_default_import`, `import.namespace_imports`, `import.is_namespace_import`.
- Resolution:
  - `import.from_file`, `import.to_file`.
  - `import.imported_symbol`, `import.resolved_symbol`, `import.imported_exports`, `import.namespace`.
  - Python `resolve_import(...)` and TypeScript `resolve_import(...)` semantics should be reflected through the public properties even if the function itself is not exposed as the first Rust boundary.
- Import string helpers:
  - `import.get_import_string(...)`.

### Export

Source references: `src/graph_sitter/core/export.py:22`, `src/graph_sitter/core/export.py:41`, `src/graph_sitter/core/export.py:50`, `src/graph_sitter/core/export.py:61`, `src/graph_sitter/core/export.py:69`, `src/graph_sitter/core/export.py:80`, `src/graph_sitter/typescript/export.py:45`, `src/graph_sitter/typescript/export.py:236`, `src/graph_sitter/typescript/export.py:248`, `src/graph_sitter/typescript/export.py:274`, `src/graph_sitter/typescript/export.py:299`, `src/graph_sitter/typescript/export.py:312`, `src/graph_sitter/typescript/export.py:328`, `src/graph_sitter/typescript/export.py:339`, `src/graph_sitter/typescript/export.py:350`, `src/graph_sitter/typescript/export.py:365`, `src/graph_sitter/typescript/export.py:381`, `src/graph_sitter/typescript/export.py:523`, `src/graph_sitter/typescript/export.py:549`, `src/graph_sitter/typescript/export.py:561`, `src/graph_sitter/typescript/export.py:578`, `src/graph_sitter/typescript/export.py:617`.

Docs/tests/codemods evidence: `docs/api-reference/core/Export.mdx`, `docs/api-reference/typescript/TSExport.mdx`, `tests/unit/sdk/typescript/export/test_export_resolve_export.py`, TS export codemod examples.

- Export identity and source:
  - `export.name`, `export.source`, `export.exported_name` where exposed by TS-specific classes.
  - `export.descendant_symbols`.
- Export predicates:
  - `export.is_named_export`, `export.is_default_export`, `export.is_default_symbol_export`, `export.is_type_export`, `export.is_reexport`, `export.is_wildcard_export`, `export.is_module_export`, `export.is_aliased`, `export.is_external_export`.
- Resolution:
  - `export.declared_symbol`, `export.exported_symbol`, `export.resolved_symbol`.
  - Reexport and wildcard resolution must preserve current symbol/import/file targets.
- Import string helpers:
  - `export.to_import_string(...)` and `export.get_import_string(...)`.

### Directory

Source references: `src/graph_sitter/core/directory.py:31`, `src/graph_sitter/core/directory.py:60`, `src/graph_sitter/core/directory.py:71`, `src/graph_sitter/core/directory.py:95`, `src/graph_sitter/core/directory.py:99`, `src/graph_sitter/core/directory.py:105`, `src/graph_sitter/core/directory.py:116`, `src/graph_sitter/core/directory.py:158`, `src/graph_sitter/core/directory.py:177`, `src/graph_sitter/core/directory.py:188`, `src/graph_sitter/core/directory.py:199`, `src/graph_sitter/core/directory.py:204`, `src/graph_sitter/core/directory.py:213`, `src/graph_sitter/core/directory.py:224`, `src/graph_sitter/core/directory.py:240`, `src/graph_sitter/core/interfaces/has_symbols.py:51`.

Docs/tests/codemods evidence: `docs/api-reference/core/Directory.mdx`, `tests/unit/sdk/core/test_directory.py`, directory traversal examples in docs/codemods.

- Directory identity and traversal:
  - `directory.name`, `directory.path`, `directory.dirpath`, `directory.parent`.
  - `directory.files(...)`, `directory.subdirectories(...)`, `directory.items`, `directory.item_names`, `directory.file_names`, `directory.tree`.
  - `directory.get_file(name)`, `directory.get_subdirectory(name)`.
  - `__iter__`, `__contains__`, `__len__`, and `__getitem__`.
- Inherited recursive symbol queries from `HasSymbols`:
  - `directory.symbols`, `directory.import_statements`, `directory.global_vars`, `directory.classes`, `directory.functions`, `directory.exports`, `directory.imports`.
  - `directory.get_symbol(...)`, `directory.get_import_statement(...)`, `directory.get_global_var(...)`, `directory.get_class(...)`, `directory.get_function(...)`, `directory.get_export(...)`, `directory.get_import(...)`.

## P1 Compatibility Surface

P1 APIs should be preserved, but the first Rust backend can use the current Python implementation as a fallback. These APIs create or mutate files, edits, imports, exports, names, comments, or AST source ranges.

### Codebase P1

Source references: `src/graph_sitter/core/codebase.py:325`, `src/graph_sitter/core/codebase.py:388`, `src/graph_sitter/core/codebase.py:476`, `src/graph_sitter/core/codebase.py:511`, `src/graph_sitter/core/codebase.py:748`, `src/graph_sitter/core/codebase.py:1012`, `src/graph_sitter/core/codebase.py:1185`, `src/graph_sitter/core/codebase.py:1196`, `src/graph_sitter/core/codebase.py:1293`, `src/graph_sitter/core/codebase.py:1310`.

- `codebase.create_file(...)`.
- `codebase.create_directory(...)`.
- `codebase.codeowners`.
- `codebase.external_modules`.
- `codebase.get_relative_path(from_file, to_file)`.
- `codebase.find_by_span(span)`.
- `codebase.set_session_options(...)`.
- `codebase.ai(...)`, `codebase.ai_client`, and AI/session helpers, if enabled in the environment.
- `codebase.visualize(...)`, if graph handles can be mapped back to a display graph.

### File and SourceFile P1

Source references: `src/graph_sitter/core/file.py:238`, `src/graph_sitter/core/file.py:262`, `src/graph_sitter/core/file.py:294`, `src/graph_sitter/core/file.py:329`, `src/graph_sitter/core/file.py:359`, `src/graph_sitter/core/file.py:396`, `src/graph_sitter/core/file.py:976`, `src/graph_sitter/core/file.py:1027`, `src/graph_sitter/core/file.py:1047`, `src/graph_sitter/typescript/file.py:214`, `src/graph_sitter/typescript/file.py:230`, `src/graph_sitter/typescript/file.py:298`, `src/graph_sitter/typescript/file.py:322`, `src/graph_sitter/typescript/file.py:397`.

- `file.write(...)`, `file.write_bytes(...)`.
- `file.edit(...)`, `file.replace(...)`, `file.remove(...)`.
- `file.rename(...)`, `file.update_filepath(...)`.
- `file.add_import(...)`.
- `file.add_symbol_from_source(...)`, `file.add_symbol(...)`.
- TypeScript `file.add_export_to_symbol(...)`.
- TypeScript `file.remove_unused_exports(...)`.
- TypeScript `file.has_export_statement_for_path(...)` and `file.get_export_statement_for_path(...)`.
- TypeScript `file.update_filepath(...)` behavior that also updates import paths.

### Editable and Symbol P1

Source references: `src/graph_sitter/core/symbol.py:123`, `src/graph_sitter/core/symbol.py:169`, `src/graph_sitter/core/symbol.py:179`, `src/graph_sitter/core/symbol.py:189`, `src/graph_sitter/core/symbol.py:204`, `src/graph_sitter/core/symbol.py:219`, `src/graph_sitter/core/symbol.py:242`, `src/graph_sitter/core/symbol.py:269`, `src/graph_sitter/core/symbol.py:408`, `src/graph_sitter/core/interfaces/has_name.py:51`, `src/graph_sitter/core/interfaces/has_name.py:64`, `src/graph_sitter/core/interfaces/has_name.py:79`, `src/graph_sitter/core/interfaces/usable.py:78`, `src/graph_sitter/core/interfaces/editable.py:394`, `src/graph_sitter/core/interfaces/editable.py:428`, `src/graph_sitter/core/interfaces/editable.py:483`, `src/graph_sitter/core/interfaces/editable.py:516`, `src/graph_sitter/core/interfaces/editable.py:571`, `src/graph_sitter/core/interfaces/editable.py:604`, `src/graph_sitter/core/interfaces/editable.py:633`, `src/graph_sitter/core/interfaces/editable.py:683`, `src/graph_sitter/core/interfaces/editable.py:859`, `src/graph_sitter/core/interfaces/editable.py:905`, `src/graph_sitter/core/interfaces/editable.py:936`, `src/graph_sitter/core/interfaces/editable.py:1040`, `src/graph_sitter/core/interfaces/editable.py:1084`, `src/graph_sitter/core/interfaces/editable.py:1090`, `src/graph_sitter/core/interfaces/editable.py:1098`, `src/graph_sitter/core/interfaces/editable.py:1106`, `src/graph_sitter/core/interfaces/editable.py:1115`, `src/graph_sitter/core/interfaces/editable.py:1132`, `src/graph_sitter/core/interfaces/editable.py:1140`, `src/graph_sitter/core/interfaces/editable.py:1148`.

- `symbol.set_name(...)`, `symbol.rename(...)`, `symbol.edit(...)`, source setter behavior.
- `symbol.comment`, `symbol.inline_comment`, `symbol.set_comment(...)`, `symbol.add_comment(...)`, `symbol.set_inline_comment(...)`.
- `symbol.insert_before(...)`, `symbol.insert_after(...)`, `symbol.remove(...)`, `symbol.move_to_file(...)`, `symbol.add_keyword(...)`.
- `Editable.find_string_literals(...)`, `find(...)`, `search(...)`.
- `Editable.replace(...)`, `insert_before(...)`, `insert_after(...)`, `edit(...)`, `remove(...)`.
- `Editable.variable_usages`, `get_variable_usages(...)`.
- `Editable.flag(...)`, `reduce_condition(...)`.
- `Editable.is_wrapped_in(...)`, `parent_of_type(...)`, `parent_of_types(...)`, `is_child_of(...)`, `ancestors`, `parent_statement`, `parent_function`, `parent_class`.

### Import, Export, and Directory P1

Source references: `src/graph_sitter/core/import_resolution.py:437`, `src/graph_sitter/core/import_resolution.py:458`, `src/graph_sitter/core/import_resolution.py:479`, `src/graph_sitter/core/import_resolution.py:503`, `src/graph_sitter/typescript/import_resolution.py:624`, `src/graph_sitter/typescript/export.py:413`, `src/graph_sitter/typescript/export.py:651`, `src/graph_sitter/core/directory.py:244`, `src/graph_sitter/core/directory.py:252`, `src/graph_sitter/core/directory.py:257`.

- `import.set_import_module(...)`, `import.set_import_symbol_alias(...)`, `import.rename(...)`, `import.remove(...)`.
- TypeScript `import.set_import_module(...)` path-update behavior.
- `export.make_non_default(...)`, `export.reexport_symbol(...)`, and inherited `export.remove(...)`.
- `directory.update_filepath(...)`, `directory.remove(...)`, `directory.rename(...)`.

## P2 Compatibility Surface

P2 APIs are public or semi-public, but should not drive the first Rust data model. Preserve them through Python-side delegation, clear errors, or later parity work.

Source references: `src/graph_sitter/core/codebase.py:235`, `src/graph_sitter/core/codebase.py:241`, `src/graph_sitter/core/codebase.py:822`, `src/graph_sitter/core/codebase.py:833`, `src/graph_sitter/core/codebase.py:865`, `src/graph_sitter/core/codebase.py:931`, `src/graph_sitter/core/codebase.py:938`, `src/graph_sitter/core/codebase.py:974`, `src/graph_sitter/core/codebase.py:1116`, `src/graph_sitter/core/codebase.py:1542`, `src/graph_sitter/core/codebase.py:1546`.

- Git and GitHub:
  - `codebase.github`, `codebase.op`.
  - `codebase.git_commit`, `codebase.default_branch`, `codebase.current_commit`, `codebase.checkout(...)`.
  - `codebase.get_diffs(...)`, `codebase.get_diff(...)`.
  - `codebase.create_pr(...)`, `codebase.create_pr_comment(...)`, `codebase.create_pr_review_comment(...)`.
  - PR-diff helpers such as modified-symbol lookup should remain Python-side until Rust graph parity is proven.
- Diagnostics, logs, and visualization:
  - `codebase.reset_logs()`.
  - Rich repr and diagnostic properties relying on Python graph object counts.
  - Visualization internals and `viz`/graph display helpers.
- Low-level/internal object access:
  - `ctx`, `_op`, raw `ts_node`, `node_id`, `parent`, `get_nodes()`, `parse/sync/recompute` helpers, and language-specific noapidoc helpers such as `valid_symbol_names`/`valid_import_names`.
  - These should not become the Rust public contract; if compatibility requires them, expose minimal Python shim objects or fail explicitly under the Rust backend.

## APIs That Currently Materialize Full Lists

These are the main memory-sensitive APIs. They should keep returning Python `list` objects for compatibility, but the Rust backend should generate compact ID lists first and wrap handles lazily.

### Codebase-wide materializers

- `codebase.files(...)` currently returns sorted Python file objects and may walk the repo operator for non-source files: `src/graph_sitter/core/codebase.py:286`.
- `codebase.directories` returns `list(self.ctx.directories.values())`: `src/graph_sitter/core/codebase.py:338`.
- `codebase.imports` returns `ctx.get_nodes(NodeType.IMPORT)`: `src/graph_sitter/core/codebase.py:351`.
- `codebase.exports` returns `ctx.get_nodes(NodeType.EXPORT)`: `src/graph_sitter/core/codebase.py:366`.
- `codebase.external_modules` returns `ctx.get_nodes(NodeType.EXTERNAL)`: `src/graph_sitter/core/codebase.py:388`.
- `codebase.symbols`, `classes`, `functions`, `global_vars`, `interfaces`, and `types` call `_symbols`, which scans `ctx.get_nodes(NodeType.SYMBOL)` and filters top-level symbols: `src/graph_sitter/core/codebase.py:273`, `src/graph_sitter/core/codebase.py:399`.
- `codebase.get_symbol(...)`, `get_symbols(...)`, `get_class(...)`, and `get_function(...)` scan those full lists: `src/graph_sitter/core/codebase.py:644`, `src/graph_sitter/core/codebase.py:671`, `src/graph_sitter/core/codebase.py:687`, `src/graph_sitter/core/codebase.py:711`.

### SourceFile materializers

- `SourceFile` inherits `Importable`, whose constructor appends each parsed node into `self.file._nodes`: `src/graph_sitter/core/interfaces/importable.py:37`.
- `file.get_nodes()` returns the per-file `_nodes` list: `src/graph_sitter/core/file.py:725`.
- `file.imports`, `file.import_statements`, `file.symbols`, `file.global_vars`, `file.classes`, and `file.functions` all filter or transform that per-file list: `src/graph_sitter/core/file.py:633`, `src/graph_sitter/core/file.py:669`, `src/graph_sitter/core/file.py:708`, `src/graph_sitter/core/file.py:773`, `src/graph_sitter/core/file.py:797`, `src/graph_sitter/core/file.py:826`.
- `file.symbols_sorted_topologically` constructs a subgraph of in-file symbol nodes: `src/graph_sitter/core/file.py:752`.
- `file.inbound_imports` combines `self.symbols`, `self.imports`, and `self.symbol_usages`: `src/graph_sitter/core/file.py:613`.
- TypeScript `file.exports`, `export_statements`, `default_exports`, `named_exports`, `interfaces`, and `types` materialize filtered lists: `src/graph_sitter/typescript/file.py:47`, `src/graph_sitter/typescript/file.py:61`, `src/graph_sitter/typescript/file.py:79`, `src/graph_sitter/typescript/file.py:91`, `src/graph_sitter/typescript/file.py:121`, `src/graph_sitter/typescript/file.py:148`.

### Directory recursive materializers

- `directory.files(...)` recursively collects files into a list: `src/graph_sitter/core/directory.py:116`.
- `directory.subdirectories(...)`, `items`, `item_names`, `file_names`, and `tree` all materialize directory children: `src/graph_sitter/core/directory.py:158`, `src/graph_sitter/core/directory.py:177`, `src/graph_sitter/core/directory.py:188`, `src/graph_sitter/core/directory.py:199`, `src/graph_sitter/core/directory.py:204`.
- `HasSymbols` recursively chains per-file properties for `symbols`, `imports`, `exports`, `classes`, `functions`, and globals: `src/graph_sitter/core/interfaces/has_symbols.py:51`.

### Relationship materializers

- `symbol.dependencies` traverses descendant symbols and dependency graph out-edges: `src/graph_sitter/core/interfaces/importable.py:44`.
- `symbol.usages` and `symbol.symbol_usages` traverse graph edges and collect usage objects: `src/graph_sitter/core/interfaces/usable.py:25`, `src/graph_sitter/core/interfaces/usable.py:44`.
- `import.imported_symbol`, `import.resolved_symbol`, `import.imported_exports`, `import.from_file`, and `import.to_file` resolve through graph edges and source-file/import lists: `src/graph_sitter/core/import_resolution.py:252`, `src/graph_sitter/core/import_resolution.py:278`, `src/graph_sitter/core/import_resolution.py:291`, `src/graph_sitter/core/import_resolution.py:356`, `src/graph_sitter/core/import_resolution.py:379`.
- `export.declared_symbol`, `export.exported_symbol`, and `export.resolved_symbol` resolve across TS export/import/file graph edges: `src/graph_sitter/typescript/export.py:350`, `src/graph_sitter/typescript/export.py:365`, `src/graph_sitter/typescript/export.py:381`.

## Recommended First-Slice Compatibility Boundary

The first Rust backend slice should be read-heavy and graph-oriented:

- Parse Python and TypeScript/TSX source files into compact records for files, top-level symbols, classes, functions, globals, TypeScript interfaces/types, imports, exports, and ranges.
- Preserve public list-returning APIs by returning Python lists of lazy compatibility handles, but do not eagerly instantiate every Python node object during codebase construction.
- Preserve current public ordering: alphabetical sorting for `codebase.files`, sorted symbol/class/function lists where the Python API sorts today, and existing file-local ordering for imports/exports/symbols.
- Preserve path normalization, `optional=True` behavior, ambiguity errors, Python-vs-TypeScript export behavior, and `ignore_case` lookup behavior.
- Implement import/export resolution, dependency edges, and usage records in Rust before claiming parity for `import.resolved_symbol`, `import.imported_symbol`, `export.resolved_symbol`, `symbol.dependencies`, or `symbol.usages`.
- Keep edit APIs, transaction application, formatting, comments, AST parent navigation, AI, Git/GitHub, and visualization on the Python backend/fallback path for the first slice.
- Make unsupported P1/P2 APIs under the Rust backend explicit: either delegate to Python compatibility objects or raise a clear `NotImplementedError`. P0 APIs should not silently fall back to incomplete or behavior-changing approximations.
- Avoid exposing persistent Rust-owned tree-sitter node wrappers as the long-term contract. Use stable IDs plus byte ranges/source text and construct Python handles only on demand.

## Initial Rust Data Required For P0

- `FileRecord`: stable file ID, interned path/name/extension, language, content hash, source/binary flag, directory ID, root range.
- `DirectoryRecord`: stable directory ID, interned path/name, parent ID, sorted child file/directory ID indexes.
- `SymbolRecord`: stable symbol ID, file ID, kind, name/full-name IDs, top-level/nested flag, parent symbol ID, range, extended range, export metadata.
- `ImportRecord`: stable import ID, file ID, module/name/alias IDs, kind flags, statement range, target file/symbol/export IDs where resolved.
- `ExportRecord`: stable export ID, file ID, exported name, kind flags, declared/exported/resolved target IDs, range.
- `UsageRecord`: stable usage ID, source file/node ID, target symbol/import/export ID, usage kind, range.
- `GraphEdge`: compact dependency and resolution edges by ID, not Python object payloads.
