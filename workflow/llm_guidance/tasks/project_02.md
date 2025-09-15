Read workflow/llm_guidance/tasks/project_01.md

The project_01 was implemented in @src/graph_sitter/extensions/kuzu_map/

This project aims to map other parts of the schema, completing the base kuzu mapping.

Graph-sitter is installed, you can use it in your advantage. Instructions: read workflow/llm_guidance/graph-tree-system-prompt.txt

# Implementation Guide for Extending Graph-Sitter KuzuDB Mapping

Let me walk you through implementing the remaining graph-sitter types in a systematic way. The goal is to extend the existing KuzuDB integration to capture the complete code structure, including symbols, assignments, interfaces, type aliases, parameters, and code blocks.

## Phase 1: Understanding the Data Model Requirements

Before we dive into implementation, let's understand what each of these types represents in the context of code analysis:

**Symbol** represents any named entity in code - variables, constants, or other identifiers that aren't functions or classes. Think of these as the atomic building blocks of your code's namespace.

**Assignment** captures the relationship between a symbol and its value. This is crucial for data flow analysis and understanding how values propagate through your code.

**Interface** (primarily in TypeScript/Java) defines contracts that classes must implement. These are essential for understanding the type system and architectural patterns.

**TypeAlias** creates alternative names for types, which helps in understanding type relationships and making complex types more readable.

**Parameter** represents function/method parameters with their types and default values. These are key to understanding function signatures and API contracts.

**CodeBlock** represents logical groupings of code - loops, conditionals, try-catch blocks. These help understand control flow and code organization.

## Phase 2: Extending the Database Schema

First, we need to extend the KuzuDB schema in `sync.py`. ADD these node and relationship definitions to the `_init_schema` method:

```python    
    node_schemas = [
        # Symbol captures all named entities (variables, constants, etc.)
        """CREATE NODE TABLE IF NOT EXISTS Symbol(
            id STRING PRIMARY KEY,
            name STRING,
            kind STRING,  # 'variable', 'constant', 'field', 'property'
            scope STRING,  # 'global', 'module', 'class', 'function', 'block'
            file_path STRING,
            parent_id STRING,  # ID of containing function/class/block
            start_line INT64,
            end_line INT64,
            is_exported BOOLEAN,
            is_mutable BOOLEAN,
            type_annotation STRING,
            created_at INT64,
            updated_at INT64
        )""",
        
        # Assignment tracks value assignments to symbols
        """CREATE NODE TABLE IF NOT EXISTS Assignment(
            id STRING PRIMARY KEY,
            target_symbol_id STRING,
            value_type STRING,  # 'literal', 'expression', 'function_call', 'object'
            value_representation STRING,  # Simplified string representation
            file_path STRING,
            line_number INT64,
            is_initialization BOOLEAN,
            created_at INT64,
            updated_at INT64
        )""",
        
        # Interface for TypeScript/Java interface definitions
        """CREATE NODE TABLE IF NOT EXISTS Interface(
            id STRING PRIMARY KEY,
            name STRING,
            qualified_name STRING,
            file_path STRING,
            start_line INT64,
            end_line INT64,
            is_exported BOOLEAN,
            extends_interfaces STRING,  # JSON array of interface names
            docstring STRING,
            created_at INT64,
            updated_at INT64
        )""",
        
        # TypeAlias for type definitions
        """CREATE NODE TABLE IF NOT EXISTS TypeAlias(
            id STRING PRIMARY KEY,
            name STRING,
            target_type STRING,
            file_path STRING,
            line_number INT64,
            is_exported BOOLEAN,
            type_parameters STRING,  # Generic type parameters if any
            created_at INT64,
            updated_at INT64
        )""",
        
        # Parameter for function/method parameters
        """CREATE NODE TABLE IF NOT EXISTS Parameter(
            id STRING PRIMARY KEY,
            name STRING,
            function_id STRING,
            position INT64,
            type_annotation STRING,
            default_value STRING,
            is_optional BOOLEAN,
            is_rest BOOLEAN,  # For *args, **kwargs, ...rest
            is_keyword_only BOOLEAN,
            created_at INT64,
            updated_at INT64
        )""",
        
        # CodeBlock for logical code groupings
        """CREATE NODE TABLE IF NOT EXISTS CodeBlock(
            id STRING PRIMARY KEY,
            block_type STRING,  # 'if', 'else', 'elif', 'for', 'while', 'try', 'catch', 'finally', 'with'
            parent_id STRING,  # ID of containing function/class/block
            file_path STRING,
            start_line INT64,
            end_line INT64,
            condition STRING,  # For conditionals/loops
            complexity_contribution INT64,
            created_at INT64,
            updated_at INT64
        )"""
    ]
    
    relationship_schemas = [
        # Symbol relationships
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
        
        # Assignment relationships
        """CREATE REL TABLE IF NOT EXISTS ASSIGNS_TO(
            FROM Assignment TO Symbol,
            assignment_operator STRING,  # '=', '+=', '-=', etc.
            created_at INT64
        )""",
        
        """CREATE REL TABLE IF NOT EXISTS ASSIGNMENT_IN_FUNCTION(
            FROM Function TO Assignment,
            created_at INT64
        )""",
        
        # Interface relationships
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
        
        # Type relationships
        """CREATE REL TABLE IF NOT EXISTS USES_TYPE(
            FROM Symbol TO TypeAlias,
            usage_context STRING,
            created_at INT64
        )""",
        
        # Parameter relationships
        """CREATE REL TABLE IF NOT EXISTS HAS_PARAMETER(
            FROM Function TO Parameter,
            created_at INT64
        )""",
        
        # CodeBlock relationships
        """CREATE REL TABLE IF NOT EXISTS CONTAINS_BLOCK(
            FROM Function TO CodeBlock,
            nesting_level INT64,
            created_at INT64
        )""",
        
        """CREATE REL TABLE IF NOT EXISTS NESTED_BLOCK(
            FROM CodeBlock TO CodeBlock,
            relationship_type STRING,  # 'parent_child', 'if_else', 'try_catch'
            created_at INT64
        )"""
    ]
    
    # Execute all extended schemas
    for query in node_schemas + relationship_schemas:
        try:
            self.conn.execute(query)
            logger.debug(f"Schema created successfully")
        except Exception as e:
            logger.error(f"Failed to create schema: {e}")
            raise
```

## Phase 3: Implementing Data Extraction Logic

Now we need to implement the extraction logic for each type. This involves parsing the AST (Abstract Syntax Tree) nodes from graph-sitter and mapping them to our schema:

```python
def _extract_symbols(self, file_obj) -> List[Dict]:
    """Extract symbol declarations from a file."""
    symbols = []
    
    # Navigate the AST to find variable/constant declarations
    for node in file_obj.ast_nodes:  # Assuming graph-sitter provides AST access
        if node.type in ['variable_declaration', 'const_declaration', 'let_declaration']:
            symbol_data = {
                'name': node.name,
                'kind': self._determine_symbol_kind(node),
                'scope': self._determine_scope(node),
                'file_path': str(file_obj.filepath),
                'parent_id': self._get_parent_id(node),
                'start_line': node.range.start_point[0],
                'end_line': node.range.end_point[0],
                'is_exported': self._is_exported(node),
                'is_mutable': node.type != 'const_declaration',
                'type_annotation': self._extract_type_annotation(node)
            }
            symbols.append(symbol_data)
    
    return symbols

def _extract_assignments(self, file_obj) -> List[Dict]:
    """Extract assignment operations from a file."""
    assignments = []
    
    for node in file_obj.ast_nodes:
        if node.type in ['assignment_expression', 'augmented_assignment_expression']:
            assignment_data = {
                'target_symbol': self._resolve_assignment_target(node),
                'value_type': self._determine_value_type(node.right),
                'value_representation': self._safe_value_representation(node.right),
                'file_path': str(file_obj.filepath),
                'line_number': node.range.start_point[0],
                'is_initialization': self._is_initialization(node)
            }
            assignments.append(assignment_data)
    
    return assignments

def _extract_parameters(self, func_obj) -> List[Dict]:
    """Extract detailed parameter information from a function."""
    parameters = []
    
    if hasattr(func_obj, 'parameters'):
        for idx, param in enumerate(func_obj.parameters):
            param_data = {
                'name': param.name,
                'function_id': self._generate_function_id(func_obj),
                'position': idx,
                'type_annotation': getattr(param, 'type_annotation', ''),
                'default_value': self._extract_default_value(param),
                'is_optional': hasattr(param, 'default_value'),
                'is_rest': self._is_rest_parameter(param),
                'is_keyword_only': self._is_keyword_only(param, idx, func_obj)
            }
            parameters.append(param_data)
    
    return parameters

def _extract_code_blocks(self, func_obj) -> List[Dict]:
    """Extract code blocks (control structures) from a function."""
    blocks = []
    
    def traverse_blocks(node, parent_id=None, nesting_level=0):
        """Recursively traverse and extract code blocks."""
        if node.type in ['if_statement', 'for_statement', 'while_statement', 
                         'try_statement', 'with_statement']:
            block_id = self._generate_block_id(node, func_obj)
            block_data = {
                'id': block_id,
                'block_type': self._normalize_block_type(node.type),
                'parent_id': parent_id or self._generate_function_id(func_obj),
                'file_path': str(func_obj.filepath),
                'start_line': node.range.start_point[0],
                'end_line': node.range.end_point[0],
                'condition': self._extract_condition(node),
                'complexity_contribution': self._calculate_block_complexity(node),
                'nesting_level': nesting_level
            }
            blocks.append(block_data)
            
            # Recursively process nested blocks
            for child in node.children:
                traverse_blocks(child, block_id, nesting_level + 1)
    
    # Start traversal from function body
    if hasattr(func_obj, 'body'):
        traverse_blocks(func_obj.body)
    
    return blocks
```

## Phase 4: Implementing Synchronization Methods

Now we need to ADD methods to sync these new types to KuzuDB:

```python
def _sync_types(self):
    """Synchronize type information to KuzuDB."""
    
    symbols_synced = 0
    assignments_synced = 0
    interfaces_synced = 0
    type_aliases_synced = 0
    parameters_synced = 0
    code_blocks_synced = 0
    
    for file_obj in self.codebase.files:
        # Extract and sync symbols
        symbols = self._extract_symbols(file_obj)
        for symbol in symbols:
            self._sync_symbol(symbol)
            symbols_synced += 1
        
        # Extract and sync assignments
        assignments = self._extract_assignments(file_obj)
        for assignment in assignments:
            self._sync_assignment(assignment)
            assignments_synced += 1
        
        # For TypeScript/Java files, extract interfaces and type aliases
        if file_obj.language in ['typescript', 'java']:
            interfaces = self._extract_interfaces(file_obj)
            for interface in interfaces:
                self._sync_interface(interface)
                interfaces_synced += 1
            
            type_aliases = self._extract_type_aliases(file_obj)
            for type_alias in type_aliases:
                self._sync_type_alias(type_alias)
                type_aliases_synced += 1
    
    # Sync parameters for all functions
    for func_obj in self.codebase.functions:
        parameters = self._extract_parameters(func_obj)
        for param in parameters:
            self._sync_parameter(param)
            parameters_synced += 1
        
        # Sync code blocks within functions
        code_blocks = self._extract_code_blocks(func_obj)
        for block in code_blocks:
            self._sync_code_block(block)
            code_blocks_synced += 1
    
    logger.info(f"Sync complete - Symbols: {symbols_synced}, "
                f"Assignments: {assignments_synced}, Interfaces: {interfaces_synced}, "
                f"TypeAliases: {type_aliases_synced}, Parameters: {parameters_synced}, "
                f"CodeBlocks: {code_blocks_synced}")
    
    return {
        'symbols': symbols_synced,
        'assignments': assignments_synced,
        'interfaces': interfaces_synced,
        'type_aliases': type_aliases_synced,
        'parameters': parameters_synced,
        'code_blocks': code_blocks_synced
    }
```

