# Graph-Sitter Features, Functions & Classes Checklist

## Core Codebase Features

### Codebase Class (src/graph_sitter/core/codebase.py)

#### Properties
- [ ] `files` - Collection of all source files in the codebase
- [ ] `directories` - Directory structure and hierarchy
- [ ] `functions` - All function and method definitions
- [ ] `classes` - All class definitions
- [ ] `symbols` - All named symbols (functions, classes, variables)
- [ ] `imports` - Import statements across all files
- [ ] `exports` - Export statements (TypeScript/JavaScript)
- [ ] `global_vars` - Module-level variables
- [ ] `interfaces` - Interface definitions (TypeScript)
- [ ] `types` - Type aliases and definitions
- [ ] `codeowners` - CODEOWNERS file mappings

#### Methods - File Operations
- [ ] `create_file(filepath, content)` - Create new files with content
- [ ] `get_file(filepath)` - Retrieve file by path
- [ ] `has_file(filepath)` - Check if file exists
- [ ] `delete_file(filepath)` - Remove file from codebase

#### Methods - Directory Operations
- [ ] `create_directory(dir_path)` - Create new directories
- [ ] `get_directory(dir_path)` - Retrieve directory by path
- [ ] `has_directory(dir_path)` - Check if directory exists

#### Methods - Symbol Operations
- [ ] `get_symbol(name)` - Retrieve symbol by name
- [ ] `get_class(name)` - Get class definition
- [ ] `get_function(name)` - Get function definition
- [ ] `has_symbol(name)` - Check if symbol exists

#### Methods - Git Integration
- [ ] `git_commit(message, branch_name)` - Commit changes to repository
- [ ] `sync_to_commit(commit_hash)` - Sync codebase to specific commit

#### Methods - AI Integration
- [ ] `ask_ai(prompt)` - Query AI about codebase
- [ ] `ai_powered_search(query)` - AI-enhanced code search

## Core Symbol Classes (src/graph_sitter/core/)

### Base Abstractions
- [ ] `Symbol` - Base class for all code symbols with name, location, body
- [ ] `File` - Represents source files with path, content, symbols
- [ ] `Directory` - Directory representation with files and subdirectories
- [ ] `Function` - Function/method with parameters, return type, body
- [ ] `Class` - Class definition with methods, attributes, inheritance
- [ ] `Assignment` - Variable assignments at module/class level
- [ ] `Import` - Import statements with module and symbol resolution
- [ ] `Interface` - TypeScript interface definitions
- [ ] `TypeAlias` - Type alias definitions
- [ ] `Export` - Export statements (TypeScript/JavaScript)
- [ ] `Parameter` - Function parameters with types and defaults
- [ ] `CodeBlock` - Generic code block representation

### Mixin Interfaces
- [ ] `Editable` - Enables code modification capabilities
- [ ] `Callable` - Represents callable items (functions, methods)
- [ ] `Chainable` - Attribute chains (e.g., obj.attr1.attr2)
- [ ] `Resolvable` - Type resolution support
- [ ] `Usable` - Usage tracking and references
- [ ] `HasSymbols` - Contains nested symbols
- [ ] `Importable` - Can be imported from other modules
- [ ] `Inherits` - Inheritance relationship tracking

## Expression Types (src/graph_sitter/core/expressions/)

### Literal Expressions
- [ ] `Name` - Variable/identifier references
- [ ] `String` - String literals with quotes
- [ ] `Number` - Numeric literals (int, float)
- [ ] `Boolean` - Boolean literals (True/False)
- [ ] `NoneType` - None/null/undefined values

### Complex Expressions
- [ ] `ChainedAttribute` - Chained property access (a.b.c)
- [ ] `GenericType` - Generic type parameters
- [ ] `UnionType` - Union types (A | B)
- [ ] `TupleType` - Tuple type definitions
- [ ] `SubscriptExpression` - Generic instantiation (List[int])
- [ ] `BinaryExpression` - Binary operations (+, -, *, /, etc.)
- [ ] `UnaryExpression` - Unary operations (!, -, +)
- [ ] `TernaryExpression` - Ternary/conditional expressions
- [ ] `FunctionCall` - Function invocations with arguments

