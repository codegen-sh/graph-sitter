# Project 04.03: Schema-Reality Consistency Fix

## Sub-Task Overview

**Parent Project**: Project 04 - MCP Self-Inspection Implementation Fixes
**Priority**: 🟡 MEDIUM PRIORITY - Affects query functionality and analysis completeness
**Complexity**: 🟡 MEDIUM - Requires schema analysis and code alignment

## Problem Definition

### Current Schema-Code Mismatch

**Issue**: Code references entities that don't exist in the current database schema, causing query failures and incomplete analysis.

**Referenced but Missing Entities**:
- `Symbol` - Variable/constant declarations
- `Assignment` - Value assignments to symbols
- `Interface` - TypeScript/Java interface definitions
- `TypeAlias` - Type definitions and aliases
- `Parameter` - Function parameter details
- `CodeBlock` - Control flow structures (if, for, while, try, etc.)

**Evidence from Code**:
```python
# In analysis queries - these will fail if tables don't exist
"MATCH (s:Symbol) WHERE s.kind = 'variable'"
"MATCH (a:Assignment)-[:ASSIGNS_TO]->(s:Symbol)"
"MATCH (i:Interface)-[:INTERFACE_METHOD]->(f:Function)"
"MATCH (t:TypeAlias) WHERE t.name = $typename"
"MATCH (f:Function)-[:HAS_PARAMETER]->(p:Parameter)"
"MATCH (b:CodeBlock) WHERE b.block_type = 'if'"
```

### Current Schema State Analysis

**Existing Schema** (from Projects 01-03):
```sql
-- Core entities (implemented)
CREATE NODE TABLE File(path STRING PRIMARY KEY, language STRING, loc INT64, ...)
CREATE NODE TABLE Function(id STRING PRIMARY KEY, name STRING, complexity INT64, ...)
CREATE NODE TABLE Class(id STRING PRIMARY KEY, name STRING, ...)
CREATE NODE TABLE Import(id STRING PRIMARY KEY, module_name STRING, ...)

-- Relationships (implemented)
CREATE REL TABLE CONTAINS(FROM File TO Function)
CREATE REL TABLE CALLS(FROM Function TO Function)
CREATE REL TABLE INHERITS(FROM Class TO Class)
```

**Missing Schema** (referenced in code):
- Symbol, Assignment, Interface, TypeAlias, Parameter, CodeBlock node tables
- Related relationship tables for these entities

## Technical Solution Strategy

### Option 1: Implement Complete Schema (Recommended)

**Rationale**: Provides full functionality as originally designed and enables advanced analysis capabilities.

**Implementation**: Add missing schema elements to match Project 01/02 specifications.

### Option 2: Remove References (Not Recommended)

**Rationale**: Would reduce functionality and make analysis tools less capable.

**Implementation**: Remove all references to missing entities and simplify analysis tools.

**Conclusion**: We choose Option 1 to maintain full functionality.

## Complete Schema Implementation

### Extended Node Tables

**1. Symbol Table**
```sql
CREATE NODE TABLE Symbol(
    id STRING PRIMARY KEY,
    name STRING,
    kind STRING,                -- 'variable', 'constant', 'field', 'property'
    scope STRING,               -- 'global', 'module', 'class', 'function', 'block'
    file_path STRING,
    parent_id STRING,           -- ID of containing function/class/block
    start_line INT64,
    end_line INT64,
    is_exported BOOLEAN,
    is_mutable BOOLEAN,
    type_annotation STRING,
    created_at INT64,
    updated_at INT64
)
```

**2. Assignment Table**
```sql
CREATE NODE TABLE Assignment(
    id STRING PRIMARY KEY,
    target_symbol_id STRING,
    value_type STRING,          -- 'literal', 'expression', 'function_call', 'object'
    value_representation STRING, -- Simplified string representation
    file_path STRING,
    line_number INT64,
    is_initialization BOOLEAN,
    created_at INT64,
    updated_at INT64
)
```