## Phase 5: Creating Analysis Queries

Finally, we need to ADD analysis capabilities that leverage these new types:

```python
class CodeGraphAnalyzer:
    """analyzer with support for new type analysis."""
    
    def find_unused_variables(self):
        """Find declared symbols that are never assigned or used."""
        query = """
        MATCH (s:Symbol)
        WHERE NOT exists {
            MATCH ()-[:ASSIGNS_TO]->(s)
        }
        AND NOT exists {
            MATCH (s)-[:USES_TYPE]->()
        }
        AND s.kind = 'variable'
        RETURN s.name, s.file_path, s.start_line, s.scope
        ORDER BY s.file_path, s.start_line
        """
        return self.kuzu_sync.query(query)
    
    def analyze_parameter_complexity(self, threshold: int = 5):
        """Find functions with too many parameters."""
        query = """
        MATCH (f:Function)-[:HAS_PARAMETER]->(p:Parameter)
        WITH f, count(p) as param_count
        WHERE param_count > $threshold
        RETURN f.name, f.file_path, param_count
        ORDER BY param_count DESC
        """
        return self.kuzu_sync.query(query, {"threshold": threshold})
    
    def find_deeply_nested_blocks(self, max_depth: int = 3):
        """Find code blocks nested beyond a certain depth."""
        query = """
        MATCH path = (f:Function)-[:CONTAINS_BLOCK]->(b1:CodeBlock)
                     -[:NESTED_BLOCK*1..]->(b2:CodeBlock)
        WHERE length(path) > $max_depth
        RETURN f.name, f.file_path, b2.start_line, 
               length(path) as nesting_depth, b2.block_type
        ORDER BY nesting_depth DESC
        """
        return self.kuzu_sync.query(query, {"max_depth": max_depth})
    
    def analyze_type_usage(self):
        """Analyze which type aliases are most commonly used."""
        query = """
        MATCH (s:Symbol)-[:USES_TYPE]->(t:TypeAlias)
        WITH t, count(s) as usage_count
        RETURN t.name, t.target_type, usage_count, t.file_path
        ORDER BY usage_count DESC
        """
        return self.kuzu_sync.query(query)
    
    def find_interface_violations(self):
        """Find classes that don't fully implement their interfaces."""
        query = """
        MATCH (c:Class)-[:IMPLEMENTS]->(i:Interface)
        MATCH (i)-[:INTERFACE_METHOD]->(required_method:Function)
        WHERE NOT exists {
            MATCH (c)-[:CLASS_METHOD]->(m:Function)
            WHERE m.name = required_method.name
        }
        RETURN c.name, i.name, required_method.name as missing_method
        ORDER BY c.name, i.name
        """
        return self.kuzu_sync.query(query)
```

## Phase 6: Integration and Testing Strategy

To ensure everything works correctly, follow this testing approach:

1. **Start with a small test file** containing examples of each type you're mapping
2. **Verify the AST structure** from graph-sitter matches your expectations
3. **Test each extraction method individually** before running full sync
4. **Check the database contents** after each sync to ensure data integrity
5. **Run analysis queries** to validate relationships are correctly established

Remember that graph-sitter's AST structure might vary between languages, so you'll need to handle language-specific variations in your extraction logic. The key is to maintain a consistent schema while adapting the extraction logic to each language's peculiarities.

This implementation gives you a comprehensive code analysis system that can track not just the structure but also the data flow and type relationships in your codebase. The combination of these elements enables powerful queries for code quality analysis, refactoring opportunities, and architectural insights.


read @.claude/commands/🧠.md