## Statement Types (src/graph_sitter/core/statements/)

### Control Flow
- [ ] `IfBlock` - If/else conditional statements
- [ ] `ForLoop` - For loop iterations
- [ ] `WhileLoop` - While loop iterations
- [ ] `SwitchStatement` - Switch/match statements
- [ ] `TryCatchStatement` - Exception handling blocks

### Variable & Function Statements
- [ ] `AssignmentStatement` - Variable assignments
- [ ] `ReturnStatement` - Return statements with values
- [ ] `RaiseStatement` - Exception raising

### Import/Export Statements
- [ ] `ImportStatement` - Import declarations
- [ ] `ExportStatement` - Export declarations

### Documentation
- [ ] `Comment` - Code comments with metadata

## Codemod Features (src/graph_sitter/runner/)

### Codemod Models
- [ ] `Codemod` - Main class defining codemod with user code
- [ ] `CodemodRunResult` - Result containing success status, observation, diff
- [ ] `GroupingConfig` - Configuration for grouping flags (by file, owner, etc.)
- [ ] `BranchConfig` - Git branch configuration for PRs
- [ ] `CodemodContext` - Execution context with metadata

### Sandbox Runner (src/graph_sitter/runner/sandbox/runner.py)
- [ ] `warmup()` - Initialize and parse codebase
- [ ] `get_diff()` - Execute codemod and return diff
- [ ] `create_branch()` - Execute with flagging and create PR branches
- [ ] `flag_grouping` - Group code instances for batch processing

### Sandbox Server (src/graph_sitter/runner/sandbox/server.py)
- [ ] `GET /` - Health check endpoint returning ServerInfo
- [ ] `POST /diff` - Execute codemod and get diff without committing
- [ ] `POST /branch` - Create branches and PRs with grouped flags

### Ephemeral Sandbox (src/graph_sitter/runner/sandbox/ephemeral_server.py)
- [ ] `POST /run_on_string` - Execute codemod on arbitrary code strings

### Local Daemon (src/graph_sitter/runner/servers/local_daemon.py)
- [ ] `GET /` - Health check for local daemon
- [ ] `POST /run` - Execute codemod with optional commit on local repository

## CLI Commands (src/graph_sitter/cli/)

### Core Commands
- [ ] `gs init` - Initialize codemod workspace
- [ ] `gs create <name>` - Create new codemod from template
- [ ] `gs run <label>` - Execute codemod (local or daemon mode)
- [ ] `gs list` - List available codemods in workspace
- [ ] `gs reset` - Reset workspace to clean state

### Configuration Commands
- [ ] `gs config set <key> <value>` - Set configuration values
- [ ] `gs config get <key>` - Get configuration values
- [ ] `gs config list` - List all configurations

## Configuration Management (src/graph_sitter/configs/)

### Configuration Classes
- [ ] `BaseConfig` - Base configuration with validation
- [ ] `RepositoryConfig` - Repository-level settings
- [ ] `CodebaseConfig` - Codebase parsing configuration
- [ ] `SecretsConfig` - Secure credential management
- [ ] `UserConfig` - User-level preferences
- [ ] `SessionManager` - Manage active sessions

### Repository Configuration
- [ ] `RepoConfig.name` - Repository name
- [ ] `RepoConfig.full_name` - Full repository identifier
- [ ] `RepoConfig.base_dir` - Repository base directory
- [ ] `RepoConfig.language` - Programming language (Python, TypeScript)
- [ ] `RepoConfig.subdirectories` - Target subdirectories to analyze
- [ ] `RepoConfig.from_envs()` - Load configuration from environment

## Git Integration (src/graph_sitter/git/)

