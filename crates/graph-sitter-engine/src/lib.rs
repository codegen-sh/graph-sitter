#![forbid(unsafe_code)]

use serde::Serialize;
use std::collections::{BTreeMap, HashMap, HashSet};
use std::fmt;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use tree_sitter::{Node, Parser, Range, Tree};

const ENABLED_FEATURES: &[&str] = &["skeleton", "python-index"];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct EngineInfo {
    version: &'static str,
    enabled_features: &'static [&'static str],
}

impl EngineInfo {
    pub fn version(&self) -> &'static str {
        self.version
    }

    pub fn enabled_features(&self) -> &'static [&'static str] {
        self.enabled_features
    }
}

#[derive(Debug, Default, Clone, Copy)]
pub struct Engine;

impl Engine {
    pub fn new() -> Self {
        Self
    }

    pub fn debug_info(&self) -> EngineInfo {
        debug_info()
    }

    pub fn version(&self) -> &'static str {
        engine_version()
    }

    pub fn enabled_features(&self) -> &'static [&'static str] {
        ENABLED_FEATURES
    }

    pub fn index_python_path(
        &self,
        repo_path: impl AsRef<Path>,
    ) -> Result<PythonIndex, IndexError> {
        PythonIndexer::new()?.index_path(repo_path)
    }

    pub fn index_python_paths<I, P>(
        &self,
        repo_path: impl AsRef<Path>,
        file_paths: I,
    ) -> Result<PythonIndex, IndexError>
    where
        I: IntoIterator<Item = P>,
        P: AsRef<Path>,
    {
        PythonIndexer::new()?.index_paths(repo_path, file_paths)
    }
}

pub fn engine_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

pub fn debug_info() -> EngineInfo {
    EngineInfo {
        version: engine_version(),
        enabled_features: ENABLED_FEATURES,
    }
}

pub fn index_python_path(repo_path: impl AsRef<Path>) -> Result<PythonIndex, IndexError> {
    Engine::new().index_python_path(repo_path)
}

pub fn index_python_paths<I, P>(
    repo_path: impl AsRef<Path>,
    file_paths: I,
) -> Result<PythonIndex, IndexError>
where
    I: IntoIterator<Item = P>,
    P: AsRef<Path>,
{
    Engine::new().index_python_paths(repo_path, file_paths)
}

#[derive(Debug)]
pub enum IndexError {
    Io { path: PathBuf, source: io::Error },
    ParseFailed { path: PathBuf },
    Language(tree_sitter::LanguageError),
}

impl fmt::Display for IndexError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io { path, source } => write!(f, "failed to read {}: {source}", path.display()),
            Self::ParseFailed { path } => {
                write!(f, "tree-sitter failed to parse {}", path.display())
            }
            Self::Language(source) => {
                write!(f, "failed to load tree-sitter Python language: {source}")
            }
        }
    }
}

impl std::error::Error for IndexError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io { source, .. } => Some(source),
            Self::Language(source) => Some(source),
            Self::ParseFailed { .. } => None,
        }
    }
}

