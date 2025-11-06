// Core Types for Graph-Sitter UI

export enum ProgrammingLanguage {
  PYTHON = 'python',
  TYPESCRIPT = 'typescript',
  JAVASCRIPT = 'javascript',
  REACT = 'react',
}

export enum WarmupState {
  NOT_STARTED = 'not_started',
  IN_PROGRESS = 'in_progress',
  COMPLETE = 'complete',
  FAILED = 'failed',
}

export enum ExecutionStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  SUCCESS = 'success',
  FAILED = 'failed',
  PARTIAL = 'partial',
}

export enum GroupBy {
  FILE = 'file',
  FILE_CHUNK = 'file_chunk',
  CODE_OWNER = 'code_owner',
  INSTANCE = 'instance',
  APP = 'app',
}

// Server Info
export interface ServerInfo {
  repo_name: string;
  synced_commit: string;
  warmup_state: WarmupState;
  version?: string;
  language?: ProgrammingLanguage;
}

// Codemod Definitions
export interface Codemod {
  user_code: string;
  codemod_context?: Record<string, any>;
  label?: string;
  description?: string;
  category?: string;
  tags?: string[];
}

export interface CodemodMetadata {
  label: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  language: ProgrammingLanguage;
  author?: string;
  version?: string;
  created_at?: string;
  updated_at?: string;
  examples?: CodemodExample[];
}

export interface CodemodExample {
  title: string;
  before: string;
  after: string;
  description?: string;
}

// Execution Requests/Responses
export interface GetDiffRequest {
  codemod: Codemod;
  max_transactions?: number;
  max_seconds?: number;
}

export interface CreateBranchRequest {
  codemod: Codemod;
  commit_msg: string;
  grouping_config?: GroupingConfig;
  branch_config?: BranchConfig;
}

export interface GroupingConfig {
  subdirectories?: string[];
  group_by?: GroupBy;
  max_prs?: number;
}

export interface BranchConfig {
  branch_name: string;
  custom_base_branch?: string;
  force_push?: boolean;
}

// Results
export interface CodemodRunResult {
  is_complete: boolean;
  observation: string;
  visualization?: VisualizationData;
  highlighted_diff?: string;
  flags?: CodeFlag[];
  error?: ErrorInfo;
  logs?: string[];
  execution_time?: number;
  files_changed?: number;
}

export interface CreateBranchResponse {
  results: CodemodRunResult[];
  branches: BranchInfo[];
  num_flags: number;
  group_segments?: GroupSegment[];
}

export interface BranchInfo {
  branch_name: string;
  commit_hash: string;
  pr_url?: string;
  files_changed: string[];
  num_flags: number;
}

export interface GroupSegment {
  group_id: string;
  group_name: string;
  flags: CodeFlag[];
  branch?: string;
}

// Code Flags
export interface CodeFlag {
  id: string;
  file_path: string;
  line_start: number;
  line_end: number;
  code_snippet: string;
  description?: string;
  group_id?: string;
  severity?: 'info' | 'warning' | 'error';
}

// Error Information
export interface ErrorInfo {
  message: string;
  type: string;
  stack_trace?: string;
  line_number?: number;
  file_path?: string;
}

// Visualization
export interface VisualizationData {
  type: 'graph' | 'tree' | 'chart';
  data: any;
  config?: Record<string, any>;
}

// File and Directory
export interface FileInfo {
  path: string;
  name: string;
  extension: string;
  size: number;
  language: ProgrammingLanguage;
  content?: string;
  symbols?: SymbolInfo[];
}

export interface DirectoryInfo {
  path: string;
  name: string;
  files: FileInfo[];
  subdirectories: DirectoryInfo[];
}

// Symbol Information
export interface SymbolInfo {
  name: string;
  type: SymbolType;
  file_path: string;
  line_start: number;
  line_end: number;
  signature?: string;
  docstring?: string;
  is_exported?: boolean;
  is_imported?: boolean;
  usages?: SymbolUsage[];
}

export enum SymbolType {
  FUNCTION = 'function',
  CLASS = 'class',
  METHOD = 'method',
  VARIABLE = 'variable',
  CONSTANT = 'constant',
  INTERFACE = 'interface',
  TYPE_ALIAS = 'type_alias',
  ENUM = 'enum',
}

export interface SymbolUsage {
  file_path: string;
  line_number: number;
  context: string;
}

// Git Information
export interface GitInfo {
  current_branch: string;
  synced_commit: string;
  branches: string[];
  uncommitted_changes: boolean;
  recent_commits: CommitInfo[];
}

export interface CommitInfo {
  hash: string;
  author: string;
  date: string;
  message: string;
  files_changed: number;
}

export interface PullRequestInfo {
  id: number;
  title: string;
  description: string;
  url: string;
  status: 'open' | 'closed' | 'merged';
  base_branch: string;
  head_branch: string;
  created_at: string;
  updated_at: string;
}

// Configuration
export interface RepositoryConfig {
  name: string;
  full_name: string;
  base_dir: string;
  language: ProgrammingLanguage;
  subdirectories: string[];
  ignore_patterns?: string[];
}

export interface UserConfig {
  theme: 'light' | 'dark' | 'auto';
  editor_preferences: {
    font_size: number;
    tab_size: number;
    show_line_numbers: boolean;
    syntax_highlighting: boolean;
  };
  default_grouping?: GroupBy;
  max_prs?: number;
}

// Search and Filtering
export interface SearchFilters {
  query?: string;
  category?: string;
  tags?: string[];
  language?: ProgrammingLanguage;
  sort_by?: 'name' | 'date' | 'popularity';
  sort_order?: 'asc' | 'desc';
}

export interface SearchResult {
  codemods: CodemodMetadata[];
  total: number;
  page: number;
  per_page: number;
}

// UI State
export interface UIState {
  sidebarOpen: boolean;
  selectedCodemod?: CodemodMetadata;
  executionStatus: ExecutionStatus;
  currentView: ViewType;
  theme: 'light' | 'dark';
}

export enum ViewType {
  CODEMODS = 'codemods',
  EXECUTION = 'execution',
  DIFF = 'diff',
  REPOSITORY = 'repository',
  CONFIGURATION = 'configuration',
  DOCUMENTATION = 'documentation',
  HISTORY = 'history',
}

// Analysis Results
export interface CodeAnalysis {
  complexity: number;
  lines_of_code: number;
  test_coverage?: number;
  dependencies: DependencyInfo[];
  code_smells: CodeSmell[];
  metrics: Record<string, number>;
}

export interface DependencyInfo {
  symbol: string;
  type: 'import' | 'usage';
  file_path: string;
  line_number: number;
}

export interface CodeSmell {
  type: string;
  description: string;
  file_path: string;
  line_number: number;
  severity: 'low' | 'medium' | 'high';
  suggestion?: string;
}

// Execution History
export interface ExecutionHistoryItem {
  id: string;
  codemod_label: string;
  timestamp: string;
  status: ExecutionStatus;
  duration: number;
  files_changed: number;
  branch?: string;
  error?: string;
}

// API Response Wrapper
export interface ApiResponse<T> {
  data?: T;
  error?: string;
  message?: string;
  status: number;
}

// WebSocket Events
export interface ExecutionProgressEvent {
  execution_id: string;
  progress: number;
  current_step: string;
  total_steps: number;
  message: string;
}

export interface FileChangeEvent {
  file_path: string;
  change_type: 'created' | 'modified' | 'deleted';
  timestamp: string;
}