### Repository Operations
- [ ] `clone_repository(url, path)` - Clone remote repository
- [ ] `setup_repository(path)` - Initialize local repository
- [ ] `create_branch(name, base)` - Create new branch
- [ ] `checkout_branch(name)` - Switch to branch
- [ ] `create_tag(name, message)` - Create git tag
- [ ] `list_branches()` - List all branches

### Commit Operations
- [ ] `create_commit(message, files)` - Create commit with changes
- [ ] `get_commit_history(limit)` - Retrieve commit history
- [ ] `sync_to_commit(hash)` - Sync to specific commit

### Pull Request Operations
- [ ] `create_pull_request(title, body, base, head)` - Create PR
- [ ] `update_pull_request(pr_id, updates)` - Update existing PR
- [ ] `list_pull_requests()` - List repository PRs

### Code Owner Tracking
- [ ] `get_code_owners(filepath)` - Get owners for file
- [ ] `parse_codeowners_file()` - Parse CODEOWNERS file

## Flagging System (src/graph_sitter/codebase/flagging/)

### Flagging Classes
- [ ] `CodeFlag` - Individual code instance flag
- [ ] `Group` - Grouped collection of flags
- [ ] `GroupSegment` - Section of grouped flags

### Groupers
- [ ] `FileGrouper` - Group flags by file
- [ ] `FileChunkGrouper` - Group by file sections/chunks
- [ ] `CodeOwnerGrouper` - Group by CODEOWNERS assignments
- [ ] `InstanceGrouper` - Group by individual instances
- [ ] `AppGrouper` - Application-level grouping

## Visualization (src/graph_sitter/visualizations/)

### Visualization Manager
- [ ] `VisualizationManager` - Manage graph visualizations
- [ ] `write_graphviz_data(graph)` - Export graphs to JSON
- [ ] `create_dependency_graph()` - Generate dependency visualization
- [ ] `create_import_graph()` - Generate import relationship graph
- [ ] `create_symbol_graph()` - Generate symbol usage graph

### Supported Graph Types
- [ ] `NetworkX Graph` - NetworkX graph objects
- [ ] `Plotly Figure` - Plotly interactive visualizations

## Extensions

### LSP Extension (src/graph_sitter/extensions/lsp/)
- [ ] `code_completion()` - Code completion suggestions
- [ ] `goto_definition()` - Navigate to symbol definitions
- [ ] `find_references()` - Find all symbol references
- [ ] `document_symbols()` - List all symbols in document
- [ ] `workspace_symbols()` - Search symbols across workspace
- [ ] `hover()` - Show hover information
- [ ] `diagnostics()` - Report code diagnostics
- [ ] `code_actions()` - Provide code actions/fixes

#### LSP Codemods
- [ ] `move_symbol()` - Move symbol to another file
- [ ] `split_tests()` - Split test file into multiple files

### GitHub Extension (src/graph_sitter/extensions/github/)
- [ ] `create_pr(title, body, branch)` - Create pull request
- [ ] `update_pr(pr_id, updates)` - Update pull request
- [ ] `list_prs()` - List repository pull requests
- [ ] `get_pr_details(pr_id)` - Get PR details
- [ ] `create_issue(title, body)` - Create GitHub issue
- [ ] `webhook_handler()` - Handle GitHub webhooks

#### GitHub Event Types
- [ ] `PullRequestEvent` - PR events (opened, closed, merged)
- [ ] `PushEvent` - Push events
- [ ] `IssueEvent` - Issue events

### Linear Extension (src/graph_sitter/extensions/linear/)
- [ ] `create_issue(title, description)` - Create Linear issue
- [ ] `update_issue(issue_id, updates)` - Update Linear issue
- [ ] `link_pr_to_issue(pr_url, issue_id)` - Link PR to issue

### Graph Extension (src/graph_sitter/extensions/graph/)
- [ ] `create_graph(codebase)` - Create graph from codebase
- [ ] `export_to_neo4j(graph, connection)` - Export to Neo4j
- [ ] `query_graph(cypher_query)` - Query graph database

