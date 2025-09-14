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
            )""",

            # New entity tables from project_02
            """CREATE NODE TABLE IF NOT EXISTS Symbol(
                id STRING PRIMARY KEY,
                name STRING,
                kind STRING,
                scope STRING,
                file_path STRING,
                parent_id STRING,
                start_line INT64,
                end_line INT64,
                is_exported BOOLEAN,
                is_mutable BOOLEAN,
                type_annotation STRING,
                created_at INT64,
                updated_at INT64
            )""",

            """CREATE NODE TABLE IF NOT EXISTS Assignment(
                id STRING PRIMARY KEY,
                target_symbol_id STRING,
                value_type STRING,
                value_representation STRING,
                file_path STRING,
                line_number INT64,
                is_initialization BOOLEAN,
                created_at INT64,
                updated_at INT64
            )""",

            """CREATE NODE TABLE IF NOT EXISTS Interface(
                id STRING PRIMARY KEY,
                name STRING,
                qualified_name STRING,
                file_path STRING,
                start_line INT64,
                end_line INT64,
                is_exported BOOLEAN,
                extends_interfaces STRING,
                docstring STRING,
                created_at INT64,
                updated_at INT64
            )""",

            """CREATE NODE TABLE IF NOT EXISTS TypeAlias(
                id STRING PRIMARY KEY,
                name STRING,
                target_type STRING,
                file_path STRING,
                line_number INT64,
                is_exported BOOLEAN,
                type_parameters STRING,
                created_at INT64,
                updated_at INT64
            )""",

            """CREATE NODE TABLE IF NOT EXISTS Parameter(
                id STRING PRIMARY KEY,
                name STRING,
                function_id STRING,
                position INT64,
                type_annotation STRING,
                default_value STRING,
                is_optional BOOLEAN,
                is_rest BOOLEAN,
                is_keyword_only BOOLEAN,
                created_at INT64,
                updated_at INT64
            )""",

            """CREATE NODE TABLE IF NOT EXISTS CodeBlock(
                id STRING PRIMARY KEY,
                block_type STRING,
                parent_id STRING,
                file_path STRING,
                start_line INT64,
                end_line INT64,
                condition STRING,
                complexity_contribution INT64,
                created_at INT64,
                updated_at INT64
            )""",

            # New relationship tables
            """CREATE REL TABLE IF NOT EXISTS DECLARES_SYMBOL(
                FROM Function TO Symbol,
                declaration_type STRING,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS CLASS_FIELD(
                FROM Class TO Symbol,
                visibility STRING,
                is_static BOOLEAN,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS ASSIGNS_TO(
                FROM Assignment TO Symbol,
                assignment_operator STRING,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS ASSIGNMENT_IN_FUNCTION(
                FROM Function TO Assignment,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS IMPLEMENTS(
                FROM Class TO Interface,
                is_partial BOOLEAN,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS INTERFACE_METHOD(
                FROM Interface TO Function,
                is_optional BOOLEAN,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS USES_TYPE(
                FROM Symbol TO TypeAlias,
                usage_context STRING,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS HAS_PARAMETER(
                FROM Function TO Parameter,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS CONTAINS_BLOCK(
                FROM Function TO CodeBlock,
                nesting_level INT64,
                created_at INT64
            )""",

            """CREATE REL TABLE IF NOT EXISTS NESTED_BLOCK(
                FROM CodeBlock TO CodeBlock,
                relationship_type STRING,
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

            # Sync new entities from project_02
            symbols_synced = self._sync_symbols()
            assignments_synced = self._sync_assignments()
            interfaces_synced = self._sync_interfaces()
            type_aliases_synced = self._sync_type_aliases()
            parameters_synced = self._sync_parameters()
            code_blocks_synced = self._sync_code_blocks()

            # Sync relationships
            relationships_synced = self._sync_relationships()

            self.conn.execute("COMMIT")

            duration = time.time() - start_time
            logger.info(f"Full sync completed in {duration:.2f}s - Files: {files_synced}, "
                       f"Functions: {functions_synced}, Classes: {classes_synced}, "
                       f"Imports: {imports_synced}, Symbols: {symbols_synced}, "
                       f"Assignments: {assignments_synced}, Interfaces: {interfaces_synced}, "
                       f"TypeAliases: {type_aliases_synced}, Parameters: {parameters_synced}, "
                       f"CodeBlocks: {code_blocks_synced}, Relationships: {relationships_synced}")

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
            # Clear relationships first
            "MATCH (a)-[r:INHERITS]-(b) DELETE r",
            "MATCH (a)-[r:IMPORTS]-(b) DELETE r",
            "MATCH (a)-[r:FUNCTION_CALLS]-(b) DELETE r",
            "MATCH (a)-[r:CLASS_METHOD]-(b) DELETE r",
            "MATCH (a)-[r:CONTAINS_IMPORT]-(b) DELETE r",
            "MATCH (a)-[r:CONTAINS_CLASS]-(b) DELETE r",
            "MATCH (a)-[r:CONTAINS_FUNCTION]-(b) DELETE r",
            # Clear new relationships
            "MATCH (a)-[r:DECLARES_SYMBOL]-(b) DELETE r",
            "MATCH (a)-[r:CLASS_FIELD]-(b) DELETE r",
            "MATCH (a)-[r:ASSIGNS_TO]-(b) DELETE r",
            "MATCH (a)-[r:ASSIGNMENT_IN_FUNCTION]-(b) DELETE r",
            "MATCH (a)-[r:IMPLEMENTS]-(b) DELETE r",
            "MATCH (a)-[r:INTERFACE_METHOD]-(b) DELETE r",
            "MATCH (a)-[r:USES_TYPE]-(b) DELETE r",
            "MATCH (a)-[r:HAS_PARAMETER]-(b) DELETE r",
            "MATCH (a)-[r:CONTAINS_BLOCK]-(b) DELETE r",
            "MATCH (a)-[r:NESTED_BLOCK]-(b) DELETE r",
            # Clear nodes
            "MATCH (n:Import) DELETE n",
            "MATCH (n:Class) DELETE n",
            "MATCH (n:Function) DELETE n",
            "MATCH (n:File) DELETE n",
            # Clear new nodes
            "MATCH (n:Symbol) DELETE n",
            "MATCH (n:Assignment) DELETE n",
            "MATCH (n:Interface) DELETE n",
            "MATCH (n:TypeAlias) DELETE n",
            "MATCH (n:Parameter) DELETE n",
            "MATCH (n:CodeBlock) DELETE n"
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

    # New sync methods for project_02 entities

    def _sync_symbols(self) -> int:
        """Sync all symbols (variables, constants, fields, etc.)."""
        count = 0
        for file_obj in self.codebase.files:
            symbols = self._extract_symbols(file_obj)
            for symbol in symbols:
                self._sync_single_symbol(symbol)
                count += 1
        return count

    def _sync_assignments(self) -> int:
        """Sync all assignment operations."""
        count = 0
        for file_obj in self.codebase.files:
            assignments = self._extract_assignments(file_obj)
            for assignment in assignments:
                self._sync_single_assignment(assignment)
                count += 1
        return count

    def _sync_interfaces(self) -> int:
        """Sync interface definitions (TypeScript/Java)."""
        count = 0
        for file_obj in self.codebase.files:
            if hasattr(file_obj, 'language') and file_obj.language.value in ['typescript', 'java']:
                interfaces = self._extract_interfaces(file_obj)
                for interface in interfaces:
                    self._sync_single_interface(interface)
                    count += 1
        return count

    def _sync_type_aliases(self) -> int:
        """Sync type alias definitions."""
        count = 0
        for file_obj in self.codebase.files:
            if hasattr(file_obj, 'language') and file_obj.language.value in ['typescript', 'java']:
                type_aliases = self._extract_type_aliases(file_obj)
                for type_alias in type_aliases:
                    self._sync_single_type_alias(type_alias)
                    count += 1
        return count

    def _sync_parameters(self) -> int:
        """Sync function parameters with detailed information."""
        count = 0
        for func in self.codebase.functions:
            parameters = self._extract_parameters(func)
            for param in parameters:
                self._sync_single_parameter(param)
                count += 1
        return count

    def _sync_code_blocks(self) -> int:
        """Sync code blocks (control structures) within functions."""
        count = 0
        for func in self.codebase.functions:
            code_blocks = self._extract_code_blocks(func)
            for block in code_blocks:
                self._sync_single_code_block(block)
                count += 1
        return count

    # Extraction methods for new entities

    def _extract_symbols(self, file_obj) -> List[Dict]:
        """Extract symbol declarations from a file."""
        symbols = []
        timestamp = int(time.time())
        file_path = str(file_obj.filepath)

        # Extract class fields/attributes
        for cls in self.codebase.classes:
            if str(cls.filepath) == file_path:
                if hasattr(cls, 'fields'):
                    for field in cls.fields:
                        symbol_id = f"{file_path}::symbol::{field.name}:{cls.name}"
                        symbols.append({
                            'id': symbol_id,
                            'name': field.name,
                            'kind': 'field',
                            'scope': 'class',
                            'file_path': file_path,
                            'parent_id': f"{cls.filepath}::{cls.name}:{cls.range.start_point[0] if hasattr(cls, 'range') else 0}",
                            'start_line': field.range.start_point[0] if hasattr(field, 'range') else 0,
                            'end_line': field.range.end_point[0] if hasattr(field, 'range') else 0,
                            'is_exported': getattr(field, 'is_exported', False),
                            'is_mutable': getattr(field, 'is_mutable', True),
                            'type_annotation': str(getattr(field, 'type_annotation', '')),
                            'created_at': timestamp,
                            'updated_at': timestamp
                        })

        # Extract function-level variables (simplified approach)
        for func in self.codebase.functions:
            if str(func.filepath) == file_path:
                # For now, we'll extract from parameters as symbols
                if hasattr(func, 'parameters'):
                    for param in func.parameters:
                        symbol_id = f"{file_path}::symbol::{param.name}:{func.name}"
                        symbols.append({
                            'id': symbol_id,
                            'name': param.name,
                            'kind': 'parameter',
                            'scope': 'function',
                            'file_path': file_path,
                            'parent_id': f"{func.filepath}::{func.name}:{func.range.start_point[0] if hasattr(func, 'range') else 0}",
                            'start_line': func.range.start_point[0] if hasattr(func, 'range') else 0,
                            'end_line': func.range.start_point[0] if hasattr(func, 'range') else 0,
                            'is_exported': False,
                            'is_mutable': True,
                            'type_annotation': str(getattr(param, 'type_annotation', '')),
                            'created_at': timestamp,
                            'updated_at': timestamp
                        })

        return symbols

    def _extract_assignments(self, file_obj) -> List[Dict]:
        """Extract assignment operations from a file."""
        assignments = []
        timestamp = int(time.time())
        file_path = str(file_obj.filepath)

        # This is a simplified extraction - in practice would need AST parsing
        # For now, we'll create assignments based on function parameters as initialization
        for func in self.codebase.functions:
            if str(func.filepath) == file_path and hasattr(func, 'parameters'):
                for param in func.parameters:
                    if hasattr(param, 'default_value') and param.default_value:
                        assignment_id = f"{file_path}::assignment::{param.name}:{func.range.start_point[0] if hasattr(func, 'range') else 0}"
                        assignments.append({
                            'id': assignment_id,
                            'target_symbol_id': f"{file_path}::symbol::{param.name}:{func.name}",
                            'value_type': 'default_value',
                            'value_representation': str(param.default_value),
                            'file_path': file_path,
                            'line_number': func.range.start_point[0] if hasattr(func, 'range') else 0,
                            'is_initialization': True,
                            'created_at': timestamp,
                            'updated_at': timestamp
                        })

        return assignments

    def _extract_interfaces(self, file_obj) -> List[Dict]:
        """Extract interface definitions (TypeScript/Java specific)."""
        interfaces = []
        timestamp = int(time.time())
        file_path = str(file_obj.filepath)

        # For now, return empty list as graph-sitter doesn't expose interfaces directly
        # In a full implementation, this would parse AST nodes for interface definitions
        return interfaces

    def _extract_type_aliases(self, file_obj) -> List[Dict]:
        """Extract type alias definitions."""
        type_aliases = []
        timestamp = int(time.time())
        file_path = str(file_obj.filepath)

        # For now, return empty list as graph-sitter doesn't expose type aliases directly
        # In a full implementation, this would parse AST nodes for type definitions
        return type_aliases

    def _extract_parameters(self, func_obj) -> List[Dict]:
        """Extract detailed parameter information from a function."""
        parameters = []
        timestamp = int(time.time())

        if hasattr(func_obj, 'parameters') and func_obj.parameters:
            for idx, param in enumerate(func_obj.parameters):
                param_id = f"{func_obj.filepath}::param::{param.name}:{func_obj.name}:{idx}"
                func_id = f"{func_obj.filepath}::{func_obj.name}:{func_obj.range.start_point[0] if hasattr(func_obj, 'range') else 0}"

                parameters.append({
                    'id': param_id,
                    'name': param.name,
                    'function_id': func_id,
                    'position': idx,
                    'type_annotation': str(getattr(param, 'type_annotation', '')),
                    'default_value': str(getattr(param, 'default_value', '')),
                    'is_optional': hasattr(param, 'default_value') and param.default_value is not None,
                    'is_rest': getattr(param, 'is_rest', False),
                    'is_keyword_only': getattr(param, 'is_keyword_only', False),
                    'created_at': timestamp,
                    'updated_at': timestamp
                })

        return parameters

    def _extract_code_blocks(self, func_obj) -> List[Dict]:
        """Extract code blocks (control structures) from a function."""
        code_blocks = []
        timestamp = int(time.time())

        # This is a simplified implementation
        # In practice, would need to traverse the AST to find control structures
        # For now, we'll estimate complexity as a proxy for code blocks
        if hasattr(func_obj, 'complexity') and func_obj.complexity > 1:
            # Create a single "complex" block for functions with high complexity
            block_id = f"{func_obj.filepath}::block::complex:{func_obj.name}"
            func_id = f"{func_obj.filepath}::{func_obj.name}:{func_obj.range.start_point[0] if hasattr(func_obj, 'range') else 0}"

            code_blocks.append({
                'id': block_id,
                'block_type': 'complex',
                'parent_id': func_id,
                'file_path': str(func_obj.filepath),
                'start_line': func_obj.range.start_point[0] if hasattr(func_obj, 'range') else 0,
                'end_line': func_obj.range.end_point[0] if hasattr(func_obj, 'range') else 0,
                'condition': '',
                'complexity_contribution': func_obj.complexity - 1,
                'created_at': timestamp,
                'updated_at': timestamp
            })

        return code_blocks

    # Individual sync methods for new entities

    def _sync_single_symbol(self, symbol_data: Dict):
        """Sync a single symbol to KuzuDB."""
        self.conn.execute(
            """CREATE (s:Symbol {
                id: $id,
                name: $name,
                kind: $kind,
                scope: $scope,
                file_path: $file_path,
                parent_id: $parent_id,
                start_line: $start_line,
                end_line: $end_line,
                is_exported: $is_exported,
                is_mutable: $is_mutable,
                type_annotation: $type_annotation,
                created_at: $created_at,
                updated_at: $updated_at
            })""",
            symbol_data
        )

    def _sync_single_assignment(self, assignment_data: Dict):
        """Sync a single assignment to KuzuDB."""
        self.conn.execute(
            """CREATE (a:Assignment {
                id: $id,
                target_symbol_id: $target_symbol_id,
                value_type: $value_type,
                value_representation: $value_representation,
                file_path: $file_path,
                line_number: $line_number,
                is_initialization: $is_initialization,
                created_at: $created_at,
                updated_at: $updated_at
            })""",
            assignment_data
        )

    def _sync_single_interface(self, interface_data: Dict):
        """Sync a single interface to KuzuDB."""
        self.conn.execute(
            """CREATE (i:Interface {
                id: $id,
                name: $name,
                qualified_name: $qualified_name,
                file_path: $file_path,
                start_line: $start_line,
                end_line: $end_line,
                is_exported: $is_exported,
                extends_interfaces: $extends_interfaces,
                docstring: $docstring,
                created_at: $created_at,
                updated_at: $updated_at
            })""",
            interface_data
        )

    def _sync_single_type_alias(self, type_alias_data: Dict):
        """Sync a single type alias to KuzuDB."""
        self.conn.execute(
            """CREATE (t:TypeAlias {
                id: $id,
                name: $name,
                target_type: $target_type,
                file_path: $file_path,
                line_number: $line_number,
                is_exported: $is_exported,
                type_parameters: $type_parameters,
                created_at: $created_at,
                updated_at: $updated_at
            })""",
            type_alias_data
        )

    def _sync_single_parameter(self, param_data: Dict):
        """Sync a single parameter to KuzuDB."""
        timestamp = int(time.time())

        self.conn.execute(
            """CREATE (p:Parameter {
                id: $id,
                name: $name,
                function_id: $function_id,
                position: $position,
                type_annotation: $type_annotation,
                default_value: $default_value,
                is_optional: $is_optional,
                is_rest: $is_rest,
                is_keyword_only: $is_keyword_only,
                created_at: $created_at,
                updated_at: $updated_at
            })""",
            param_data
        )

        # Create HAS_PARAMETER relationship
        self.conn.execute(
            """MATCH (f:Function {id: $function_id}), (p:Parameter {id: $param_id})
               CREATE (f)-[:HAS_PARAMETER {created_at: $created}]->(p)""",
            {
                "function_id": param_data['function_id'],
                "param_id": param_data['id'],
                "created": timestamp
            }
        )

    def _sync_single_code_block(self, block_data: Dict):
        """Sync a single code block to KuzuDB."""
        timestamp = int(time.time())

        self.conn.execute(
            """CREATE (b:CodeBlock {
                id: $id,
                block_type: $block_type,
                parent_id: $parent_id,
                file_path: $file_path,
                start_line: $start_line,
                end_line: $end_line,
                condition: $condition,
                complexity_contribution: $complexity_contribution,
                created_at: $created_at,
                updated_at: $updated_at
            })""",
            block_data
        )

        # Create CONTAINS_BLOCK relationship
        self.conn.execute(
            """MATCH (f:Function {id: $parent_id}), (b:CodeBlock {id: $block_id})
               CREATE (f)-[:CONTAINS_BLOCK {nesting_level: 1, created_at: $created}]->(b)""",
            {
                "parent_id": block_data['parent_id'],
                "block_id": block_data['id'],
                "created": timestamp
            }
        )

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