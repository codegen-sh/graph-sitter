"""Core KuzuDB synchronization functionality."""

import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional

import kuzu
from graph_sitter.core.codebase import Codebase
from graph_sitter.shared.logging.get_logger import get_logger

logger = get_logger(__name__)
"""
SourceFile
Directory
Class
Function
Import

Symbol
Assignment
Interface
TypeAlias
Parameter
CodeBlock
"""
class KuzuSync:
    """Synchronizes graph-sitter codebase to KuzuDB."""

    def __init__(self, codebase: Codebase, db_path: str = "./code_graph.kuzu"):
        self.codebase = codebase
        self.db_path = Path(db_path)
        self.db = kuzu.Database(str(self.db_path))
        self.conn = kuzu.Connection(self.db)
        self._init_schema()

    def _init_schema(self):
        """Initialize KuzuDB schema for code graph."""
        schema_queries = [
            """CREATE NODE TABLE IF NOT EXISTS File(
                path STRING PRIMARY KEY,
                name STRING,
                extension STRING,
                size INT64,
                hash STRING,
                language STRING,
                created_at INT64,
                updated_at INT64
            )""",

            """CREATE NODE TABLE IF NOT EXISTS Function(
                id STRING PRIMARY KEY,
                name STRING,
                qualified_name STRING,
                file_path STRING,
                start_line INT64,
                end_line INT64,
                start_col INT64,
                end_col INT64,
                is_method BOOLEAN,
                is_async BOOLEAN,
                complexity INT64,
                params_count INT64,
                docstring STRING,
                created_at INT64,
                updated_at INT64
            )""",

            """CREATE NODE TABLE IF NOT EXISTS Class(
                id STRING PRIMARY KEY,
                name STRING,
                qualified_name STRING,
                file_path STRING,
                start_line INT64,
                end_line INT64,
                is_abstract BOOLEAN,
                methods_count INT64,
                docstring STRING,
                created_at INT64,
                updated_at INT64
            )""",

            """CREATE NODE TABLE IF NOT EXISTS Import(
                id STRING PRIMARY KEY,
                module_name STRING,
                imported_name STRING,
                alias STRING,
                file_path STRING,
                line_number INT64,
                is_from_import BOOLEAN,
                created_at INT64,
                updated_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS CONTAINS_FUNCTION(
                FROM File TO Function,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS CONTAINS_CLASS(
                FROM File TO Class,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS CONTAINS_IMPORT(
                FROM File TO Import,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS CLASS_METHOD(
                FROM Class TO Function,
                visibility STRING,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS FUNCTION_CALLS(
                FROM Function TO Function,
                line_number INT64,
                call_type STRING,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS IMPORTS(
                FROM Function TO Import,
                usage_type STRING,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS INHERITS(
                FROM Class TO Class,
                inheritance_type STRING,
                created_at INT64
            )"""
        ]

        for query in schema_queries:
            try:
                self.conn.execute(query)
                logger.debug(f"Executed schema query successfully")
            except Exception as e:
                logger.error(f"Failed to execute schema query: {e}")
                raise

    def sync_full(self):
        """Perform full sync of codebase to KuzuDB."""
        logger.info("Starting full sync to KuzuDB")
        start_time = time.time()

        try:
            self.conn.execute("BEGIN TRANSACTION")

            # Clear existing data
            self._clear_data()

            # Sync files
            files_synced = self._sync_files()

            # Sync functions
            functions_synced = self._sync_functions()

            # Sync classes
            classes_synced = self._sync_classes()

            # Sync imports
            imports_synced = self._sync_imports()

            # Sync relationships
            relationships_synced = self._sync_relationships()

            self.conn.execute("COMMIT")

            duration = time.time() - start_time
            logger.info(f"Full sync completed in {duration:.2f}s - Files: {files_synced}, "
                       f"Functions: {functions_synced}, Classes: {classes_synced}, "
                       f"Imports: {imports_synced}, Relationships: {relationships_synced}")

        except Exception as e:
            try:
                self.conn.execute("ROLLBACK")
            except Exception:
                pass  # No active transaction
            logger.error(f"Full sync failed: {e}")
            raise

    def sync_file(self, file_path: str):
        """Sync a specific file to KuzuDB."""
        logger.debug(f"Syncing file: {file_path}")

        try:
            self.conn.execute("BEGIN TRANSACTION")

            # Remove existing data for this file
            self._clear_file_data(file_path)

            # Find the file in codebase
            file_obj = None
            for f in self.codebase.files:
                if str(f.filepath) == file_path or f.filepath.endswith(file_path):
                    file_obj = f
                    break

            if not file_obj:
                logger.warning(f"File not found in codebase: {file_path}")
                return

            # Sync the file and its contents
            self._sync_single_file(file_obj)

            self.conn.execute("COMMIT")
            logger.debug(f"Successfully synced file: {file_path}")

        except Exception as e:
            try:
                self.conn.execute("ROLLBACK")
            except Exception:
                pass  # No active transaction
            logger.error(f"Failed to sync file {file_path}: {e}")
            raise

    def _clear_data(self):
        """Clear all existing data from KuzuDB."""
        clear_queries = [
            "MATCH (a)-[r:INHERITS]-(b) DELETE r",
            "MATCH (a)-[r:IMPORTS]-(b) DELETE r",
            "MATCH (a)-[r:FUNCTION_CALLS]-(b) DELETE r",
            "MATCH (a)-[r:CLASS_METHOD]-(b) DELETE r",
            "MATCH (a)-[r:CONTAINS_IMPORT]-(b) DELETE r",
            "MATCH (a)-[r:CONTAINS_CLASS]-(b) DELETE r",
            "MATCH (a)-[r:CONTAINS_FUNCTION]-(b) DELETE r",
            "MATCH (n:Import) DELETE n",
            "MATCH (n:Class) DELETE n",
            "MATCH (n:Function) DELETE n",
            "MATCH (n:File) DELETE n"
        ]

        for query in clear_queries:
            try:
                self.conn.execute(query)
            except Exception as e:
                # Continue if relationship table doesn't exist or is empty
                logger.debug(f"Clear query failed (expected): {e}")

    def _clear_file_data(self, file_path: str):
        """Clear data for a specific file."""
        clear_queries = [
            f"MATCH (f:File {{path: '{file_path}'}})-[r]-() DELETE r",
            f"MATCH (f:Function {{file_path: '{file_path}'}}) DELETE f",
            f"MATCH (c:Class {{file_path: '{file_path}'}}) DELETE c",
            f"MATCH (i:Import {{file_path: '{file_path}'}}) DELETE i",
            f"MATCH (file:File {{path: '{file_path}'}}) DELETE file"
        ]

        for query in clear_queries:
            self.conn.execute(query)

    def _sync_files(self) -> int:
        """Sync all files."""
        count = 0
        for file_obj in self.codebase.files:
            self._sync_single_file(file_obj)
            count += 1
        return count

    def _sync_single_file(self, file_obj):
        """Sync a single file object."""
        timestamp = int(time.time())
        file_path = str(file_obj.filepath)

        # Calculate file hash
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            file_hash = ""

        # Get file stats
        path_obj = Path(file_path)
        size = path_obj.stat().st_size if path_obj.exists() else 0

        # Insert file node
        self.conn.execute(
            """CREATE (f:File {
                path: $path,
                name: $name,
                extension: $ext,
                size: $size,
                hash: $hash,
                language: $lang,
                created_at: $created,
                updated_at: $updated
            })""",
            {
                "path": file_path,
                "name": path_obj.name,
                "ext": path_obj.suffix,
                "size": size,
                "hash": file_hash,
                "lang": file_obj.language.value if hasattr(file_obj, 'language') else "unknown",
                "created": timestamp,
                "updated": timestamp
            }
        )

    def _sync_functions(self) -> int:
        """Sync all functions."""
        count = 0
        for func in self.codebase.functions:
            self._sync_single_function(func)
            count += 1
        return count

    def _sync_single_function(self, func):
        """Sync a single function object."""
        timestamp = int(time.time())

        # Get start/end from range attribute
        start_line = func.range.start_point[0] if hasattr(func, 'range') else 0
        end_line = func.range.end_point[0] if hasattr(func, 'range') else 0
        start_col = func.range.start_point[1] if hasattr(func, 'range') else 0
        end_col = func.range.end_point[1] if hasattr(func, 'range') else 0

        func_id = f"{func.filepath}::{func.name}:{start_line}"

        self.conn.execute(
            """CREATE (f:Function {
                id: $id,
                name: $name,
                qualified_name: $qualified,
                file_path: $path,
                start_line: $start_line,
                end_line: $end_line,
                start_col: $start_col,
                end_col: $end_col,
                is_method: $is_method,
                is_async: $is_async,
                complexity: $complexity,
                params_count: $params_count,
                docstring: $docstring,
                created_at: $created,
                updated_at: $updated
            })""",
            {
                "id": func_id,
                "name": func.name,
                "qualified": getattr(func, 'qualified_name', func.name),
                "path": str(func.filepath),
                "start_line": start_line,
                "end_line": end_line,
                "start_col": start_col,
                "end_col": end_col,
                "is_method": func.is_method,
                "is_async": getattr(func, 'is_async', False),
                "complexity": getattr(func, 'complexity', 1),
                "params_count": len(func.parameters) if hasattr(func, 'parameters') else 0,
                "docstring": str(getattr(func, 'docstring', '')),
                "created": timestamp,
                "updated": timestamp
            }
        )

        # Create CONTAINS_FUNCTION relationship
        self.conn.execute(
            """MATCH (file:File {path: $path}), (func:Function {id: $id})
               CREATE (file)-[:CONTAINS_FUNCTION {created_at: $created}]->(func)""",
            {
                "path": str(func.filepath),
                "id": func_id,
                "created": timestamp
            }
        )

    def _sync_classes(self) -> int:
        """Sync all classes."""
        count = 0
        for cls in self.codebase.classes:
            self._sync_single_class(cls)
            count += 1
        return count

    def _sync_single_class(self, cls):
        """Sync a single class object."""
        timestamp = int(time.time())

        # Get start/end from range attribute
        start_line = cls.range.start_point[0] if hasattr(cls, 'range') else 0
        end_line = cls.range.end_point[0] if hasattr(cls, 'range') else 0

        cls_id = f"{cls.filepath}::{cls.name}:{start_line}"

        self.conn.execute(
            """CREATE (c:Class {
                id: $id,
                name: $name,
                qualified_name: $qualified,
                file_path: $path,
                start_line: $start_line,
                end_line: $end_line,
                is_abstract: $is_abstract,
                methods_count: $methods_count,
                docstring: $docstring,
                created_at: $created,
                updated_at: $updated
            })""",
            {
                "id": cls_id,
                "name": cls.name,
                "qualified": getattr(cls, 'qualified_name', cls.name),
                "path": str(cls.filepath),
                "start_line": start_line,
                "end_line": end_line,
                "is_abstract": getattr(cls, 'is_abstract', False),
                "methods_count": len(cls.methods) if hasattr(cls, 'methods') else 0,
                "docstring": str(getattr(cls, 'docstring', '')),
                "created": timestamp,
                "updated": timestamp
            }
        )

        # Create CONTAINS_CLASS relationship
        self.conn.execute(
            """MATCH (file:File {path: $path}), (cls:Class {id: $id})
               CREATE (file)-[:CONTAINS_CLASS {created_at: $created}]->(cls)""",
            {
                "path": str(cls.filepath),
                "id": cls_id,
                "created": timestamp
            }
        )

    def _sync_imports(self) -> int:
        """Sync all imports."""
        count = 0
        for imp in self.codebase.imports:
            self._sync_single_import(imp)
            count += 1
        return count

    def _sync_single_import(self, imp):
        """Sync a single import object."""
        timestamp = int(time.time())

        # Get line from range attribute
        line_number = imp.range.start_point[0] if hasattr(imp, 'range') else 0

        # Get module name from module attribute
        module_name = str(getattr(imp, 'module', ''))
        imported_name = str(getattr(imp, 'name', ''))
        alias_name = str(getattr(imp, 'alias', ''))

        imp_id = f"{imp.filepath}::{module_name}::{imported_name}:{line_number}"

        self.conn.execute(
            """CREATE (i:Import {
                id: $id,
                module_name: $module,
                imported_name: $imported,
                alias: $alias,
                file_path: $path,
                line_number: $line,
                is_from_import: $is_from,
                created_at: $created,
                updated_at: $updated
            })""",
            {
                "id": imp_id,
                "module": module_name,
                "imported": imported_name,
                "alias": alias_name,
                "path": str(imp.filepath),
                "line": line_number,
                "is_from": hasattr(imp, 'import_statement') and 'from' in str(getattr(imp.import_statement, 'source', '')).lower(),
                "created": timestamp,
                "updated": timestamp
            }
        )

        # Create CONTAINS_IMPORT relationship
        self.conn.execute(
            """MATCH (file:File {path: $path}), (imp:Import {id: $id})
               CREATE (file)-[:CONTAINS_IMPORT {created_at: $created}]->(imp)""",
            {
                "path": str(imp.filepath),
                "id": imp_id,
                "created": timestamp
            }
        )

    def _sync_relationships(self) -> int:
        """Sync function calls and other relationships."""
        count = 0
        timestamp = int(time.time())

        # Sync function calls
        for func in self.codebase.functions:
            if hasattr(func, 'calls') and func.calls:
                func_start_line = func.range.start_point[0] if hasattr(func, 'range') else 0
                for call in func.calls:
                    if hasattr(call, 'resolved_symbol') and call.resolved_symbol:
                        caller_id = f"{func.filepath}::{func.name}:{func_start_line}"
                        callee_start_line = call.resolved_symbol.range.start_point[0] if hasattr(call.resolved_symbol, 'range') else 0
                        callee_id = f"{call.resolved_symbol.filepath}::{call.resolved_symbol.name}:{callee_start_line}"

                        self.conn.execute(
                            """MATCH (caller:Function {id: $caller_id}), (callee:Function {id: $callee_id})
                               CREATE (caller)-[:FUNCTION_CALLS {
                                   line_number: $line,
                                   call_type: $type,
                                   created_at: $created
                               }]->(callee)""",
                            {
                                "caller_id": caller_id,
                                "callee_id": callee_id,
                                "line": call.range.start_point[0] if hasattr(call, 'range') else 0,
                                "type": "direct",
                                "created": timestamp
                            }
                        )
                        count += 1

        # Sync class methods
        for cls in self.codebase.classes:
            if hasattr(cls, 'methods'):
                cls_start_line = cls.range.start_point[0] if hasattr(cls, 'range') else 0
                cls_id = f"{cls.filepath}::{cls.name}:{cls_start_line}"
                for method in cls.methods:
                    method_start_line = method.range.start_point[0] if hasattr(method, 'range') else 0
                    method_id = f"{method.filepath}::{method.name}:{method_start_line}"

                    self.conn.execute(
                        """MATCH (cls:Class {id: $cls_id}), (method:Function {id: $method_id})
                           CREATE (cls)-[:CLASS_METHOD {
                               visibility: $visibility,
                               created_at: $created
                           }]->(method)""",
                        {
                            "cls_id": cls_id,
                            "method_id": method_id,
                            "visibility": getattr(method, 'visibility', 'public'),
                            "created": timestamp
                        }
                    )
                    count += 1

        return count

    def query(self, cypher_query: str, params: Optional[Dict] = None):
        """Execute a Cypher query on the KuzuDB."""
        try:
            result = self.conn.execute(cypher_query, params or {})
            return result
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

    def get_stats(self) -> Dict:
        """Get basic statistics about the synced data."""
        stats = {}

        queries = {
            "files": "MATCH (f:File) RETURN count(f) as count",
            "functions": "MATCH (f:Function) RETURN count(f) as count",
            "classes": "MATCH (c:Class) RETURN count(c) as count",
            "imports": "MATCH (i:Import) RETURN count(i) as count",
            "function_calls": "MATCH ()-[r:FUNCTION_CALLS]-() RETURN count(r) as count"
        }

        for name, query in queries.items():
            try:
                result = self.conn.execute(query)
                stats[name] = result.get_next()[0] if result.has_next() else 0
            except Exception as e:
                logger.error(f"Failed to get {name} count: {e}")
                stats[name] = 0

        return stats

    def close(self):
        """Close the KuzuDB connection."""
        if hasattr(self, 'conn'):
            self.conn.close()
        if hasattr(self, 'db'):
            self.db.close()