### Attribution Extension (src/graph_sitter/extensions/attribution/)
- [ ] `add_attribution_to_symbols()` - Add git history to symbols
- [ ] `analyze_ai_impact()` - Analyze AI-authored code impact
- [ ] `get_symbol_editors(symbol)` - Get editors for symbol
- [ ] `get_editor_history(symbol)` - Get edit history for symbol
- [ ] `is_ai_authored(symbol)` - Check if symbol is AI-authored

### Index Extension (src/graph_sitter/extensions/index/)
- [ ] `CodeIndex` - Fast symbol indexing
- [ ] `FileIndex` - File lookup optimization
- [ ] `SymbolIndex` - Symbol resolution indexing

### Slack Extension (src/graph_sitter/extensions/slack/)
- [ ] `send_notification(message, channel)` - Send Slack notification
- [ ] `post_codemod_results(results)` - Post codemod results

### MCP Extension (src/graph_sitter/extensions/mcp/)
- [ ] `expose_codebase_tools()` - Expose operations as MCP tools
- [ ] `register_codemod_resources()` - Register codemod resources
- [ ] `mcp_server()` - MCP protocol server

## AI Integration (src/graph_sitter/ai/)

### OpenAI Client
- [ ] `query_openai(prompt, context)` - Query OpenAI API
- [ ] `count_tokens(text)` - Count tokens using tiktoken
- [ ] `generate_system_prompt()` - Create system prompts
- [ ] `create_tool_definitions()` - Define tools for AI

### AI-Assisted Operations
- [ ] `ai_code_review()` - AI-powered code review
- [ ] `ai_refactoring_suggestions()` - Suggest refactorings
- [ ] `ai_bug_detection()` - Detect potential bugs

## Python-Specific Features (src/graph_sitter/python/)

### Python Symbol Classes
- [ ] `PythonFunction` - Python function with decorators
- [ ] `PythonClass` - Python class with metaclasses
- [ ] `PythonDecorator` - Decorator definitions
- [ ] `PythonProperty` - Property decorators
- [ ] `PythonClassMethod` - Class method decorators
- [ ] `PythonStaticMethod` - Static method decorators
- [ ] `PythonAsyncFunction` - Async function definitions
- [ ] `PythonGenerator` - Generator functions
- [ ] `PythonLambda` - Lambda expressions
- [ ] `PythonComprehension` - List/dict/set comprehensions
- [ ] `PythonWithStatement` - Context managers
- [ ] `PythonAsyncWith` - Async context managers

### Python Type System
- [ ] `PythonTypeAnnotation` - Type hints (PEP 484)
- [ ] `PythonTypeComment` - Type comments (legacy)
- [ ] `PythonGeneric` - Generic types
- [ ] `PythonProtocol` - Protocol types (PEP 544)
- [ ] `PythonTypedDict` - TypedDict definitions

## TypeScript-Specific Features (src/graph_sitter/typescript/)

### TypeScript Symbol Classes
- [ ] `TypeScriptInterface` - Interface definitions
- [ ] `TypeScriptTypeAlias` - Type alias declarations
- [ ] `TypeScriptEnum` - Enum definitions
- [ ] `TypeScriptNamespace` - Namespace declarations
- [ ] `TypeScriptModule` - Module declarations
- [ ] `TypeScriptDecorator` - Decorator syntax
- [ ] `TypeScriptGeneric` - Generic type parameters
- [ ] `TypeScriptIntersection` - Intersection types
- [ ] `TypeScriptUnion` - Union types
- [ ] `TypeScriptTuple` - Tuple types
- [ ] `TypeScriptMapped` - Mapped types
- [ ] `TypeScriptConditional` - Conditional types

### React-Specific
- [ ] `ReactComponent` - React component definitions
- [ ] `ReactHook` - React hooks (useState, useEffect, etc.)
- [ ] `ReactProps` - Component props interfaces
- [ ] `JSXElement` - JSX syntax elements
- [ ] `JSXAttribute` - JSX attributes