**3. Interface Table**
```sql
CREATE NODE TABLE Interface(
    id STRING PRIMARY KEY,
    name STRING,
    qualified_name STRING,
    file_path STRING,
    start_line INT64,
    end_line INT64,
    is_exported BOOLEAN,
    extends_interfaces STRING,   -- JSON array of interface names
    docstring STRING,
    created_at INT64,
    updated_at INT64
)
```

**4. TypeAlias Table**
```sql
CREATE NODE TABLE TypeAlias(
    id STRING PRIMARY KEY,
    name STRING,
    target_type STRING,
    file_path STRING,
    line_number INT64,
    is_exported BOOLEAN,
    type_parameters STRING,     -- Generic type parameters if any
    created_at INT64,
    updated_at INT64
)
```

**5. Parameter Table**
```sql
CREATE NODE TABLE Parameter(
    id STRING PRIMARY KEY,
    name STRING,
    function_id STRING,
    position INT64,
    type_annotation STRING,
    default_value STRING,
    is_optional BOOLEAN,
    is_rest BOOLEAN,            -- For *args, **kwargs, ...rest
    is_keyword_only BOOLEAN,
    created_at INT64,
    updated_at INT64
)
```

**6. CodeBlock Table**
```sql
CREATE NODE TABLE CodeBlock(
    id STRING PRIMARY KEY,
    block_type STRING,          -- 'if', 'else', 'elif', 'for', 'while', 'try', 'catch', 'finally', 'with'
    parent_id STRING,           -- ID of containing function/class/block
    file_path STRING,
    start_line INT64,
    end_line INT64,
    condition STRING,           -- For conditionals/loops
    complexity_contribution INT64,
    created_at INT64,
    updated_at INT64
)
```

### Extended Relationship Tables

**Symbol Relationships**:
```sql
CREATE REL TABLE DECLARES_SYMBOL(
    FROM Function TO Symbol,
    declaration_type STRING,
    created_at INT64
)

CREATE REL TABLE CLASS_FIELD(
    FROM Class TO Symbol,
    visibility STRING,          -- 'public', 'private', 'protected'
    is_static BOOLEAN,
    created_at INT64
)
```

**Assignment Relationships**:
```sql
CREATE REL TABLE ASSIGNS_TO(
    FROM Assignment TO Symbol,
    assignment_operator STRING, -- '=', '+=', '-=', etc.
    created_at INT64
)

CREATE REL TABLE ASSIGNMENT_IN_FUNCTION(
    FROM Function TO Assignment,
    created_at INT64
)
```

**Interface Relationships**:
```sql
CREATE REL TABLE IMPLEMENTS(
    FROM Class TO Interface,
    is_partial BOOLEAN,
    created_at INT64
)

CREATE REL TABLE INTERFACE_METHOD(
    FROM Interface TO Function,
    is_optional BOOLEAN,
    created_at INT64
)
```

**Type Relationships**:
```sql
CREATE REL TABLE USES_TYPE(
    FROM Symbol TO TypeAlias,
    usage_context STRING,
    created_at INT64
)
```

**Parameter Relationships**:
```sql
CREATE REL TABLE HAS_PARAMETER(
    FROM Function TO Parameter,
    created_at INT64
)
```

**CodeBlock Relationships**:
```sql
CREATE REL TABLE CONTAINS_BLOCK(
    FROM Function TO CodeBlock,
    nesting_level INT64,
    created_at INT64
)

CREATE REL TABLE NESTED_BLOCK(
    FROM CodeBlock TO CodeBlock,
    relationship_type STRING,   -- 'parent_child', 'if_else', 'try_catch'
    created_at INT64
)
```

## Implementation Steps

### Step 1: Extend KuzuSync Schema Initialization

**Location**: `src/graph_sitter/extensions/kuzu_map/sync.py`
**Method**: `_init_schema()`

**Action**: Add all missing table creation statements to existing schema initialization:

```python
def _init_schema(self):
    """Initialize complete KuzuDB schema including extended entities"""

    # Existing tables (File, Function, Class, Import)
    existing_schemas = [...]

    # Extended node tables
    extended_node_schemas = [
        """CREATE NODE TABLE IF NOT EXISTS Symbol(...)""",
        """CREATE NODE TABLE IF NOT EXISTS Assignment(...)""",
        """CREATE NODE TABLE IF NOT EXISTS Interface(...)""",
        """CREATE NODE TABLE IF NOT EXISTS TypeAlias(...)""",
        """CREATE NODE TABLE IF NOT EXISTS Parameter(...)""",
        """CREATE NODE TABLE IF NOT EXISTS CodeBlock(...)"""
    ]

    # Extended relationship tables
    extended_rel_schemas = [
        """CREATE REL TABLE IF NOT EXISTS DECLARES_SYMBOL(...)""",
        # ... all relationship tables
    ]

    # Execute all schemas
    all_schemas = existing_schemas + extended_node_schemas + extended_rel_schemas

    for schema in all_schemas:
        try:
            self.conn.execute(schema)
            logger.debug(f"Schema created: {schema[:50]}...")
        except Exception as e:
            logger.error(f"Failed to create schema: {e}")
            raise
```

### Step 2: Implement Data Extraction

**Location**: `src/graph_sitter/extensions/kuzu_map/sync.py`
**Add New Methods**:

```python
def _extract_symbols(self, file_obj) -> List[Dict]:
    """Extract symbol declarations from file"""
    # Implementation to parse AST and extract variables, constants, etc.
    pass

def _extract_assignments(self, file_obj) -> List[Dict]:
    """Extract assignment operations from file"""
    # Implementation to parse assignment statements
    pass

def _extract_parameters(self, func_obj) -> List[Dict]:
    """Extract detailed parameter information"""
    # Implementation to parse function parameters with types, defaults, etc.
    pass

def _extract_code_blocks(self, func_obj) -> List[Dict]:
    """Extract control flow blocks from function"""
    # Implementation to parse if/for/while/try blocks
    pass

def _extract_interfaces(self, file_obj) -> List[Dict]:
    """Extract interface definitions (TypeScript/Java)"""
    # Implementation for interface parsing
    pass

def _extract_type_aliases(self, file_obj) -> List[Dict]:
    """Extract type alias definitions"""
    # Implementation for type alias parsing
    pass
```

### Step 3: Extend Synchronization Process

**Location**: Same file, modify `sync()` method:

```python
def sync(self):
    """Enhanced sync with extended entities"""
    try:
        logger.info("Starting enhanced codebase synchronization...")

        # Existing sync (files, functions, classes, imports)
        self._sync_files()
        self._sync_functions()
        self._sync_classes()
        self._sync_imports()

        # Extended sync
        self._sync_symbols()
        self._sync_assignments()
        self._sync_parameters()
        self._sync_code_blocks()

        # Language-specific entities
        self._sync_interfaces()
        self._sync_type_aliases()

        # Create relationships
        self._create_extended_relationships()

        logger.info("Enhanced synchronization completed successfully")

    except Exception as e:
        logger.error(f"Synchronization failed: {e}")
        raise
```

### Step 4: Update Analysis Queries

**Location**: `src/graph_sitter/extensions/kuzu_map/analyzer.py`
**Ensure All Referenced Queries Work**:

```python
def find_unused_variables(self):
    """Find declared symbols that are never assigned or used"""
    query = """
    MATCH (s:Symbol)
    WHERE NOT exists {
        MATCH ()-[:ASSIGNS_TO]->(s)
    }
    AND s.kind = 'variable'
    RETURN s.name, s.file_path, s.start_line, s.scope
    ORDER BY s.file_path, s.start_line
    """
    return self.kuzu_sync.query(query)

def analyze_parameter_complexity(self, threshold: int = 5):
    """Find functions with too many parameters"""
    query = """
    MATCH (f:Function)-[:HAS_PARAMETER]->(p:Parameter)
    WITH f, count(p) as param_count
    WHERE param_count > $threshold
    RETURN f.name, f.file_path, param_count
    ORDER BY param_count DESC
    """
    return self.kuzu_sync.query(query, {"threshold": threshold})

def find_deeply_nested_blocks(self, max_depth: int = 3):
    """Find code blocks nested beyond a certain depth"""
    query = """
    MATCH path = (f:Function)-[:CONTAINS_BLOCK]->(b1:CodeBlock)
                 -[:NESTED_BLOCK*1..]->(b2:CodeBlock)
    WHERE length(path) > $max_depth
    RETURN f.name, f.file_path, b2.start_line,
           length(path) as nesting_depth, b2.block_type
    ORDER BY nesting_depth DESC
    """
    return self.kuzu_sync.query(query, {"max_depth": max_depth})
```

### Step 5: Graceful Migration

**Add Schema Version Check**:
```python
def _check_schema_version(self):
    """Check if database has extended schema"""
    try:
        # Test for Symbol table existence
        self.conn.execute("MATCH (s:Symbol) RETURN count(s) LIMIT 1")
        return "extended"
    except:
        return "basic"

def _migrate_schema_if_needed(self):
    """Migrate existing database to extended schema"""
    schema_version = self._check_schema_version()

    if schema_version == "basic":
        logger.info("Migrating to extended schema...")
        self._init_extended_schema()
        self._resync_with_extended_entities()
        logger.info("Schema migration completed")
```

## Implementation Priority

### Phase 1: Schema Tables (Essential)
1. Create all missing node and relationship tables
2. Update schema initialization to include extended entities
3. Test table creation and basic queries

### Phase 2: Data Extraction (Core Functionality)
1. Implement extraction methods for each entity type
2. Update synchronization process to populate new tables
3. Test data population with sample code

### Phase 3: Analysis Integration (Advanced Features)
1. Update existing analysis queries to use new tables
2. Add new analysis capabilities leveraging extended schema
3. Comprehensive testing of analysis tools

## Success Criteria

### Schema Consistency
- [ ] All referenced entities exist in database schema
- [ ] All analysis queries execute without "table not found" errors
- [ ] Schema creation succeeds for all entity types
- [ ] Relationship constraints are properly defined

### Functionality Completeness
- [ ] Symbol analysis works (unused variables, scope analysis)
- [ ] Assignment tracking enables data flow analysis
- [ ] Parameter analysis provides function signature insights
- [ ] Code block analysis supports complexity and nesting metrics
- [ ] Interface/TypeAlias support enhances type system analysis

### Migration Safety
- [ ] Existing databases can be upgraded gracefully
- [ ] Schema version detection works correctly
- [ ] Migration preserves existing data integrity
- [ ] Rollback capability for failed migrations

## Validation Plan

### Test Database Creation
```bash
# Test complete schema creation
python -c "
from graph_sitter.extensions.kuzu_map import KuzuSync
from graph_sitter.core.codebase import Codebase
sync = KuzuSync(Codebase('./'), './test_complete_schema.kuzu')
"
```

### Test Analysis Queries
```bash
# Test all referenced queries work
mcp-client analyze_code_structure --analysis-type unused
mcp-client analyze_code_structure --analysis-type parameters --threshold 3
mcp-client analyze_code_structure --analysis-type nesting --threshold 2
```

### Test Data Population
```bash
# Verify new entities are populated
mcp-client query "MATCH (s:Symbol) RETURN count(s)"
mcp-client query "MATCH (a:Assignment) RETURN count(a)"
mcp-client query "MATCH (p:Parameter) RETURN count(p)"
mcp-client query "MATCH (b:CodeBlock) RETURN count(b)"
```

---

**Sub-Task Status**: 📋 SPECIFICATION COMPLETE
**Implementation Priority**: 🟡 MEDIUM - Affects analysis completeness
**Estimated Complexity**: 🟡 MEDIUM - Requires schema work and data extraction
**Dependencies**: Can be implemented after 04.01 and 04.02, or in parallel