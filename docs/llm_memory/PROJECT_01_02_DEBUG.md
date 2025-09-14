# Bugfixing

## Scope:
Project implementation consists of:
Read @docs/llm_guidance/project_01.md
Read @docs/llm_guidance/project_02.md

Implementation reports:
Read @docs/llm_memory/PROJECT_01_IMPLEMENTATION.md
Read @docs/llm_memory/PROJECT_02_IMPLEMENTATION.md

# Bug to fix:

~/graph_sitter_kuzu_git$ python -m src.graph_sitter.extensions.kuzu_map.cli sync --project-path ./
Syncing ./ to ./code_graph.kuzu
2025-09-14 14:40:52,953 - graph_sitter.codebase.codebase_context - INFO - > Parsing 1132 files in ALL subdirectories with ['.py'] extensions
2025-09-14 14:41:00,562 - graph_sitter.codebase.codebase_context - INFO - > Building directory tree
2025-09-14 14:41:00,732 - graph_sitter.codebase.codebase_context - INFO - > Computing import resolution edges for 7458 imports
2025-09-14 14:41:01,097 - graph_sitter.codebase.codebase_context - INFO - > Computing superclass dependencies
2025-09-14 14:41:01,176 - graph_sitter.codebase.codebase_context - INFO - > Incrementally computing dependencies for 39410 nodes
2025-09-14 14:41:11,780 - graph_sitter.codebase.codebase_context - INFO - > Incrementally computing dependencies for 744 nodes
2025-09-14 14:41:11,816 - graph_sitter.codebase.codebase_context - INFO - > Found 1132 files
2025-09-14 14:41:11,826 - graph_sitter.codebase.codebase_context - INFO - > Found 40154 nodes and 146499 edges
2025-09-14 14:41:11,827 - graph_sitter.shared.performance.stopwatch_utils - INFO - Function 'build_graph' took 18 seconds and 982.97 milliseconds to execute.
2025-09-14 14:41:12,075 - src.graph_sitter.extensions.kuzu_map.sync - INFO - Starting full sync to KuzuDB
2025-09-14 14:44:36,369 - src.graph_sitter.extensions.kuzu_map.sync - ERROR - Full sync failed: Runtime exception: Found duplicated primary key value src/graph_sitter/core/autocommit/decorators.py::symbol::wrapped:writer, which violates the uniqueness constraint of the primary key column.
2025-09-14 14:44:37,673 - graph_sitter.typescript.external.ts_analyzer_engine - ERROR - Uncaught exception
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/home/y3i12/graph_sitter_kuzu_git/src/graph_sitter/extensions/kuzu_map/cli.py", line 206, in <module>
    kuzu()
    ~~~~^^
  File "/home/y3i12/.venv/lib/python3.13/site-packages/click/core.py", line 1161, in __call__
    return self.main(*args, **kwargs)
           ~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/y3i12/.venv/lib/python3.13/site-packages/click/core.py", line 1082, in main
    rv = self.invoke(ctx)
  File "/home/y3i12/.venv/lib/python3.13/site-packages/click/core.py", line 1697, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
                           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^
  File "/home/y3i12/.venv/lib/python3.13/site-packages/click/core.py", line 1443, in invoke
    return ctx.invoke(self.callback, **ctx.params)
           ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/y3i12/.venv/lib/python3.13/site-packages/click/core.py", line 788, in invoke
    return __callback(*args, **kwargs)
  File "/home/y3i12/graph_sitter_kuzu_git/src/graph_sitter/extensions/kuzu_map/cli.py", line 38, in sync
    kuzu_sync.sync_full()
    ~~~~~~~~~~~~~~~~~~~^^
  File "/home/y3i12/graph_sitter_kuzu_git/src/graph_sitter/extensions/kuzu_map/sync.py", line 310, in sync_full
    symbols_synced = self._sync_symbols()
  File "/home/y3i12/graph_sitter_kuzu_git/src/graph_sitter/extensions/kuzu_map/sync.py", line 727, in _sync_symbols
    self._sync_single_symbol(symbol)
    ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/home/y3i12/graph_sitter_kuzu_git/src/graph_sitter/extensions/kuzu_map/sync.py", line 943, in _sync_single_symbol
    self.conn.execute(
    ~~~~~~~~~~~~~~~~~^
        """CREATE (s:Symbol {
        ^^^^^^^^^^^^^^^^^^^^^
    ...<14 lines>...
        symbol_data
        ^^^^^^^^^^^
    )
    ^
  File "/home/y3i12/.venv/lib/python3.13/site-packages/kuzu/connection.py", line 134, in execute
    query_result_internal = self._connection.execute(prepared_statement._prepared_statement, parameters)
RuntimeError: Runtime exception: Found duplicated primary key value src/graph_sitter/core/autocommit/decorators.py::symbol::wrapped:writer, which violates the uniqueness constraint of the primary key column.