## Output & Formatting (src/graph_sitter/output/)

### Output Utilities
- [ ] `format_ast(node)` - Format AST representation
- [ ] `to_json(object)` - Convert to JSON
- [ ] `inspect_code(symbol)` - Inspect symbol details
- [ ] `format_diff(changes)` - Format diff output
- [ ] `highlight_syntax(code)` - Syntax highlighting

### Output Models
- [ ] `DiffLite` - Lightweight diff representation
- [ ] `Span` - Source code span (line, column)
- [ ] `Range` - Code range representation
- [ ] `HighlightedDiff` - Syntax-highlighted changes

## Testing Infrastructure (tests/)

### Test Categories
- [ ] Unit tests - 150+ test files for individual components
- [ ] Integration tests - 300+ test files for end-to-end flows
- [ ] Skill tests - 40+ tests for code transformation skills

### Test Utilities
- [ ] `skill_test_framework` - Framework for testing codemods
- [ ] `mock_codebase()` - Create mock codebases for testing
- [ ] `assert_diff(expected, actual)` - Diff assertion helper
- [ ] `run_codemod_test(codemod, input, expected)` - Codemod test runner

## Canonical Codemods (src/codemods/canonical/)

### Refactoring Codemods
- [ ] `move_functions_to_new_file` - Move functions with dependencies
- [ ] `rename_function_parameters` - Safe parameter renaming
- [ ] `update_union_types` - Update type annotations
- [ ] `refactor_react_components_into_separate_files` - Extract components
- [ ] `enum_mover` - Move enums with import management

### Migration Codemods
- [ ] `python2_to_python3` - Python 2 to 3 migration
- [ ] `unittest_to_pytest` - unittest to pytest conversion
- [ ] `sqlalchemy_1.6_to_2.0` - SQLAlchemy version migration
- [ ] `flask_to_fastapi_migration` - Flask to FastAPI migration
- [ ] `freezegun_to_timemachine_migration` - Test library migration

### Analysis Codemods
- [ ] `cyclomatic_complexity` - Calculate code complexity
- [ ] `delete_dead_code` - Remove unused code
- [ ] `symbol_attributions` - Add git attribution to symbols
- [ ] `dependency_analysis` - Analyze dependencies
- [ ] `type_coverage_analysis` - Check type annotation coverage

### Code Quality Codemods
- [ ] `add_type_annotations` - Add missing type hints
- [ ] `remove_unused_imports` - Clean up imports
- [ ] `format_docstrings` - Standardize docstrings
- [ ] `add_missing_tests` - Identify untested code
- [ ] `extract_magic_numbers` - Replace magic numbers with constants

## Performance Features

### Cython-Compiled Modules (src/graph_sitter/compiled/)
- [ ] `sort_editables()` - Optimize edit ordering
- [ ] `uncache_all()` - Memory management

### Optimization Features
- [ ] `lazy_evaluation` - Lazy loading for large codebases
- [ ] `recursive_parsing` - Configurable parsing depth
- [ ] `incremental_sync` - Incremental codebase updates
- [ ] `cache_management` - Symbol and file caching

## Build Utilities (src/gsbuild/)

### Build System
- [ ] `build_project()` - Build graph-sitter project
- [ ] `compile_cython()` - Compile Cython modules
- [ ] `generate_bindings()` - Generate language bindings
- [ ] `package_distribution()` - Create distribution packages

## Data Models

### API Models (src/graph_sitter/runner/models/apis.py)
- [ ] `ServerInfo` - Server status information
- [ ] `GetDiffRequest` - Request for diff generation
- [ ] `GetDiffResponse` - Diff generation response
- [ ] `CreateBranchRequest` - Branch creation request
- [ ] `CreateBranchResponse` - Branch creation response with PR info