impl From<tree_sitter::LanguageError> for IndexError {
    fn from(value: tree_sitter::LanguageError) -> Self {
        Self::Language(value)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct PythonIndex {
    pub files: Vec<FileRecord>,
    pub symbols: Vec<SymbolRecord>,
    pub imports: Vec<ImportRecord>,
    pub import_resolutions: Vec<ImportResolutionRecord>,
    pub references: Vec<ReferenceRecord>,
    pub dependencies: Vec<DependencyRecord>,
}

impl PythonIndex {
    pub fn summary(&self) -> IndexSummary {
        IndexSummary {
            files: self.files.len(),
            symbols: self.symbols.len(),
            classes: self
                .symbols
                .iter()
                .filter(|symbol| symbol.kind == SymbolKind::Class)
                .count(),
            functions: self
                .symbols
                .iter()
                .filter(|symbol| symbol.kind == SymbolKind::Function)
                .count(),
            global_variables: self
                .symbols
                .iter()
                .filter(|symbol| symbol.kind == SymbolKind::GlobalVariable)
                .count(),
            imports: self.imports.len(),
            import_resolutions: self.import_resolutions.len(),
            references: self.references.len(),
            dependencies: self.dependencies.len(),
            bytes: self.files.iter().map(|file| file.byte_len).sum(),
            lines: self.files.iter().map(|file| file.line_count).sum(),
            files_with_errors: self.files.iter().filter(|file| file.has_error).count(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct IndexSummary {
    pub files: usize,
    pub symbols: usize,
    pub classes: usize,
    pub functions: usize,
    pub global_variables: usize,
    pub imports: usize,
    pub import_resolutions: usize,
    pub references: usize,
    pub dependencies: usize,
    pub bytes: usize,
    pub lines: usize,
    pub files_with_errors: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct FileRecord {
    pub id: u32,
    pub path: String,
    pub module_name: Option<String>,
    pub byte_len: usize,
    pub line_count: usize,
    pub has_error: bool,
    pub root_range: SourceRange,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SymbolKind {
    Class,
    Function,
    GlobalVariable,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SymbolRecord {
    pub id: u32,
    pub file_id: u32,
    pub parent_symbol_id: Option<u32>,
    pub is_top_level: bool,
    pub name: String,
    pub kind: SymbolKind,
    pub range: SourceRange,
    pub name_range: SourceRange,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ImportKind {
    Import,
    FromImport,
    FutureImport,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ImportRecord {
    pub id: u32,
    pub file_id: u32,
    pub kind: ImportKind,
    pub module: Option<String>,
    pub name: Option<String>,
    pub alias: Option<String>,
    pub range: SourceRange,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ImportResolutionRecord {
    pub id: u32,
    pub import_id: u32,
    pub source_file_id: u32,
    pub target_file_id: u32,
    pub target_symbol_id: Option<u32>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ReferenceRecord {
    pub id: u32,
    pub source_file_id: u32,
    pub source_symbol_id: Option<u32>,
    pub target_symbol_id: u32,
    pub import_id: Option<u32>,
    pub name: String,
    pub range: SourceRange,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct DependencyRecord {
    pub id: u32,
    pub source_symbol_id: u32,
    pub target_symbol_id: u32,
    pub source_file_id: u32,
    pub target_file_id: u32,
    pub reference_ids: Vec<u32>,
    pub reference_count: usize,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct SourceRange {
    pub start_byte: usize,
    pub end_byte: usize,
    pub start_row: usize,
    pub start_column: usize,
    pub end_row: usize,
    pub end_column: usize,
}

impl From<Range> for SourceRange {
    fn from(value: Range) -> Self {
        Self {
            start_byte: value.start_byte,
            end_byte: value.end_byte,
            start_row: value.start_point.row,
            start_column: value.start_point.column,
            end_row: value.end_point.row,
            end_column: value.end_point.column,
        }
    }
}

struct PythonIndexer {
    parser: Parser,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ReferenceCandidate {
    source_file_id: u32,
    source_symbol_id: Option<u32>,
    name: String,
    range: SourceRange,
}

impl PythonIndexer {
    fn new() -> Result<Self, IndexError> {
        let mut parser = Parser::new();
        parser.set_language(&tree_sitter_python::LANGUAGE.into())?;
        Ok(Self { parser })
    }

    fn index_path(mut self, repo_path: impl AsRef<Path>) -> Result<PythonIndex, IndexError> {
        let repo_path = repo_path.as_ref();
        let mut paths = Vec::new();
        collect_python_files(repo_path, &mut paths)?;
        self.index_absolute_paths(repo_path, paths)
    }

    fn index_paths<I, P>(
        mut self,
        repo_path: impl AsRef<Path>,
        file_paths: I,
    ) -> Result<PythonIndex, IndexError>
    where
        I: IntoIterator<Item = P>,
        P: AsRef<Path>,
    {
        let repo_path = repo_path.as_ref();
        let paths = file_paths
            .into_iter()
            .map(|path| {
                let path = path.as_ref();
                if path.is_absolute() {
                    path.to_path_buf()
                } else {
                    repo_path.join(path)
                }
            })
            .collect();
        self.index_absolute_paths(repo_path, paths)
    }

    fn index_absolute_paths(
        &mut self,
        repo_path: &Path,
        mut paths: Vec<PathBuf>,
    ) -> Result<PythonIndex, IndexError> {
        let mut index = PythonIndex {
            files: Vec::new(),
            symbols: Vec::new(),
            imports: Vec::new(),
            import_resolutions: Vec::new(),
            references: Vec::new(),
            dependencies: Vec::new(),
        };
        let mut reference_candidates = Vec::new();
        paths.sort();

        for path in paths {
            let file_id = index.files.len() as u32;
            let content = fs::read_to_string(&path).map_err(|source| IndexError::Io {
                path: path.clone(),
                source,
            })?;
            let tree = self
                .parser
                .parse(&content, None)
                .ok_or_else(|| IndexError::ParseFailed { path: path.clone() })?;
            let root = tree.root_node();
            let relative_path = path
                .strip_prefix(repo_path)
                .unwrap_or(path.as_path())
                .to_string_lossy()
                .replace('\\', "/");

            index.files.push(FileRecord {
                id: file_id,
                module_name: python_module_name(&relative_path),
                path: relative_path,
                byte_len: content.len(),
                line_count: line_count(&content),
                has_error: root.has_error(),
                root_range: root.range().into(),
            });
            extract_python_file(
                file_id,
                &content,
                &tree,
                &mut index,
                &mut reference_candidates,
            );
        }

        resolve_python_imports(&mut index);
        resolve_python_references(&mut index, reference_candidates);
        build_python_dependencies(&mut index);
        Ok(index)
    }
}

fn collect_python_files(dir: &Path, out: &mut Vec<PathBuf>) -> Result<(), IndexError> {
    let entries = fs::read_dir(dir).map_err(|source| IndexError::Io {
        path: dir.to_path_buf(),
        source,
    })?;
    for entry in entries {
        let entry = entry.map_err(|source| IndexError::Io {
            path: dir.to_path_buf(),
            source,
        })?;
        let path = entry.path();
        let file_type = entry.file_type().map_err(|source| IndexError::Io {
            path: path.clone(),
            source,
        })?;
        if file_type.is_dir() {
            if should_skip_dir(&path) {
                continue;
            }
            collect_python_files(&path, out)?;
        } else if file_type.is_file() && path.extension().and_then(|ext| ext.to_str()) == Some("py")
        {
            out.push(path);
        }
    }
    Ok(())
}

fn should_skip_dir(path: &Path) -> bool {
    matches!(
        path.file_name().and_then(|name| name.to_str()),
        Some(
            ".git" | ".hg" | ".svn" | ".venv" | "venv" | "__pycache__" | "node_modules" | "target"
        )
    )
}

fn extract_python_file(
    file_id: u32,
    source: &str,
    tree: &Tree,
    index: &mut PythonIndex,
    reference_candidates: &mut Vec<ReferenceCandidate>,
) {
    let root = tree.root_node();
    let mut excluded_name_ranges = Vec::new();
    let mut cursor = root.walk();
    for child in root.named_children(&mut cursor) {
        extract_top_level_node(file_id, source, child, index, &mut excluded_name_ranges);
    }
    let symbol_ranges = index
        .symbols
        .iter()
        .filter(|symbol| symbol.file_id == file_id)
        .map(|symbol| (symbol.id, symbol.range))
        .collect::<Vec<_>>();
    let local_bindings_by_symbol_id =
        collect_local_bindings(file_id, source, root, index, &symbol_ranges);
    collect_identifier_candidates(
        file_id,
        source,
        root,
        &symbol_ranges,
        &local_bindings_by_symbol_id,
        &excluded_name_ranges,
        reference_candidates,
    );
}

fn extract_top_level_node(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    index: &mut PythonIndex,
    excluded_name_ranges: &mut Vec<SourceRange>,
) {
    match node.kind() {
        "class_definition" => {
            extract_symbol_tree(
                file_id,
                source,
                node,
                node.range(),
                SymbolKind::Class,
                None,
                index,
                excluded_name_ranges,
            );
        }
        "function_definition" => {
            extract_symbol_tree(
                file_id,
                source,
                node,
                node.range(),
                SymbolKind::Function,
                None,
                index,
                excluded_name_ranges,
            );
        }
        "decorated_definition" => {
            if let Some(definition) =
                first_child_of_kind(node, &["class_definition", "function_definition"])
            {
                let kind = if definition.kind() == "class_definition" {
                    SymbolKind::Class
                } else {
                    SymbolKind::Function
                };
                extract_symbol_tree(
                    file_id,
                    source,
                    definition,
                    node.range(),
                    kind,
                    None,
                    index,
                    excluded_name_ranges,
                );
            }
        }
        "import_statement" => push_import_statement(file_id, source, node, index),
        "import_from_statement" | "future_import_statement" => {
            push_from_import_statement(file_id, source, node, index)
        }
        "assignment" | "annotated_assignment" => {
            push_global_assignment(file_id, source, node, index, excluded_name_ranges)
        }
        "expression_statement" => {
            if let Some(assignment) =
                first_child_of_kind(node, &["assignment", "annotated_assignment"])
            {
                push_global_assignment(file_id, source, assignment, index, excluded_name_ranges);
            }
        }
        _ => {}
    }
}

fn extract_symbol_tree(
    file_id: u32,
    source: &str,
    definition: Node<'_>,
    declaration_range: Range,
    kind: SymbolKind,
    parent_symbol_id: Option<u32>,
    index: &mut PythonIndex,
    excluded_name_ranges: &mut Vec<SourceRange>,
) -> Option<u32> {
    let symbol_id = push_symbol_with_range(
        file_id,
        source,
        definition,
        declaration_range,
        kind,
        parent_symbol_id,
        index,
    )?;
    if let Some(name_node) = definition.child_by_field_name("name") {
        excluded_name_ranges.push(name_node.range().into());
    }
    extract_nested_symbols(
        file_id,
        source,
        definition,
        Some(symbol_id),
        index,
        excluded_name_ranges,
    );
    Some(symbol_id)
}

fn extract_nested_symbols(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    parent_symbol_id: Option<u32>,
    index: &mut PythonIndex,
    excluded_name_ranges: &mut Vec<SourceRange>,
) {
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        match child.kind() {
            "class_definition" => {
                extract_symbol_tree(
                    file_id,
                    source,
                    child,
                    child.range(),
                    SymbolKind::Class,
                    parent_symbol_id,
                    index,
                    excluded_name_ranges,
                );
            }
            "function_definition" => {
                extract_symbol_tree(
                    file_id,
                    source,
                    child,
                    child.range(),
                    SymbolKind::Function,
                    parent_symbol_id,
                    index,
                    excluded_name_ranges,
                );
            }
            "decorated_definition" => {
                if let Some(definition) =
                    first_child_of_kind(child, &["class_definition", "function_definition"])
                {
                    let kind = if definition.kind() == "class_definition" {
                        SymbolKind::Class
                    } else {
                        SymbolKind::Function
                    };
                    extract_symbol_tree(
                        file_id,
                        source,
                        definition,
                        child.range(),
                        kind,
                        parent_symbol_id,
                        index,
                        excluded_name_ranges,
                    );
                }
            }
            _ => extract_nested_symbols(
                file_id,
                source,
                child,
                parent_symbol_id,
                index,
                excluded_name_ranges,
            ),
        }
    }
}

fn push_symbol_with_range(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    declaration_range: Range,
    kind: SymbolKind,
    parent_symbol_id: Option<u32>,
    index: &mut PythonIndex,
) -> Option<u32> {
    let Some(name_node) = node.child_by_field_name("name") else {
        return None;
    };
    let Ok(name) = name_node.utf8_text(source.as_bytes()) else {
        return None;
    };
    let symbol_id = index.symbols.len() as u32;
    index.symbols.push(SymbolRecord {
        id: symbol_id,
        file_id,
        parent_symbol_id,
        is_top_level: parent_symbol_id.is_none(),
        name: name.to_owned(),
        kind,
        range: declaration_range.into(),
        name_range: name_node.range().into(),
    });
    Some(symbol_id)
}

fn push_global_assignment(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    index: &mut PythonIndex,
    excluded_name_ranges: &mut Vec<SourceRange>,
) {
    let Some(left) = node.child_by_field_name("left") else {
        return;
    };
    let mut targets = Vec::new();
    collect_assignment_targets(left, &mut targets);
    for target in targets {
        let Ok(name) = target.utf8_text(source.as_bytes()) else {
            continue;
        };
        index.symbols.push(SymbolRecord {
            id: index.symbols.len() as u32,
            file_id,
            parent_symbol_id: None,
            is_top_level: true,
            name: name.to_owned(),
            kind: SymbolKind::GlobalVariable,
            range: node.range().into(),
            name_range: target.range().into(),
        });
        excluded_name_ranges.push(target.range().into());
    }
}

fn collect_assignment_targets<'tree>(node: Node<'tree>, out: &mut Vec<Node<'tree>>) {
    match node.kind() {
        "identifier" => out.push(node),
        "as_pattern_target" | "pattern" | "pattern_list" | "tuple_pattern" | "list_pattern" => {
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                collect_assignment_targets(child, out);
            }
        }
        _ => {}
    }
}

fn collect_local_bindings(
    file_id: u32,
    source: &str,
    root: Node<'_>,
    index: &PythonIndex,
    symbol_ranges: &[(u32, SourceRange)],
) -> HashMap<u32, HashSet<String>> {
    let mut bindings: HashMap<u32, HashSet<String>> = HashMap::new();

    for symbol in index
        .symbols
        .iter()
        .filter(|symbol| symbol.file_id == file_id)
    {
        if let Some(parent_symbol_id) = symbol.parent_symbol_id {
            bindings
                .entry(parent_symbol_id)
                .or_default()
                .insert(symbol.name.clone());
        }
    }

    collect_local_bindings_from_node(source, root, symbol_ranges, &mut bindings);
    bindings
}

fn collect_local_bindings_from_node(
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    bindings: &mut HashMap<u32, HashSet<String>>,
) {
    match node.kind() {
        "parameters" => {
            if let Some(source_symbol_id) =
                innermost_symbol_for_range(symbol_ranges, node.range().into())
            {
                let mut targets = Vec::new();
                collect_parameter_targets(node, &mut targets);
                push_local_binding_names(source, source_symbol_id, targets, bindings);
            }
            return;
        }
        "assignment" | "annotated_assignment" | "augmented_assignment" => {
            if let Some(left) = node.child_by_field_name("left") {
                push_local_binding_targets(source, left, symbol_ranges, bindings);
            }
            return;
        }
        "for_statement" => {
            if let Some(left) = node.child_by_field_name("left") {
                push_local_binding_targets(source, left, symbol_ranges, bindings);
            }
        }
        "with_statement" => {
            if let Some(with_clause) = first_child_of_kind(node, &["with_clause"]) {
                push_as_pattern_binding_targets(source, with_clause, symbol_ranges, bindings);
            }
        }
        "except_clause" => {
            if let Some(alias) = node.child_by_field_name("alias") {
                push_local_binding_targets(source, alias, symbol_ranges, bindings);
            }
            if let Some(value) = node.child_by_field_name("value") {
                push_as_pattern_binding_targets(source, value, symbol_ranges, bindings);
            }
        }
        "import_statement" | "import_from_statement" | "future_import_statement" => {
            if let Some(source_symbol_id) =
                innermost_symbol_for_range(symbol_ranges, node.range().into())
            {
                for binding in local_import_binding_names(source, node) {
                    bindings
                        .entry(source_symbol_id)
                        .or_default()
                        .insert(binding);
                }
            }
            return;
        }
        _ => {}
    }

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_local_bindings_from_node(source, child, symbol_ranges, bindings);
    }
}

fn push_local_binding_targets(
    source: &str,
    target_root: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    bindings: &mut HashMap<u32, HashSet<String>>,
) {
    if let Some(source_symbol_id) =
        innermost_symbol_for_range(symbol_ranges, target_root.range().into())
    {
        let mut targets = Vec::new();
        collect_assignment_targets(target_root, &mut targets);
        push_local_binding_names(source, source_symbol_id, targets, bindings);
    }
}

fn push_as_pattern_binding_targets(
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    bindings: &mut HashMap<u32, HashSet<String>>,
) {
    let mut targets = Vec::new();
    collect_as_pattern_alias_targets(node, &mut targets);
    for target in targets {
        push_local_binding_targets(source, target, symbol_ranges, bindings);
    }
}

fn collect_as_pattern_alias_targets<'tree>(node: Node<'tree>, out: &mut Vec<Node<'tree>>) {
    if node.kind() == "as_pattern" {
        if let Some(alias) = node.child_by_field_name("alias") {
            collect_assignment_targets(alias, out);
        }
        return;
    }

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_as_pattern_alias_targets(child, out);
    }
}

fn collect_parameter_targets<'tree>(node: Node<'tree>, out: &mut Vec<Node<'tree>>) {
    match node.kind() {
        "identifier" => out.push(node),
        "typed_parameter" | "default_parameter" | "typed_default_parameter" => {
            if let Some(name) = node.child_by_field_name("name") {
                collect_parameter_targets(name, out);
            } else if let Some(first_child) = first_named_child(node) {
                collect_parameter_targets(first_child, out);
            }
        }
        "list_splat_pattern" | "dictionary_splat_pattern" => {
            if let Some(first_child) = first_named_child(node) {
                collect_parameter_targets(first_child, out);
            }
        }
        "parameters" => {
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                collect_parameter_targets(child, out);
            }
        }
        _ => {}
    }
}

fn push_local_binding_names(
    source: &str,
    source_symbol_id: u32,
    targets: Vec<Node<'_>>,
    bindings: &mut HashMap<u32, HashSet<String>>,
) {
    for target in targets {
        let Ok(name) = target.utf8_text(source.as_bytes()) else {
            continue;
        };
        bindings
            .entry(source_symbol_id)
            .or_default()
            .insert(name.to_owned());
    }
}

fn local_import_binding_names(source: &str, node: Node<'_>) -> Vec<String> {
    match node.kind() {
        "import_statement" => plain_import_binding_names(node_text(source, node)),
        "import_from_statement" | "future_import_statement" => {
            from_import_binding_names(node_text(source, node))
        }
        _ => Vec::new(),
    }
}

fn plain_import_binding_names(text: &str) -> Vec<String> {
    text.trim()
        .trim_start_matches("import")
        .split(',')
        .map(str::trim)
        .filter(|part| !part.is_empty())
        .filter_map(|part| {
            let (name, alias) = split_alias(part);
            alias
                .map(str::to_owned)
                .or_else(|| name.split('.').next().map(str::to_owned))
        })
        .collect()
}

fn from_import_binding_names(text: &str) -> Vec<String> {
    let stripped = text.trim();
    let Some(after_from) = stripped.strip_prefix("from ") else {
        return Vec::new();
    };
    let Some((_, names)) = after_from.split_once(" import ") else {
        return Vec::new();
    };
    names
        .split(',')
        .map(str::trim)
        .filter(|part| !part.is_empty() && *part != "*")
        .map(|part| {
            let (name, alias) = split_alias(part);
            alias.unwrap_or(name).to_owned()
        })
        .collect()
}

fn collect_identifier_candidates(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    excluded_ranges: &[SourceRange],
    out: &mut Vec<ReferenceCandidate>,
) {
    if matches!(
        node.kind(),
        "import_statement" | "import_from_statement" | "future_import_statement"
    ) {
        return;
    }

    let range = node.range().into();
    if node.kind() == "identifier" && !range_matches_any(range, excluded_ranges) {
        if let Ok(name) = node.utf8_text(source.as_bytes()) {
            let source_symbol_id = innermost_symbol_for_range(symbol_ranges, range);
            if is_shadowed_local_binding(source_symbol_id, name, local_bindings_by_symbol_id) {
                return;
            }
            out.push(ReferenceCandidate {
                source_file_id: file_id,
                source_symbol_id,
                name: name.to_owned(),
                range,
            });
        }
    }

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_identifier_candidates(
            file_id,
            source,
            child,
            symbol_ranges,
            local_bindings_by_symbol_id,
            excluded_ranges,
            out,
        );
    }
}

fn is_shadowed_local_binding(
    source_symbol_id: Option<u32>,
    name: &str,
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
) -> bool {
    source_symbol_id
        .and_then(|symbol_id| local_bindings_by_symbol_id.get(&symbol_id))
        .is_some_and(|bindings| bindings.contains(name))
}

fn innermost_symbol_for_range(
    symbol_ranges: &[(u32, SourceRange)],
    range: SourceRange,
) -> Option<u32> {
    symbol_ranges
        .iter()
        .filter(|(_, symbol_range)| contains_range(*symbol_range, range))
        .min_by_key(|(_, symbol_range)| symbol_range.end_byte - symbol_range.start_byte)
        .map(|(symbol_id, _)| *symbol_id)
}

fn contains_range(container: SourceRange, range: SourceRange) -> bool {
    container.start_byte <= range.start_byte && range.end_byte <= container.end_byte
}

fn range_matches_any(range: SourceRange, others: &[SourceRange]) -> bool {
    others
        .iter()
        .any(|other| range.start_byte == other.start_byte && range.end_byte == other.end_byte)
}

fn push_import_statement(file_id: u32, source: &str, node: Node<'_>, index: &mut PythonIndex) {
    let text = node_text(source, node);
    let imports = text
        .trim_start_matches("import")
        .split(',')
        .map(str::trim)
        .filter(|part| !part.is_empty());

    for import in imports {
        let (name, alias) = split_alias(import);
        index.imports.push(ImportRecord {
            id: index.imports.len() as u32,
            file_id,
            kind: ImportKind::Import,
            module: None,
            name: Some(name.to_owned()),
            alias: alias.map(str::to_owned),
            range: node.range().into(),
        });
    }
}

fn push_from_import_statement(file_id: u32, source: &str, node: Node<'_>, index: &mut PythonIndex) {
    let text = node_text(source, node);
    let stripped = text.trim();
    let kind = if node.kind() == "future_import_statement" {
        ImportKind::FutureImport
    } else {
        ImportKind::FromImport
    };
    let Some(after_from) = stripped.strip_prefix("from ") else {
        return;
    };
    let Some((module, names)) = after_from.split_once(" import ") else {
        return;
    };

    for import in names
        .split(',')
        .map(str::trim)
        .filter(|part| !part.is_empty())
    {
        let (name, alias) = split_alias(import);
        index.imports.push(ImportRecord {
            id: index.imports.len() as u32,
            file_id,
            kind,
            module: Some(module.trim().to_owned()),
            name: Some(name.to_owned()),
            alias: alias.map(str::to_owned),
            range: node.range().into(),
        });
    }
}

fn first_child_of_kind<'tree>(node: Node<'tree>, kinds: &[&str]) -> Option<Node<'tree>> {
    let mut cursor = node.walk();
    let child = node
        .named_children(&mut cursor)
        .find(|child| kinds.iter().any(|kind| child.kind() == *kind));
    child
}

fn first_named_child(node: Node<'_>) -> Option<Node<'_>> {
    let mut cursor = node.walk();
    let child = node.named_children(&mut cursor).next();
    child
}

fn split_alias(import: &str) -> (&str, Option<&str>) {
    if let Some((name, alias)) = import.split_once(" as ") {
        (name.trim(), Some(alias.trim()))
    } else {
        (import.trim(), None)
    }
}

fn node_text<'source>(source: &'source str, node: Node<'_>) -> &'source str {
    &source[node.start_byte()..node.end_byte()]
}

fn line_count(source: &str) -> usize {
    if source.is_empty() {
        0
    } else {
        source
            .as_bytes()
            .iter()
            .filter(|byte| **byte == b'\n')
            .count()
            + usize::from(!source.ends_with('\n'))
    }
}

fn resolve_python_imports(index: &mut PythonIndex) {
    let module_to_file: HashMap<&str, u32> = index
        .files
        .iter()
        .filter_map(|file| file.module_name.as_deref().map(|module| (module, file.id)))
        .collect();
    let symbol_to_id: HashMap<(u32, &str), u32> = index
        .symbols
        .iter()
        .filter(|symbol| symbol.is_top_level)
        .map(|symbol| ((symbol.file_id, symbol.name.as_str()), symbol.id))
        .collect();

    let mut resolutions = Vec::new();
    for import in &index.imports {
        let Some(source_file) = index.files.get(import.file_id as usize) else {
            continue;
        };
        let resolution = match import.kind {
            ImportKind::Import => {
                resolve_plain_import(import, &module_to_file).map(|target_file_id| {
                    ImportResolutionRecord {
                        id: resolutions.len() as u32,
                        import_id: import.id,
                        source_file_id: import.file_id,
                        target_file_id,
                        target_symbol_id: None,
                    }
                })
            }
            ImportKind::FromImport | ImportKind::FutureImport => resolve_from_import(
                import,
                source_file,
                &module_to_file,
                &symbol_to_id,
                resolutions.len() as u32,
            ),
        };
        if let Some(resolution) = resolution {
            resolutions.push(resolution);
        }
    }
    index.import_resolutions = resolutions;
}

fn resolve_python_references(index: &mut PythonIndex, candidates: Vec<ReferenceCandidate>) {
    let symbol_to_id: HashMap<(u32, &str), u32> = index
        .symbols
        .iter()
        .filter(|symbol| symbol.is_top_level)
        .map(|symbol| ((symbol.file_id, symbol.name.as_str()), symbol.id))
        .collect();
    let resolution_by_import_id: HashMap<u32, &ImportResolutionRecord> = index
        .import_resolutions
        .iter()
        .map(|resolution| (resolution.import_id, resolution))
        .collect();
    let mut imported_symbol_by_binding: HashMap<(u32, String), (u32, u32)> = HashMap::new();

    for import in &index.imports {
        let Some(resolution) = resolution_by_import_id.get(&import.id) else {
            continue;
        };
        let Some(target_symbol_id) = resolution.target_symbol_id else {
            continue;
        };
        let Some(binding) = import_binding_name(import) else {
            continue;
        };
        imported_symbol_by_binding.insert((import.file_id, binding), (target_symbol_id, import.id));
    }

    let mut references = Vec::new();
    for candidate in candidates {
        let imported_target = imported_symbol_by_binding
            .get(&(candidate.source_file_id, candidate.name.clone()))
            .copied();
        let same_file_target = symbol_to_id
            .get(&(candidate.source_file_id, candidate.name.as_str()))
            .copied()
            .map(|symbol_id| (symbol_id, None));
        let Some((target_symbol_id, import_id)) = imported_target
            .map(|(symbol_id, import_id)| (symbol_id, Some(import_id)))
            .or(same_file_target)
        else {
            continue;
        };
        if candidate.source_symbol_id == Some(target_symbol_id) {
            continue;
        }

        references.push(ReferenceRecord {
            id: references.len() as u32,
            source_file_id: candidate.source_file_id,
            source_symbol_id: candidate.source_symbol_id,
            target_symbol_id,
            import_id,
            name: candidate.name,
            range: candidate.range,
        });
    }
    index.references = references;
}

fn build_python_dependencies(index: &mut PythonIndex) {
    let symbol_file_ids: HashMap<u32, u32> = index
        .symbols
        .iter()
        .map(|symbol| (symbol.id, symbol.file_id))
        .collect();
    let mut dependency_reference_ids: BTreeMap<(u32, u32), Vec<u32>> = BTreeMap::new();

    for reference in &index.references {
        let Some(source_symbol_id) = reference.source_symbol_id else {
            continue;
        };
        dependency_reference_ids
            .entry((source_symbol_id, reference.target_symbol_id))
            .or_default()
            .push(reference.id);
    }

    let dependencies = dependency_reference_ids
        .into_iter()
        .filter_map(|((source_symbol_id, target_symbol_id), reference_ids)| {
            let source_file_id = symbol_file_ids.get(&source_symbol_id).copied()?;
            let target_file_id = symbol_file_ids.get(&target_symbol_id).copied()?;
            Some(DependencyRecord {
                id: 0,
                source_symbol_id,
                target_symbol_id,
                source_file_id,
                target_file_id,
                reference_count: reference_ids.len(),
                reference_ids,
            })
        })
        .enumerate()
        .map(|(id, mut dependency)| {
            dependency.id = id as u32;
            dependency
        })
        .collect();

    index.dependencies = dependencies;
}

fn import_binding_name(import: &ImportRecord) -> Option<String> {
    if let Some(alias) = import.alias.as_deref() {
        return Some(alias.to_owned());
    }
    match import.kind {
        ImportKind::Import => import
            .name
            .as_deref()
            .and_then(|name| name.split('.').next())
            .map(str::to_owned),
        ImportKind::FromImport | ImportKind::FutureImport => import.name.clone(),
    }
}

fn resolve_plain_import(import: &ImportRecord, module_to_file: &HashMap<&str, u32>) -> Option<u32> {
    let name = import.name.as_deref()?;
    module_to_file.get(name).copied()
}

fn resolve_from_import(
    import: &ImportRecord,
    source_file: &FileRecord,
    module_to_file: &HashMap<&str, u32>,
    symbol_to_id: &HashMap<(u32, &str), u32>,
    resolution_id: u32,
) -> Option<ImportResolutionRecord> {
    let module = import.module.as_deref()?;
    let resolved_module = resolve_module_name(source_file, module)?;
    let import_name = import.name.as_deref();

    if let Some(target_file_id) = module_to_file.get(resolved_module.as_str()).copied() {
        let target_symbol_id =
            import_name.and_then(|name| symbol_to_id.get(&(target_file_id, name)).copied());
        if target_symbol_id.is_some() || import_name == Some("*") {
            return Some(ImportResolutionRecord {
                id: resolution_id,
                import_id: import.id,
                source_file_id: import.file_id,
                target_file_id,
                target_symbol_id,
            });
        }
    }

    let import_name = import_name?;
    let child_module = join_module(&resolved_module, import_name);
    if let Some(target_file_id) = module_to_file.get(child_module.as_str()).copied() {
        return Some(ImportResolutionRecord {
            id: resolution_id,
            import_id: import.id,
            source_file_id: import.file_id,
            target_file_id,
            target_symbol_id: None,
        });
    }

    module_to_file
        .get(resolved_module.as_str())
        .copied()
        .map(|target_file_id| ImportResolutionRecord {
            id: resolution_id,
            import_id: import.id,
            source_file_id: import.file_id,
            target_file_id,
            target_symbol_id: None,
        })
}

fn resolve_module_name(source_file: &FileRecord, raw_module: &str) -> Option<String> {
    if !raw_module.starts_with('.') {
        return Some(raw_module.to_owned());
    }

    let dot_count = raw_module
        .as_bytes()
        .iter()
        .take_while(|byte| **byte == b'.')
        .count();
    let suffix = &raw_module[dot_count..];
    let mut package_parts = source_package_name(source_file)
        .map(|package| {
            package
                .split('.')
                .filter(|part| !part.is_empty())
                .map(str::to_owned)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let ascend = dot_count.saturating_sub(1);
    if ascend > package_parts.len() {
        return None;
    }
    let keep = package_parts.len() - ascend;
    package_parts.truncate(keep);
    if !suffix.is_empty() {
        package_parts.extend(
            suffix
                .split('.')
                .filter(|part| !part.is_empty())
                .map(str::to_owned),
        );
    }
    Some(package_parts.join("."))
}

fn source_package_name(file: &FileRecord) -> Option<&str> {
    let module = file.module_name.as_deref()?;
    if file.path.ends_with("/__init__.py") || file.path == "__init__.py" {
        Some(module)
    } else {
        module.rsplit_once('.').map(|(package, _)| package)
    }
}

fn join_module(parent: &str, child: &str) -> String {
    if parent.is_empty() {
        child.to_owned()
    } else {
        format!("{parent}.{child}")
    }
}

fn python_module_name(path: &str) -> Option<String> {
    let without_suffix = path.strip_suffix(".py")?;
    let module = without_suffix
        .strip_suffix("/__init__")
        .unwrap_or(without_suffix)
        .split('/')
        .filter(|part| !part.is_empty())
        .collect::<Vec<_>>()
        .join(".");
    if module.is_empty() {
        None
    } else {
        Some(module)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn debug_info_reports_version_and_python_index_feature() {
        let info = Engine::new().debug_info();

        assert_eq!(info.version(), env!("CARGO_PKG_VERSION"));
        assert_eq!(info.enabled_features(), ["skeleton", "python-index"]);
    }

    #[test]
    fn indexes_python_files_without_materializing_python_objects() {
        let repo = temp_repo_path("index-python");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(
            repo.join("pkg/mod.py"),
            "from __future__ import annotations\nfrom .base import Base as RenamedBase\nimport os, sys as system\n\n@decorator\nclass Service(RenamedBase):\n    pass\n\ndef helper(value):\n    return value\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 1);
        assert_eq!(index.summary().classes, 1);
        assert_eq!(index.summary().functions, 1);
        assert_eq!(index.summary().global_variables, 0);
        assert_eq!(index.summary().imports, 4);
        assert_eq!(index.summary().import_resolutions, 0);
        assert_eq!(index.summary().references, 0);
        assert_eq!(index.summary().dependencies, 0);
        assert_eq!(index.symbols[0].name, "Service");
        assert_eq!(index.symbols[0].parent_symbol_id, None);
        assert!(index.symbols[0].is_top_level);
        assert_eq!(index.symbols[1].name, "helper");
        assert_eq!(index.symbols[1].parent_symbol_id, None);
        assert!(index.symbols[1].is_top_level);
        assert!(index
            .imports
            .iter()
            .any(|import| import.module.as_deref() == Some(".base")));
        assert!(index
            .imports
            .iter()
            .any(|import| import.alias.as_deref() == Some("system")));
    }

    #[test]
    fn indexes_only_requested_python_paths() {
        let repo = temp_repo_path("index-python-paths");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(repo.join("pkg/included.py"), "class Included:\n    pass\n").unwrap();
        fs::write(repo.join("pkg/skipped.py"), "class Skipped:\n    pass\n").unwrap();

        let index = index_python_paths(&repo, ["pkg/included.py"]).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 1);
        assert_eq!(index.files[0].path, "pkg/included.py");
        assert_eq!(index.summary().classes, 1);
        assert_eq!(index.symbols[0].name, "Included");
    }

    #[test]
    fn resolves_internal_python_imports_to_files_and_symbols() {
        let repo = temp_repo_path("resolve-python-imports");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(repo.join("pkg/__init__.py"), "").unwrap();
        fs::write(
            repo.join("pkg/base.py"),
            "CONSTANT = 'base'\nclass Base:\n    pass\n",
        )
        .unwrap();
        fs::write(
            repo.join("pkg/service.py"),
            "from __future__ import annotations\nfrom .base import Base, CONSTANT\nfrom . import base\nimport pkg.base\nimport os\n\nclass Service(Base):\n    pass\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 3);
        assert_eq!(index.summary().classes, 2);
        assert_eq!(index.summary().global_variables, 1);
        assert_eq!(index.summary().imports, 6);
        assert_eq!(index.summary().import_resolutions, 4);
        assert_eq!(index.summary().references, 1);
        assert_eq!(index.summary().dependencies, 1);

        let base_file_id = index
            .files
            .iter()
            .find(|file| file.path == "pkg/base.py")
            .unwrap()
            .id;
        let base_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == base_file_id && symbol.name == "Base")
            .unwrap()
            .id;
        let constant_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == base_file_id && symbol.name == "CONSTANT")
            .unwrap()
            .id;
        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.target_file_id == base_file_id
                && resolution.target_symbol_id == Some(base_symbol_id)
        }));
        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.target_file_id == base_file_id
                && resolution.target_symbol_id == Some(constant_symbol_id)
        }));
        assert_eq!(
            index
                .import_resolutions
                .iter()
                .filter(|resolution| resolution.target_file_id == base_file_id)
                .count(),
            4
        );
        assert!(index.references.iter().any(|reference| {
            reference.name == "Base"
                && reference.source_symbol_id.is_some()
                && reference.target_symbol_id == base_symbol_id
                && reference.import_id.is_some()
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.target_symbol_id == base_symbol_id
                && dependency.reference_count == 1
                && dependency.reference_ids == vec![0]
        }));
    }

    #[test]
    fn attributes_references_to_innermost_python_symbol() {
        let repo = temp_repo_path("nested-python-reference-sources");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(repo.join("pkg/__init__.py"), "").unwrap();
        fs::write(
            repo.join("pkg/base.py"),
            "class Base:\n    pass\n\ndef helper():\n    return Base\n",
        )
        .unwrap();
        fs::write(
            repo.join("pkg/service.py"),
            "from .base import Base, helper\n\nclass Service(Base):\n    def run(self):\n        return helper()\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        let service = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "Service")
            .unwrap();
        let run = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "run")
            .unwrap();
        let helper = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "helper")
            .unwrap();
        let base = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "Base")
            .unwrap();

        assert!(service.is_top_level);
        assert!(!run.is_top_level);
        assert_eq!(run.parent_symbol_id, Some(service.id));
        assert!(index.references.iter().any(|reference| {
            reference.name == "Base"
                && reference.source_symbol_id == Some(service.id)
                && reference.target_symbol_id == base.id
        }));
        assert!(index.references.iter().any(|reference| {
            reference.name == "helper"
                && reference.source_symbol_id == Some(run.id)
                && reference.target_symbol_id == helper.id
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == run.id && dependency.target_symbol_id == helper.id
        }));
    }