### Execution Models
- [ ] `WarmupState` - Codebase warmup status
- [ ] `TransactionState` - Transaction management state
- [ ] `ExecutionLog` - Execution logging data
- [ ] `ErrorInfo` - Error details and stack traces

## Advanced Features

### Type Resolution
- [ ] `resolve_type(symbol)` - Resolve symbol types
- [ ] `infer_type(expression)` - Infer expression types
- [ ] `resolve_generic(type, parameters)` - Resolve generic types
- [ ] `resolve_import(import_path)` - Resolve import paths

### Dependency Management
- [ ] `get_dependencies(symbol)` - Get symbol dependencies
- [ ] `get_dependents(symbol)` - Get symbol dependents
- [ ] `check_circular_dependencies()` - Detect circular imports
- [ ] `build_dependency_graph()` - Create dependency graph

### Import Resolution
- [ ] `resolve_import_path(path)` - Resolve import to file
- [ ] `track_reexports(module)` - Track re-exported symbols
- [ ] `resolve_tsconfig_paths()` - Handle TypeScript path mappings
- [ ] `resolve_wildcard_imports()` - Handle wildcard imports

### Code Transformation
- [ ] `safe_rename(symbol, new_name)` - Rename with reference updates
- [ ] `safe_move(symbol, target_file)` - Move with import updates
- [ ] `extract_function(code_range, name)` - Extract function refactoring
- [ ] `inline_function(function)` - Inline function calls
- [ ] `extract_variable(expression, name)` - Extract to variable

## Metrics & Analysis

### Code Metrics
- [ ] `calculate_complexity(function)` - Cyclomatic complexity
- [ ] `calculate_lines_of_code(file)` - Count LOC
- [ ] `calculate_test_coverage()` - Test coverage metrics
- [ ] `identify_code_smells()` - Detect code smells
- [ ] `calculate_maintainability_index()` - Maintainability score

### Usage Analysis
- [ ] `find_usages(symbol)` - Find all symbol usages
- [ ] `find_unused_symbols()` - Identify unused code
- [ ] `analyze_import_usage()` - Import usage analysis
- [ ] `detect_dead_code()` - Find unreachable code

## Security & Validation

### Security Features
- [ ] `validate_secrets()` - Check for exposed secrets
- [ ] `scan_vulnerabilities()` - Security vulnerability scanning
- [ ] `validate_permissions()` - File permission validation

### Code Validation
- [ ] `validate_syntax(code)` - Syntax validation
- [ ] `validate_types(symbol)` - Type checking
- [ ] `validate_imports(file)` - Import validation
- [ ] `validate_circular_dependencies()` - Check circular deps

---

## Summary Statistics

- **Total Core Classes**: 150+ specialized symbol classes
- **Total Codemods**: 48+ (28 examples + 20 canonical)
- **Total Extensions**: 11 major extensions
- **Total CLI Commands**: 10+ commands
- **Total API Endpoints**: 6+ FastAPI endpoints
- **Total Test Files**: 502 test files
- **Languages Supported**: Python, TypeScript, JavaScript, React
- **Total Features**: 300+ distinct features

---

## UI Integration Priority Matrix

### Critical (Must Have)
- [ ] Codemod execution interface with preview
- [ ] Before/after diff viewer
- [ ] Repository browser and file explorer
- [ ] Configuration management UI
- [ ] Error display and validation feedback

### High Priority
- [ ] Search and filtering for codemods
- [ ] Symbol dependency visualization
- [ ] Git operations (branch, commit, PR)
- [ ] Progress tracking for long operations
- [ ] Documentation integration

### Medium Priority
- [ ] AI integration interface
- [ ] Attribution and history timeline
- [ ] Test runner and coverage display
- [ ] Metrics dashboard
- [ ] Code quality indicators

### Low Priority (Nice to Have)
- [ ] Custom codemod editor
- [ ] Performance profiling UI
- [ ] Slack/Linear integration controls
- [ ] Advanced graph visualizations
- [ ] Custom plugin configuration