    #[test]
    fn skips_references_shadowed_by_python_parameters_and_locals() {
        let repo = temp_repo_path("python-shadowed-reference-sources");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(repo.join("pkg/__init__.py"), "").unwrap();
        fs::write(
            repo.join("pkg/base.py"),
            "class Base:\n    pass\n\ndef helper():\n    return Base\n",
        )
        .unwrap();
        fs::write(
            repo.join("pkg/service.py"),
            "from .base import Base, helper\n\n\
other = object()\n\n\
Error = Exception\n\n\
def shadowed(Base):\n    helper = Base\n    return helper, Base\n\n\
def import_shadowed():\n    import other.module\n    import other.module as helper\n    from other import Base\n    return helper, Base, other\n\n\
def control_flow_shadowed(items, manager):\n    for Base, helper in items:\n        pass\n    with manager as other:\n        pass\n    try:\n        pass\n    except Error as helper:\n        return Base, helper, other\n\n\
def caller():\n    return helper()\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        let shadowed = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "shadowed")
            .unwrap();
        let caller = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "caller")
            .unwrap();
        let import_shadowed = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "import_shadowed")
            .unwrap();
        let control_flow_shadowed = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "control_flow_shadowed")
            .unwrap();
        let helper = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "helper")
            .unwrap();
        let other = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "other")
            .unwrap();
        let base = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "Base")
            .unwrap();
        let error = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "Error")
            .unwrap();

        assert!(!index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(shadowed.id)
                && (reference.target_symbol_id == base.id
                    || reference.target_symbol_id == helper.id)
        }));
        assert!(!index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(import_shadowed.id)
                && (reference.target_symbol_id == base.id
                    || reference.target_symbol_id == helper.id
                    || reference.target_symbol_id == other.id)
        }));
        assert!(!index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(control_flow_shadowed.id)
                && (reference.target_symbol_id == base.id
                    || reference.target_symbol_id == helper.id
                    || reference.target_symbol_id == other.id)
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(control_flow_shadowed.id)
                && reference.name == "Error"
                && reference.target_symbol_id == error.id
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(caller.id)
                && reference.name == "helper"
                && reference.target_symbol_id == helper.id
        }));
    }

    #[test]
    fn compact_python_graph_snapshot_is_stable() {
        let repo = temp_repo_path("compact-python-graph-snapshot");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(repo.join("pkg/__init__.py"), "").unwrap();
        fs::write(
            repo.join("pkg/base.py"),
            "CONSTANT = 'base'\nclass Base:\n    pass\n",
        )
        .unwrap();
        fs::write(
            repo.join("pkg/service.py"),
            "from .base import Base, CONSTANT\nfrom . import base\nimport pkg.base\nimport os\n\nclass Service(Base):\n    pass\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        let files = index
            .files
            .iter()
            .map(|file| {
                serde_json::json!({
                    "id": file.id,
                    "path": file.path,
                    "module_name": file.module_name,
                })
            })
            .collect::<Vec<_>>();
        let symbols = index
            .symbols
            .iter()
            .map(|symbol| {
                serde_json::json!({
                    "id": symbol.id,
                    "file_id": symbol.file_id,
                    "parent_symbol_id": symbol.parent_symbol_id,
                    "is_top_level": symbol.is_top_level,
                    "name": symbol.name,
                    "kind": symbol.kind,
                })
            })
            .collect::<Vec<_>>();
        let imports = index
            .imports
            .iter()
            .map(|import| {
                serde_json::json!({
                    "id": import.id,
                    "file_id": import.file_id,
                    "kind": import.kind,
                    "module": import.module,
                    "name": import.name,
                    "alias": import.alias,
                })
            })
            .collect::<Vec<_>>();
        let references = index
            .references
            .iter()
            .map(|reference| {
                serde_json::json!({
                    "id": reference.id,
                    "source_file_id": reference.source_file_id,
                    "source_symbol_id": reference.source_symbol_id,
                    "target_symbol_id": reference.target_symbol_id,
                    "import_id": reference.import_id,
                    "name": reference.name,
                })
            })
            .collect::<Vec<_>>();
        let dependencies = index
            .dependencies
            .iter()
            .map(|dependency| {
                serde_json::json!({
                    "id": dependency.id,
                    "source_symbol_id": dependency.source_symbol_id,
                    "target_symbol_id": dependency.target_symbol_id,
                    "source_file_id": dependency.source_file_id,
                    "target_file_id": dependency.target_file_id,
                    "reference_ids": dependency.reference_ids,
                    "reference_count": dependency.reference_count,
                })
            })
            .collect::<Vec<_>>();

        assert_eq!(
            serde_json::json!({
                "files": files,
                "symbols": symbols,
                "imports": imports,
                "import_resolutions": index.import_resolutions,
                "references": references,
                "dependencies": dependencies,
            }),
            serde_json::json!({
                "files": [
                    {"id": 0, "path": "pkg/__init__.py", "module_name": "pkg"},
                    {"id": 1, "path": "pkg/base.py", "module_name": "pkg.base"},
                    {"id": 2, "path": "pkg/service.py", "module_name": "pkg.service"}
                ],
                "symbols": [
                    {"id": 0, "file_id": 1, "parent_symbol_id": null, "is_top_level": true, "name": "CONSTANT", "kind": "global_variable"},
                    {"id": 1, "file_id": 1, "parent_symbol_id": null, "is_top_level": true, "name": "Base", "kind": "class"},
                    {"id": 2, "file_id": 2, "parent_symbol_id": null, "is_top_level": true, "name": "Service", "kind": "class"}
                ],
                "imports": [
                    {"id": 0, "file_id": 2, "kind": "from_import", "module": ".base", "name": "Base", "alias": null},
                    {"id": 1, "file_id": 2, "kind": "from_import", "module": ".base", "name": "CONSTANT", "alias": null},
                    {"id": 2, "file_id": 2, "kind": "from_import", "module": ".", "name": "base", "alias": null},
                    {"id": 3, "file_id": 2, "kind": "import", "module": null, "name": "pkg.base", "alias": null},
                    {"id": 4, "file_id": 2, "kind": "import", "module": null, "name": "os", "alias": null}
                ],
                "import_resolutions": [
                    {"id": 0, "import_id": 0, "source_file_id": 2, "target_file_id": 1, "target_symbol_id": 1},
                    {"id": 1, "import_id": 1, "source_file_id": 2, "target_file_id": 1, "target_symbol_id": 0},
                    {"id": 2, "import_id": 2, "source_file_id": 2, "target_file_id": 1, "target_symbol_id": null},
                    {"id": 3, "import_id": 3, "source_file_id": 2, "target_file_id": 1, "target_symbol_id": null}
                ],
                "references": [
                    {"id": 0, "source_file_id": 2, "source_symbol_id": 2, "target_symbol_id": 1, "import_id": 0, "name": "Base"}
                ],
                "dependencies": [
                    {"id": 0, "source_symbol_id": 2, "target_symbol_id": 1, "source_file_id": 2, "target_file_id": 1, "reference_ids": [0], "reference_count": 1}
                ]
            })
        );
    }

    fn temp_repo_path(prefix: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("graph-sitter-{prefix}-{nanos}"))
    }
}
