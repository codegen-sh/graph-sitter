#![forbid(unsafe_code)]

use serde::{Serialize, Serializer};
use std::borrow::Borrow;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::fmt;
use std::fs;
use std::io;
use std::ops::Deref;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tree_sitter::{Node, Parser, Range, Tree};

const ENABLED_FEATURES: &[&str] = &["skeleton", "python-index", "typescript-index"];

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct InternedString(Arc<str>);

impl InternedString {
    pub fn ptr_eq(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.0, &other.0)
    }
}

impl From<&str> for InternedString {
    fn from(value: &str) -> Self {
        Self(Arc::from(value))
    }
}

impl From<String> for InternedString {
    fn from(value: String) -> Self {
        Self(Arc::from(value))
    }
}

impl AsRef<str> for InternedString {
    fn as_ref(&self) -> &str {
        &self.0
    }
}

impl Borrow<str> for InternedString {
    fn borrow(&self) -> &str {
        self.as_ref()
    }
}

impl Deref for InternedString {
    type Target = str;

    fn deref(&self) -> &Self::Target {
        self.as_ref()
    }
}

impl fmt::Display for InternedString {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(self.as_ref())
    }
}

impl PartialEq<&str> for InternedString {
    fn eq(&self, other: &&str) -> bool {
        self.as_ref() == *other
    }
}

impl PartialEq<InternedString> for &str {
    fn eq(&self, other: &InternedString) -> bool {
        *self == other.as_ref()
    }
}

impl Serialize for InternedString {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(self.as_ref())
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct StringInterner {
    values: HashSet<InternedString>,
}

impl StringInterner {
    pub fn intern(&mut self, value: impl AsRef<str>) -> InternedString {
        let value = value.as_ref();
        if let Some(existing) = self.values.get(value) {
            return existing.clone();
        }
        let interned = InternedString::from(value);
        self.values.insert(interned.clone());
        interned
    }

    pub fn len(&self) -> usize {
        self.values.len()
    }

    pub fn clear(&mut self) {
        self.values = HashSet::new();
    }
}

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

    pub fn index_typescript_path(
        &self,
        repo_path: impl AsRef<Path>,
    ) -> Result<TypeScriptIndex, IndexError> {
        TypeScriptIndexer::new()?.index_path(repo_path)
    }

    pub fn index_typescript_paths<I, P>(
        &self,
        repo_path: impl AsRef<Path>,
        file_paths: I,
    ) -> Result<TypeScriptIndex, IndexError>
    where
        I: IntoIterator<Item = P>,
        P: AsRef<Path>,
    {
        TypeScriptIndexer::new()?.index_paths(repo_path, file_paths)
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

pub fn index_typescript_path(repo_path: impl AsRef<Path>) -> Result<TypeScriptIndex, IndexError> {
    Engine::new().index_typescript_path(repo_path)
}

pub fn index_typescript_paths<I, P>(
    repo_path: impl AsRef<Path>,
    file_paths: I,
) -> Result<TypeScriptIndex, IndexError>
where
    I: IntoIterator<Item = P>,
    P: AsRef<Path>,
{
    Engine::new().index_typescript_paths(repo_path, file_paths)
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
    pub external_modules: Vec<ExternalModuleRecord>,
    pub references: Vec<ReferenceRecord>,
    pub external_references: Vec<ExternalReferenceRecord>,
    pub dependencies: Vec<DependencyRecord>,
    #[serde(skip)]
    pub all_exports_by_file: HashMap<u32, BTreeSet<String>>,
    #[serde(skip)]
    pub strings: StringInterner,
}

impl PythonIndex {
    fn intern(&mut self, value: impl AsRef<str>) -> InternedString {
        self.strings.intern(value)
    }

    fn finish(mut self) -> Self {
        self.all_exports_by_file.clear();
        self.strings.clear();
        self
    }

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
            external_modules: self.external_modules.len(),
            exports: 0,
            references: self.references.len(),
            external_references: self.external_references.len(),
            dependencies: self.dependencies.len(),
            subclass_edges: 0,
            bytes: self.files.iter().map(|file| file.byte_len).sum(),
            lines: self.files.iter().map(|file| file.line_count).sum(),
            files_with_errors: self.files.iter().filter(|file| file.has_error).count(),
        }
    }

    pub fn debug_graph_dump(&self) -> GraphDebugDump {
        let mut nodes = Vec::new();
        let mut edges = Vec::new();
        append_common_debug_graph(
            &mut nodes,
            &mut edges,
            &self.files,
            &self.symbols,
            &self.imports,
            &self.import_resolutions,
            &self.external_modules,
            &self.references,
            &self.external_references,
            &self.dependencies,
        );
        GraphDebugDump { nodes, edges }
    }

    pub fn debug_graph_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string(&self.debug_graph_dump())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TypeScriptIndex {
    pub files: Vec<FileRecord>,
    pub symbols: Vec<SymbolRecord>,
    pub imports: Vec<ImportRecord>,
    pub import_resolutions: Vec<ImportResolutionRecord>,
    pub external_modules: Vec<ExternalModuleRecord>,
    pub exports: Vec<ExportRecord>,
    pub references: Vec<ReferenceRecord>,
    pub external_references: Vec<ExternalReferenceRecord>,
    pub function_calls: Vec<FunctionCallRecord>,
    pub dependencies: Vec<DependencyRecord>,
    pub subclass_edges: Vec<SubclassRecord>,
    #[serde(skip)]
    pub strings: StringInterner,
}

impl TypeScriptIndex {
    fn intern(&mut self, value: impl AsRef<str>) -> InternedString {
        self.strings.intern(value)
    }

    fn finish(mut self) -> Self {
        self.strings.clear();
        self
    }

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
            external_modules: self.external_modules.len(),
            exports: self.exports.len(),
            references: self.references.len(),
            external_references: self.external_references.len(),
            dependencies: self.dependencies.len(),
            subclass_edges: self.subclass_edges.len(),
            bytes: self.files.iter().map(|file| file.byte_len).sum(),
            lines: self.files.iter().map(|file| file.line_count).sum(),
            files_with_errors: self.files.iter().filter(|file| file.has_error).count(),
        }
    }

    pub fn debug_graph_dump(&self) -> GraphDebugDump {
        let mut nodes = Vec::new();
        let mut edges = Vec::new();
        append_common_debug_graph(
            &mut nodes,
            &mut edges,
            &self.files,
            &self.symbols,
            &self.imports,
            &self.import_resolutions,
            &self.external_modules,
            &self.references,
            &self.external_references,
            &self.dependencies,
        );

        for export in &self.exports {
            nodes.push(GraphDebugNode {
                id: export_debug_id(export.id),
                node_type: "export",
                record_id: export.id,
                file_id: Some(export.file_id),
                name: export_debug_name(export),
                path: None,
                range: Some(export.range),
            });

            let mut file_edge = debug_edge(
                "contains_export",
                file_debug_id(export.file_id),
                export_debug_id(export.id),
            );
            file_edge.export_id = Some(export.id);
            file_edge.name = export_debug_name(export);
            file_edge.range = Some(export.range);
            edges.push(file_edge);

            if let Some(symbol_id) = export.symbol_id {
                let mut symbol_edge = debug_edge(
                    "export_symbol",
                    export_debug_id(export.id),
                    symbol_debug_id(symbol_id),
                );
                symbol_edge.export_id = Some(export.id);
                symbol_edge.name = export_debug_name(export);
                symbol_edge.range = Some(export.range);
                edges.push(symbol_edge);
            }
            if let Some(import_id) = export.import_id {
                let mut import_edge = debug_edge(
                    "export_import",
                    export_debug_id(export.id),
                    import_debug_id(import_id),
                );
                import_edge.export_id = Some(export.id);
                import_edge.import_id = Some(import_id);
                import_edge.name = export_debug_name(export);
                import_edge.range = Some(export.range);
                edges.push(import_edge);
            }
        }

        for subclass in &self.subclass_edges {
            let mut edge = debug_edge(
                "subclass",
                symbol_debug_id(subclass.source_symbol_id),
                symbol_debug_id(subclass.target_symbol_id),
            );
            edge.subclass_id = Some(subclass.id);
            edge.reference_id = Some(subclass.reference_id);
            edges.push(edge);
        }

        GraphDebugDump { nodes, edges }
    }

    pub fn debug_graph_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string(&self.debug_graph_dump())
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
    pub external_modules: usize,
    pub exports: usize,
    pub references: usize,
    pub external_references: usize,
    pub dependencies: usize,
    pub subclass_edges: usize,
    pub bytes: usize,
    pub lines: usize,
    pub files_with_errors: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct FileRecord {
    pub id: u32,
    pub path: InternedString,
    pub module_name: Option<InternedString>,
    pub language: FileLanguage,
    pub content_hash: String,
    pub byte_len: usize,
    pub line_count: usize,
    pub has_error: bool,
    pub root_range: SourceRange,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum FileLanguage {
    #[serde(rename = "python")]
    Python,
    #[serde(rename = "typescript")]
    TypeScript,
    #[serde(rename = "tsx")]
    Tsx,
    #[serde(rename = "javascript")]
    JavaScript,
    #[serde(rename = "jsx")]
    Jsx,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SymbolKind {
    Class,
    Function,
    GlobalVariable,
    Interface,
    TypeAlias,
    Enum,
    Namespace,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SymbolRecord {
    pub id: u32,
    pub file_id: u32,
    pub parent_symbol_id: Option<u32>,
    pub is_top_level: bool,
    pub name: InternedString,
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
    SideEffect,
    DefaultImport,
    NamedImport,
    NamespaceImport,
    DynamicImport,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ImportRecord {
    pub id: u32,
    pub file_id: u32,
    pub kind: ImportKind,
    pub module: Option<InternedString>,
    pub name: Option<InternedString>,
    pub alias: Option<InternedString>,
    pub range: SourceRange,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ExternalModuleRecord {
    pub id: u32,
    pub import_id: u32,
    pub file_id: u32,
    pub module: Option<InternedString>,
    pub name: InternedString,
    pub alias: Option<InternedString>,
    pub range: SourceRange,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ExportKind {
    Named,
    Default,
    Wildcard,
    Namespace,
    ExportEquals,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ExportRecord {
    pub id: u32,
    pub file_id: u32,
    pub kind: ExportKind,
    pub name: Option<InternedString>,
    pub local_name: Option<InternedString>,
    pub source_module: Option<InternedString>,
    pub symbol_id: Option<u32>,
    pub import_id: Option<u32>,
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
    pub name: InternedString,
    pub range: SourceRange,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ExternalReferenceRecord {
    pub id: u32,
    pub source_file_id: u32,
    pub source_symbol_id: Option<u32>,
    pub import_id: u32,
    pub name: InternedString,
    pub range: SourceRange,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct FunctionCallRecord {
    pub id: u32,
    pub source_file_id: u32,
    pub source_symbol_id: Option<u32>,
    pub target_symbol_id: Option<u32>,
    pub import_id: Option<u32>,
    pub name: InternedString,
    pub range: SourceRange,
    pub name_range: SourceRange,
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

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SubclassRecord {
    pub id: u32,
    pub source_symbol_id: u32,
    pub target_symbol_id: u32,
    pub source_file_id: u32,
    pub target_file_id: u32,
    pub reference_id: u32,
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

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct GraphDebugDump {
    pub nodes: Vec<GraphDebugNode>,
    pub edges: Vec<GraphDebugEdge>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct GraphDebugNode {
    pub id: String,
    pub node_type: &'static str,
    pub record_id: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub file_id: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub range: Option<SourceRange>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct GraphDebugEdge {
    pub edge_type: &'static str,
    pub source: String,
    pub target: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub import_id: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub export_id: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reference_id: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dependency_id: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub subclass_id: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub range: Option<SourceRange>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub reference_ids: Vec<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reference_count: Option<usize>,
}

fn append_common_debug_graph(
    nodes: &mut Vec<GraphDebugNode>,
    edges: &mut Vec<GraphDebugEdge>,
    files: &[FileRecord],
    symbols: &[SymbolRecord],
    imports: &[ImportRecord],
    import_resolutions: &[ImportResolutionRecord],
    external_modules: &[ExternalModuleRecord],
    references: &[ReferenceRecord],
    external_references: &[ExternalReferenceRecord],
    dependencies: &[DependencyRecord],
) {
    for file in files {
        nodes.push(GraphDebugNode {
            id: file_debug_id(file.id),
            node_type: "file",
            record_id: file.id,
            file_id: Some(file.id),
            name: file.module_name.as_ref().map(|name| name.to_string()),
            path: Some(file.path.to_string()),
            range: Some(file.root_range),
        });
    }

    for symbol in symbols {
        nodes.push(GraphDebugNode {
            id: symbol_debug_id(symbol.id),
            node_type: "symbol",
            record_id: symbol.id,
            file_id: Some(symbol.file_id),
            name: Some(symbol.name.to_string()),
            path: None,
            range: Some(symbol.range),
        });

        let mut file_edge = debug_edge(
            "contains_symbol",
            file_debug_id(symbol.file_id),
            symbol_debug_id(symbol.id),
        );
        file_edge.name = Some(symbol.name.to_string());
        file_edge.range = Some(symbol.range);
        edges.push(file_edge);

        if let Some(parent_symbol_id) = symbol.parent_symbol_id {
            let mut parent_edge = debug_edge(
                "parent_symbol",
                symbol_debug_id(parent_symbol_id),
                symbol_debug_id(symbol.id),
            );
            parent_edge.name = Some(symbol.name.to_string());
            parent_edge.range = Some(symbol.range);
            edges.push(parent_edge);
        }
    }

    for import in imports {
        nodes.push(GraphDebugNode {
            id: import_debug_id(import.id),
            node_type: "import",
            record_id: import.id,
            file_id: Some(import.file_id),
            name: import_debug_name(import),
            path: None,
            range: Some(import.range),
        });

        let mut file_edge = debug_edge(
            "contains_import",
            file_debug_id(import.file_id),
            import_debug_id(import.id),
        );
        file_edge.import_id = Some(import.id);
        file_edge.name = import_debug_name(import);
        file_edge.range = Some(import.range);
        edges.push(file_edge);
    }

    let mut external_module_id_by_import_id = BTreeMap::new();
    for external_module in external_modules {
        external_module_id_by_import_id.insert(external_module.import_id, external_module.id);
        nodes.push(GraphDebugNode {
            id: external_module_debug_id(external_module.id),
            node_type: "external_module",
            record_id: external_module.id,
            file_id: Some(external_module.file_id),
            name: Some(external_module.name.to_string()),
            path: None,
            range: Some(external_module.range),
        });

        let mut file_edge = debug_edge(
            "contains_external_module",
            file_debug_id(external_module.file_id),
            external_module_debug_id(external_module.id),
        );
        file_edge.import_id = Some(external_module.import_id);
        file_edge.name = Some(external_module.name.to_string());
        file_edge.range = Some(external_module.range);
        edges.push(file_edge);
    }

    for resolution in import_resolutions {
        let target = resolution
            .target_symbol_id
            .map(symbol_debug_id)
            .unwrap_or_else(|| file_debug_id(resolution.target_file_id));
        let mut edge = debug_edge(
            "import_resolution",
            import_debug_id(resolution.import_id),
            target,
        );
        edge.import_id = Some(resolution.import_id);
        edges.push(edge);
    }

    for reference in references {
        let mut edge = debug_edge(
            "reference",
            source_debug_id(reference.source_symbol_id, reference.source_file_id),
            symbol_debug_id(reference.target_symbol_id),
        );
        edge.import_id = reference.import_id;
        edge.reference_id = Some(reference.id);
        edge.name = Some(reference.name.to_string());
        edge.range = Some(reference.range);
        edges.push(edge);
    }

    for reference in external_references {
        let target = external_module_id_by_import_id
            .get(&reference.import_id)
            .copied()
            .map(external_module_debug_id)
            .unwrap_or_else(|| import_debug_id(reference.import_id));
        let mut edge = debug_edge(
            "external_reference",
            source_debug_id(reference.source_symbol_id, reference.source_file_id),
            target,
        );
        edge.import_id = Some(reference.import_id);
        edge.reference_id = Some(reference.id);
        edge.name = Some(reference.name.to_string());
        edge.range = Some(reference.range);
        edges.push(edge);
    }

    for dependency in dependencies {
        let mut edge = debug_edge(
            "dependency",
            symbol_debug_id(dependency.source_symbol_id),
            symbol_debug_id(dependency.target_symbol_id),
        );
        edge.dependency_id = Some(dependency.id);
        edge.reference_ids = dependency.reference_ids.clone();
        edge.reference_count = Some(dependency.reference_count);
        edges.push(edge);
    }
}

fn debug_edge(edge_type: &'static str, source: String, target: String) -> GraphDebugEdge {
    GraphDebugEdge {
        edge_type,
        source,
        target,
        import_id: None,
        export_id: None,
        reference_id: None,
        dependency_id: None,
        subclass_id: None,
        name: None,
        range: None,
        reference_ids: Vec::new(),
        reference_count: None,
    }
}

fn source_debug_id(symbol_id: Option<u32>, file_id: u32) -> String {
    symbol_id
        .map(symbol_debug_id)
        .unwrap_or_else(|| file_debug_id(file_id))
}

fn file_debug_id(id: u32) -> String {
    format!("file:{id}")
}

fn symbol_debug_id(id: u32) -> String {
    format!("symbol:{id}")
}

fn import_debug_id(id: u32) -> String {
    format!("import:{id}")
}

fn external_module_debug_id(id: u32) -> String {
    format!("external_module:{id}")
}

fn export_debug_id(id: u32) -> String {
    format!("export:{id}")
}

fn import_debug_name(import: &ImportRecord) -> Option<String> {
    import
        .alias
        .as_ref()
        .or(import.name.as_ref())
        .or(import.module.as_ref())
        .map(|value| value.to_string())
}

fn export_debug_name(export: &ExportRecord) -> Option<String> {
    export
        .name
        .as_ref()
        .or(export.local_name.as_ref())
        .or(export.source_module.as_ref())
        .map(|value| value.to_string())
}

struct PythonIndexer {
    parser: Parser,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ReferenceCandidate {
    source_file_id: u32,
    source_symbol_id: Option<u32>,
    name: String,
    qualifier: Option<String>,
    range: SourceRange,
    is_subclass: bool,
    call_range: Option<SourceRange>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct LocalBindingScope {
    source_symbol_id: u32,
    range: SourceRange,
    names: HashSet<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct IndexedLocalSymbol {
    id: u32,
    name_range: SourceRange,
}

#[derive(Debug, Clone, Default)]
struct IndexedLocalSymbols {
    parent_symbol_by_id: HashMap<u32, u32>,
    symbols_by_parent_and_name: HashMap<(u32, String), Vec<IndexedLocalSymbol>>,
}

impl IndexedLocalSymbols {
    fn from_symbols<'a>(symbols: impl IntoIterator<Item = &'a SymbolRecord>) -> Self {
        let mut index = Self::default();
        for symbol in symbols {
            if let Some(parent_symbol_id) = symbol.parent_symbol_id {
                index
                    .parent_symbol_by_id
                    .insert(symbol.id, parent_symbol_id);
                index
                    .symbols_by_parent_and_name
                    .entry((parent_symbol_id, symbol.name.to_string()))
                    .or_default()
                    .push(IndexedLocalSymbol {
                        id: symbol.id,
                        name_range: symbol.name_range,
                    });
            }
        }
        for symbols in index.symbols_by_parent_and_name.values_mut() {
            symbols.sort_by_key(|symbol| symbol.name_range.start_byte);
        }
        index
    }
}

type ExportedSymbolsByFile = HashMap<u32, BTreeMap<String, u32>>;

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
            external_modules: Vec::new(),
            references: Vec::new(),
            external_references: Vec::new(),
            dependencies: Vec::new(),
            all_exports_by_file: HashMap::new(),
            strings: StringInterner::default(),
        };
        let mut reference_candidates = Vec::new();
        paths.sort();

        for path in paths {
            let file_id = index.files.len() as u32;
            let (content, byte_len, content_hash) = read_source_lossy(&path)?;
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

            let module_name = python_module_name(&relative_path).map(|name| index.intern(name));
            let relative_path = index.intern(relative_path);
            index.files.push(FileRecord {
                id: file_id,
                module_name,
                path: relative_path,
                language: FileLanguage::Python,
                content_hash,
                byte_len,
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
        Ok(index.finish())
    }
}

struct TypeScriptIndexer {
    parser: Parser,
}

impl TypeScriptIndexer {
    fn new() -> Result<Self, IndexError> {
        let mut parser = Parser::new();
        parser.set_language(&tree_sitter_typescript::LANGUAGE_TSX.into())?;
        Ok(Self { parser })
    }

    fn index_path(mut self, repo_path: impl AsRef<Path>) -> Result<TypeScriptIndex, IndexError> {
        let repo_path = repo_path.as_ref();
        let mut paths = Vec::new();
        collect_typescript_files(repo_path, &mut paths)?;
        self.index_absolute_paths(repo_path, paths)
    }

    fn index_paths<I, P>(
        mut self,
        repo_path: impl AsRef<Path>,
        file_paths: I,
    ) -> Result<TypeScriptIndex, IndexError>
    where
        I: IntoIterator<Item = P>,
        P: AsRef<Path>,
    {
        let repo_path = repo_path.as_ref();
        let paths = file_paths
            .into_iter()
            .filter_map(|path| {
                let path = path.as_ref();
                let absolute_path = if path.is_absolute() {
                    path.to_path_buf()
                } else {
                    repo_path.join(path)
                };
                is_typescript_like_file(&absolute_path).then_some(absolute_path)
            })
            .collect();
        self.index_absolute_paths(repo_path, paths)
    }

    fn index_absolute_paths(
        &mut self,
        repo_path: &Path,
        mut paths: Vec<PathBuf>,
    ) -> Result<TypeScriptIndex, IndexError> {
        let mut index = TypeScriptIndex {
            files: Vec::new(),
            symbols: Vec::new(),
            imports: Vec::new(),
            import_resolutions: Vec::new(),
            external_modules: Vec::new(),
            exports: Vec::new(),
            references: Vec::new(),
            external_references: Vec::new(),
            function_calls: Vec::new(),
            dependencies: Vec::new(),
            subclass_edges: Vec::new(),
            strings: StringInterner::default(),
        };
        let mut reference_candidates = Vec::new();
        paths.sort();
        let ts_configs = collect_typescript_configs(repo_path);

        for path in paths {
            let file_id = index.files.len() as u32;
            let (content, byte_len, content_hash) = read_source_lossy(&path)?;
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

            let relative_path = index.intern(relative_path);
            index.files.push(FileRecord {
                id: file_id,
                module_name: None,
                language: file_language_for_typescript_path(&path),
                content_hash,
                path: relative_path,
                byte_len,
                line_count: line_count(&content),
                has_error: root.has_error(),
                root_range: root.range().into(),
            });
            extract_typescript_file(
                file_id,
                &content,
                &tree,
                &mut index,
                &mut reference_candidates,
            );
        }

        resolve_typescript_imports(&mut index, &ts_configs);
        resolve_typescript_references(&mut index, reference_candidates);
        build_typescript_dependencies(&mut index);
        Ok(index.finish())
    }
}

#[derive(Debug, Clone)]
struct TypeScriptConfig {
    dir: String,
    base_url: Option<String>,
    path_base: String,
    paths: Vec<TypeScriptPathMapping>,
}

#[derive(Debug, Clone)]
struct TypeScriptPathMapping {
    pattern_prefix: String,
    pattern_suffix: String,
    pattern_has_wildcard: bool,
    target_prefix: String,
    target_suffix: String,
    target_has_wildcard: bool,
}

impl TypeScriptPathMapping {
    fn from_pattern(pattern: &str, target: &str) -> Self {
        let (pattern_prefix, pattern_suffix, pattern_has_wildcard) =
            split_typescript_path_pattern(pattern);
        let (target_prefix, target_suffix, target_has_wildcard) =
            split_typescript_path_pattern(target);
        Self {
            pattern_prefix,
            pattern_suffix,
            pattern_has_wildcard,
            target_prefix,
            target_suffix,
            target_has_wildcard,
        }
    }

    fn apply(&self, module: &str) -> Option<String> {
        let wildcard = if self.pattern_has_wildcard {
            module
                .strip_prefix(&self.pattern_prefix)
                .and_then(|rest| rest.strip_suffix(&self.pattern_suffix))
        } else if module == self.pattern_prefix {
            Some("")
        } else {
            None
        }?;
        if self.target_has_wildcard {
            Some(format!(
                "{}{}{}",
                self.target_prefix, wildcard, self.target_suffix
            ))
        } else {
            Some(self.target_prefix.clone())
        }
    }

    fn specificity(&self) -> usize {
        self.pattern_prefix.len() + self.pattern_suffix.len()
    }
}

fn split_typescript_path_pattern(pattern: &str) -> (String, String, bool) {
    pattern
        .split_once('*')
        .map(|(prefix, suffix)| (prefix.to_owned(), suffix.to_owned(), true))
        .unwrap_or_else(|| (pattern.to_owned(), String::new(), false))
}

fn collect_typescript_configs(repo_path: &Path) -> Vec<TypeScriptConfig> {
    let mut config_paths = Vec::new();
    if collect_typescript_config_files(repo_path, &mut config_paths).is_err() {
        return Vec::new();
    }
    config_paths.sort();
    config_paths
        .into_iter()
        .filter_map(|path| parse_typescript_config(repo_path, &path))
        .collect()
}

fn collect_typescript_config_files(dir: &Path, out: &mut Vec<PathBuf>) -> Result<(), IndexError> {
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
            collect_typescript_config_files(&path, out)?;
        } else if file_type.is_file()
            && path.file_name().and_then(|name| name.to_str()) == Some("tsconfig.json")
        {
            out.push(path);
        }
    }
    Ok(())
}

fn parse_typescript_config(repo_path: &Path, path: &Path) -> Option<TypeScriptConfig> {
    let source = fs::read_to_string(path).ok()?;
    let json_source = strip_jsonc_comments_and_trailing_commas(&source);
    let json: serde_json::Value = serde_json::from_str(&json_source).ok()?;
    let compiler_options = json.get("compilerOptions")?.as_object()?;
    let dir = path
        .parent()
        .unwrap_or(repo_path)
        .strip_prefix(repo_path)
        .unwrap_or_else(|_| Path::new(""))
        .to_string_lossy()
        .replace('\\', "/");
    let base_url = compiler_options
        .get("baseUrl")
        .and_then(|value| value.as_str())
        .and_then(|value| normalize_typescript_config_path(&dir, value));
    let path_base = base_url.clone().unwrap_or_else(|| dir.clone());

    let mut paths = Vec::new();
    if let Some(paths_object) = compiler_options
        .get("paths")
        .and_then(|value| value.as_object())
    {
        for (pattern, targets) in paths_object {
            if let Some(target) = targets.as_str() {
                paths.push(TypeScriptPathMapping::from_pattern(pattern, target));
                continue;
            }
            if let Some(targets) = targets.as_array() {
                for target in targets.iter().filter_map(|target| target.as_str()) {
                    paths.push(TypeScriptPathMapping::from_pattern(pattern, target));
                }
            }
        }
    }
    paths.sort_by(|left, right| {
        right
            .specificity()
            .cmp(&left.specificity())
            .then_with(|| left.pattern_has_wildcard.cmp(&right.pattern_has_wildcard))
    });

    Some(TypeScriptConfig {
        dir,
        base_url,
        path_base,
        paths,
    })
}

fn strip_jsonc_comments_and_trailing_commas(source: &str) -> String {
    strip_json_trailing_commas(&strip_json_comments(source))
}

fn strip_json_comments(source: &str) -> String {
    let mut output = String::with_capacity(source.len());
    let mut chars = source.chars().peekable();
    let mut in_string = false;
    let mut escaped = false;

    while let Some(ch) = chars.next() {
        if in_string {
            output.push(ch);
            if escaped {
                escaped = false;
            } else if ch == '\\' {
                escaped = true;
            } else if ch == '"' {
                in_string = false;
            }
            continue;
        }

        if ch == '"' {
            in_string = true;
            output.push(ch);
            continue;
        }

        if ch == '/' && chars.peek() == Some(&'/') {
            chars.next();
            for comment_ch in chars.by_ref() {
                if comment_ch == '\n' {
                    output.push('\n');
                    break;
                }
            }
            continue;
        }

        if ch == '/' && chars.peek() == Some(&'*') {
            chars.next();
            let mut previous = '\0';
            for comment_ch in chars.by_ref() {
                if comment_ch == '\n' {
                    output.push('\n');
                }
                if previous == '*' && comment_ch == '/' {
                    break;
                }
                previous = comment_ch;
            }
            continue;
        }

        output.push(ch);
    }

    output
}

fn strip_json_trailing_commas(source: &str) -> String {
    let chars: Vec<char> = source.chars().collect();
    let mut output = String::with_capacity(source.len());
    let mut index = 0;
    let mut in_string = false;
    let mut escaped = false;

    while index < chars.len() {
        let ch = chars[index];
        if in_string {
            output.push(ch);
            if escaped {
                escaped = false;
            } else if ch == '\\' {
                escaped = true;
            } else if ch == '"' {
                in_string = false;
            }
            index += 1;
            continue;
        }

        if ch == '"' {
            in_string = true;
            output.push(ch);
            index += 1;
            continue;
        }

        if ch == ',' {
            let mut lookahead = index + 1;
            while lookahead < chars.len() && chars[lookahead].is_whitespace() {
                lookahead += 1;
            }
            if lookahead < chars.len() && matches!(chars[lookahead], '}' | ']') {
                index += 1;
                continue;
            }
        }

        output.push(ch);
        index += 1;
    }

    output
}

fn normalize_typescript_config_path(base: &str, path: &str) -> Option<String> {
    let mut raw_path = if path.starts_with('/') {
        path.trim_start_matches('/').to_owned()
    } else if base.is_empty() || path.is_empty() {
        format!("{base}{path}")
    } else {
        format!("{base}/{path}")
    };
    raw_path = raw_path.replace('\\', "/");

    let mut parts = Vec::new();
    for part in raw_path.split('/') {
        match part {
            "" | "." => {}
            ".." => {
                parts.pop()?;
            }
            _ => parts.push(part),
        }
    }
    Some(parts.join("/"))
}

fn read_source_lossy(path: &Path) -> Result<(String, usize, String), IndexError> {
    let bytes = fs::read(path).map_err(|source| IndexError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let byte_len = bytes.len();
    let content_hash = stable_content_hash(&bytes);
    Ok((
        String::from_utf8_lossy(&bytes).into_owned(),
        byte_len,
        content_hash,
    ))
}

fn stable_content_hash(bytes: &[u8]) -> String {
    let mut hash = 0xcbf2_9ce4_8422_2325u64;
    for byte in bytes {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
    format!("{hash:016x}")
}

fn file_language_for_typescript_path(path: &Path) -> FileLanguage {
    match path.extension().and_then(|extension| extension.to_str()) {
        Some("ts") => FileLanguage::TypeScript,
        Some("tsx") => FileLanguage::Tsx,
        Some("js") => FileLanguage::JavaScript,
        Some("jsx") => FileLanguage::Jsx,
        _ => FileLanguage::TypeScript,
    }
}

fn collect_typescript_files(dir: &Path, out: &mut Vec<PathBuf>) -> Result<(), IndexError> {
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
            collect_typescript_files(&path, out)?;
        } else if file_type.is_file() && is_typescript_like_file(&path) {
            out.push(path);
        }
    }
    Ok(())
}

fn is_typescript_like_file(path: &Path) -> bool {
    matches!(
        path.extension().and_then(|ext| ext.to_str()),
        Some("js" | "jsx" | "ts" | "tsx")
    )
}

fn extract_typescript_file(
    file_id: u32,
    source: &str,
    tree: &Tree,
    index: &mut TypeScriptIndex,
    reference_candidates: &mut Vec<ReferenceCandidate>,
) {
    let root = tree.root_node();
    let mut cursor = root.walk();
    for child in root.named_children(&mut cursor) {
        extract_typescript_top_level_node(file_id, source, child, index);
    }
    extract_typescript_nested_local_symbols(file_id, source, root, index);
    collect_typescript_reference_candidates(file_id, source, root, index, reference_candidates);
}

fn extract_typescript_top_level_node(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    index: &mut TypeScriptIndex,
) {
    match node.kind() {
        "function_declaration"
        | "generator_function_declaration"
        | "class_declaration"
        | "abstract_class_declaration"
        | "interface_declaration"
        | "type_alias_declaration"
        | "enum_declaration"
        | "internal_module" => {
            push_typescript_symbol(file_id, source, node, index);
        }
        "lexical_declaration" | "variable_declaration" => {
            push_typescript_variable_symbols(file_id, source, node, index);
            push_typescript_dynamic_imports(file_id, source, node, index);
        }
        "expression_statement" => {
            if let Some(module) = first_child_of_kind(node, &["internal_module"]) {
                push_typescript_symbol(file_id, source, module, index);
            }
        }
        "import_statement" => push_typescript_import_statement(file_id, source, node, index),
        "export_statement" => push_typescript_export_statement(file_id, source, node, index),
        _ => {}
    }
}

fn push_typescript_symbol(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    index: &mut TypeScriptIndex,
) -> Option<u32> {
    push_typescript_symbol_with_parent(file_id, source, node, None, index)
}

fn push_typescript_symbol_with_parent(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    parent_symbol_id: Option<u32>,
    index: &mut TypeScriptIndex,
) -> Option<u32> {
    let kind = match node.kind() {
        "function_declaration" | "generator_function_declaration" => SymbolKind::Function,
        "class_declaration" | "abstract_class_declaration" => SymbolKind::Class,
        "interface_declaration" => SymbolKind::Interface,
        "type_alias_declaration" => SymbolKind::TypeAlias,
        "enum_declaration" => SymbolKind::Enum,
        "internal_module" => SymbolKind::Namespace,
        _ => return None,
    };
    let symbol_id =
        push_typescript_named_symbol(file_id, source, node, node, kind, parent_symbol_id, index)?;
    if kind == SymbolKind::Namespace {
        extract_typescript_namespace_members(file_id, source, node, symbol_id, index);
    }
    Some(symbol_id)
}

fn push_typescript_named_symbol(
    file_id: u32,
    source: &str,
    declaration: Node<'_>,
    name_owner: Node<'_>,
    kind: SymbolKind,
    parent_symbol_id: Option<u32>,
    index: &mut TypeScriptIndex,
) -> Option<u32> {
    let Some(name_node) = name_owner.child_by_field_name("name") else {
        return None;
    };
    let Ok(name) = name_node.utf8_text(source.as_bytes()) else {
        return None;
    };
    let symbol_id = index.symbols.len() as u32;
    let name = index.intern(name);
    index.symbols.push(SymbolRecord {
        id: symbol_id,
        file_id,
        parent_symbol_id,
        is_top_level: parent_symbol_id.is_none(),
        name,
        kind,
        range: declaration.range().into(),
        name_range: name_node.range().into(),
    });
    Some(symbol_id)
}

fn push_typescript_variable_symbols(
    file_id: u32,
    source: &str,
    declaration: Node<'_>,
    index: &mut TypeScriptIndex,
) -> Vec<u32> {
    push_typescript_variable_symbols_with_parent(file_id, source, declaration, None, index)
}

fn push_typescript_variable_symbols_with_parent(
    file_id: u32,
    source: &str,
    declaration: Node<'_>,
    parent_symbol_id: Option<u32>,
    index: &mut TypeScriptIndex,
) -> Vec<u32> {
    let mut symbol_ids = Vec::new();
    let mut cursor = declaration.walk();
    for declarator in declaration
        .named_children(&mut cursor)
        .filter(|child| child.kind() == "variable_declarator")
    {
        let kind = declarator
            .child_by_field_name("value")
            .filter(|value| typescript_value_is_function(*value))
            .map_or(SymbolKind::GlobalVariable, |_| SymbolKind::Function);
        if let Some(name_node) = declarator.child_by_field_name("name") {
            let mut targets = Vec::new();
            collect_typescript_binding_targets(name_node, &mut targets);
            for target in targets {
                if let Ok(name) = target.utf8_text(source.as_bytes()) {
                    let symbol_id = index.symbols.len() as u32;
                    let name = index.intern(name);
                    index.symbols.push(SymbolRecord {
                        id: symbol_id,
                        file_id,
                        parent_symbol_id,
                        is_top_level: parent_symbol_id.is_none(),
                        name,
                        kind,
                        range: declaration.range().into(),
                        name_range: target.range().into(),
                    });
                    symbol_ids.push(symbol_id);
                }
            }
        }
    }
    symbol_ids
}

fn extract_typescript_namespace_members(
    file_id: u32,
    source: &str,
    namespace: Node<'_>,
    namespace_symbol_id: u32,
    index: &mut TypeScriptIndex,
) {
    let Some(body) = namespace.child_by_field_name("body") else {
        return;
    };
    let mut cursor = body.walk();
    for child in body.named_children(&mut cursor) {
        let declaration = if child.kind() == "export_statement" {
            child.child_by_field_name("declaration")
        } else {
            Some(child)
        };
        let Some(declaration) = declaration else {
            continue;
        };
        match declaration.kind() {
            "function_declaration"
            | "generator_function_declaration"
            | "class_declaration"
            | "abstract_class_declaration"
            | "interface_declaration"
            | "type_alias_declaration"
            | "enum_declaration"
            | "internal_module" => {
                push_typescript_symbol_with_parent(
                    file_id,
                    source,
                    declaration,
                    Some(namespace_symbol_id),
                    index,
                );
            }
            "lexical_declaration" | "variable_declaration" => {
                push_typescript_variable_symbols_with_parent(
                    file_id,
                    source,
                    declaration,
                    Some(namespace_symbol_id),
                    index,
                );
            }
            _ => {}
        }
    }
}

fn extract_typescript_nested_local_symbols(
    file_id: u32,
    source: &str,
    root: Node<'_>,
    index: &mut TypeScriptIndex,
) {
    let owner_symbol_ranges = index
        .symbols
        .iter()
        .filter(|symbol| {
            symbol.file_id == file_id
                && matches!(
                    symbol.kind,
                    SymbolKind::Class
                        | SymbolKind::Function
                        | SymbolKind::GlobalVariable
                        | SymbolKind::Interface
                        | SymbolKind::TypeAlias
                        | SymbolKind::Enum
                        | SymbolKind::Namespace
                )
                && (symbol.kind != SymbolKind::GlobalVariable || symbol.is_top_level)
        })
        .map(|symbol| (symbol.id, symbol.range))
        .collect::<Vec<_>>();
    extract_typescript_nested_local_symbols_from_node(
        file_id,
        source,
        root,
        index,
        &owner_symbol_ranges,
        None,
        0,
    );
}

fn extract_typescript_nested_local_symbols_from_node(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    index: &mut TypeScriptIndex,
    owner_symbol_ranges: &[(u32, SourceRange)],
    current_symbol_id: Option<u32>,
    nested_function_depth: usize,
) {
    let node_range = SourceRange::from(node.range());
    let mut current_symbol_id = current_symbol_id;
    let mut nested_function_depth = nested_function_depth;
    if let Some((symbol_id, _)) = owner_symbol_ranges
        .iter()
        .find(|(_, range)| *range == node_range)
    {
        current_symbol_id = Some(*symbol_id);
        nested_function_depth = 0;
    } else if current_symbol_id.is_some() && is_typescript_function_like(node) {
        nested_function_depth += 1;
    }

    if let Some(parent_symbol_id) = current_symbol_id {
        if nested_function_depth > 0 {
            match node.kind() {
                "variable_declarator" => {
                    push_typescript_local_variable_symbol_targets(
                        file_id,
                        source,
                        parent_symbol_id,
                        node,
                        node.child_by_field_name("name"),
                        index,
                    );
                }
                "assignment_expression" | "augmented_assignment_expression" => {
                    if let Some(left) = node.child_by_field_name("left") {
                        if typescript_assignment_left_can_bind(left) {
                            push_typescript_local_variable_symbol_targets(
                                file_id,
                                source,
                                parent_symbol_id,
                                node,
                                Some(left),
                                index,
                            );
                        }
                    }
                }
                _ => {}
            }
        }
    }

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        extract_typescript_nested_local_symbols_from_node(
            file_id,
            source,
            child,
            index,
            owner_symbol_ranges,
            current_symbol_id,
            nested_function_depth,
        );
    }
}

fn typescript_assignment_left_can_bind(node: Node<'_>) -> bool {
    matches!(
        node.kind(),
        "identifier"
            | "shorthand_property_identifier_pattern"
            | "object_pattern"
            | "array_pattern"
            | "pair_pattern"
            | "assignment_pattern"
            | "object_assignment_pattern"
    )
}

fn push_typescript_local_variable_symbol_targets(
    file_id: u32,
    source: &str,
    parent_symbol_id: u32,
    declaration: Node<'_>,
    binding_root: Option<Node<'_>>,
    index: &mut TypeScriptIndex,
) -> Vec<u32> {
    let mut symbol_ids = Vec::new();
    let Some(binding_root) = binding_root else {
        return symbol_ids;
    };
    let mut targets = Vec::new();
    collect_typescript_binding_targets(binding_root, &mut targets);
    for target in targets {
        let Ok(name) = target.utf8_text(source.as_bytes()) else {
            continue;
        };
        let symbol_id = index.symbols.len() as u32;
        let name = index.intern(name);
        index.symbols.push(SymbolRecord {
            id: symbol_id,
            file_id,
            parent_symbol_id: Some(parent_symbol_id),
            is_top_level: false,
            name,
            kind: SymbolKind::GlobalVariable,
            range: declaration.range().into(),
            name_range: target.range().into(),
        });
        symbol_ids.push(symbol_id);
    }
    symbol_ids
}

fn typescript_value_is_function(node: Node<'_>) -> bool {
    match node.kind() {
        "arrow_function" | "function_expression" | "generator_function" => true,
        "parenthesized_expression" => {
            first_named_child(node).is_some_and(typescript_value_is_function)
        }
        _ => false,
    }
}

fn collect_typescript_binding_targets<'tree>(node: Node<'tree>, out: &mut Vec<Node<'tree>>) {
    match node.kind() {
        "identifier"
        | "type_identifier"
        | "shorthand_property_identifier_pattern"
        | "property_identifier" => out.push(node),
        "variable_declarator" => {
            if let Some(name) = node.child_by_field_name("name") {
                collect_typescript_binding_targets(name, out);
            }
        }
        "pair_pattern" => {
            if let Some(value) = node.child_by_field_name("value") {
                collect_typescript_binding_targets(value, out);
            }
        }
        "assignment_pattern" | "object_assignment_pattern" => {
            if let Some(left) = node.child_by_field_name("left") {
                collect_typescript_binding_targets(left, out);
            }
        }
        "formal_parameters"
        | "lexical_declaration"
        | "optional_parameter"
        | "parameters"
        | "required_parameter"
        | "rest_pattern"
        | "variable_declaration"
        | "object_pattern"
        | "array_pattern" => {
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                collect_typescript_binding_targets(child, out);
            }
        }
        _ => {}
    }
}

fn push_typescript_import_statement(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    index: &mut TypeScriptIndex,
) {
    let module = node
        .child_by_field_name("source")
        .and_then(|source_node| typescript_string_literal_value(node_text(source, source_node)));
    let Some(module) = module else {
        return;
    };
    let Some(import_clause) = first_child_of_kind(node, &["import_clause"]) else {
        push_typescript_import(
            file_id,
            ImportKind::SideEffect,
            Some(module),
            None,
            None,
            node.range().into(),
            index,
        );
        return;
    };

    let mut emitted = false;
    let mut cursor = import_clause.walk();
    for child in import_clause.named_children(&mut cursor) {
        match child.kind() {
            "identifier" => {
                let name = node_text(source, child).to_owned();
                push_typescript_import(
                    file_id,
                    ImportKind::DefaultImport,
                    Some(module.clone()),
                    Some(name.clone()),
                    Some(name),
                    child.range().into(),
                    index,
                );
                emitted = true;
            }
            "named_imports" => {
                push_typescript_named_imports(file_id, source, child, &module, index);
                emitted = true;
            }
            "namespace_import" => {
                if let Some(alias) = first_identifier_child(child) {
                    let alias = node_text(source, alias).to_owned();
                    push_typescript_import(
                        file_id,
                        ImportKind::NamespaceImport,
                        Some(module.clone()),
                        Some("*".to_owned()),
                        Some(alias),
                        child.range().into(),
                        index,
                    );
                    emitted = true;
                }
            }
            _ => {}
        }
    }

    if !emitted {
        push_typescript_import(
            file_id,
            ImportKind::SideEffect,
            Some(module),
            None,
            None,
            import_clause.range().into(),
            index,
        );
    }
}

fn push_typescript_named_imports(
    file_id: u32,
    source: &str,
    named_imports: Node<'_>,
    module: &str,
    index: &mut TypeScriptIndex,
) {
    let mut cursor = named_imports.walk();
    for specifier in named_imports
        .named_children(&mut cursor)
        .filter(|child| child.kind() == "import_specifier")
    {
        let Some(name_node) = specifier.child_by_field_name("name") else {
            continue;
        };
        let name = node_text(source, name_node).to_owned();
        let alias = specifier
            .child_by_field_name("alias")
            .map(|alias| node_text(source, alias).to_owned())
            .unwrap_or_else(|| name.clone());
        push_typescript_import(
            file_id,
            ImportKind::NamedImport,
            Some(module.to_owned()),
            Some(name),
            Some(alias),
            specifier.range().into(),
            index,
        );
    }
}

fn push_typescript_dynamic_imports(
    file_id: u32,
    source: &str,
    declaration: Node<'_>,
    index: &mut TypeScriptIndex,
) {
    let mut cursor = declaration.walk();
    for declarator in declaration
        .named_children(&mut cursor)
        .filter(|child| child.kind() == "variable_declarator")
    {
        let Some(value) = declarator.child_by_field_name("value") else {
            continue;
        };
        let Some(module) = find_typescript_dynamic_import_module(source, value) else {
            continue;
        };
        if let Some(name_node) = declarator.child_by_field_name("name") {
            let mut targets = Vec::new();
            collect_typescript_binding_targets(name_node, &mut targets);
            for target in targets {
                let local_name = node_text(source, target).to_owned();
                push_typescript_import(
                    file_id,
                    ImportKind::DynamicImport,
                    Some(module.clone()),
                    Some(local_name.clone()),
                    Some(local_name),
                    declarator.range().into(),
                    index,
                );
            }
        }
    }
}

fn find_typescript_dynamic_import_module(source: &str, node: Node<'_>) -> Option<String> {
    if node.kind() == "call_expression" {
        if let Some(function) = node.child_by_field_name("function") {
            let function_text = node_text(source, function);
            if matches!(function_text, "require" | "import") {
                if let Some(arguments) = node.child_by_field_name("arguments") {
                    let mut cursor = arguments.walk();
                    for child in arguments.named_children(&mut cursor) {
                        if child.kind() == "string" {
                            return typescript_string_literal_value(node_text(source, child));
                        }
                    }
                }
            }
        }
    }

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        if let Some(module) = find_typescript_dynamic_import_module(source, child) {
            return Some(module);
        }
    }
    None
}

fn push_typescript_export_statement(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    index: &mut TypeScriptIndex,
) {
    let source_module = node
        .child_by_field_name("source")
        .and_then(|source_node| typescript_string_literal_value(node_text(source, source_node)));

    if let Some(declaration) = node.child_by_field_name("declaration") {
        let symbol_ids = push_typescript_export_declaration(file_id, source, declaration, index);
        let is_default = has_direct_child_kind(node, "default");
        for symbol_id in symbol_ids {
            let symbol = &index.symbols[symbol_id as usize];
            let symbol_name = symbol.name.to_string();
            push_typescript_export(
                file_id,
                if is_default {
                    ExportKind::Default
                } else {
                    ExportKind::Named
                },
                Some(if is_default {
                    "default".to_owned()
                } else {
                    symbol_name.clone()
                }),
                Some(symbol_name),
                None,
                Some(symbol_id),
                None,
                node.range().into(),
                index,
            );
        }
        return;
    }

    if let Some(export_clause) = first_child_of_kind(node, &["export_clause"]) {
        push_typescript_export_clause(file_id, source, node, export_clause, source_module, index);
        return;
    }

    if let Some(namespace_export) = first_child_of_kind(node, &["namespace_export"]) {
        let name = first_identifier_child(namespace_export)
            .map(|identifier| node_text(source, identifier).to_owned());
        let import_id = source_module.as_ref().and_then(|module| {
            name.as_ref().map(|name| {
                push_typescript_import(
                    file_id,
                    ImportKind::NamespaceImport,
                    Some(module.clone()),
                    Some("*".to_owned()),
                    Some(name.clone()),
                    namespace_export.range().into(),
                    index,
                )
            })
        });
        push_typescript_export(
            file_id,
            ExportKind::Namespace,
            name.clone(),
            name,
            source_module,
            None,
            import_id,
            node.range().into(),
            index,
        );
        return;
    }

    if has_direct_child_kind(node, "*") {
        let import_id = source_module.as_ref().map(|module| {
            push_typescript_import(
                file_id,
                ImportKind::NamespaceImport,
                Some(module.clone()),
                Some("*".to_owned()),
                None,
                node.range().into(),
                index,
            )
        });
        push_typescript_export(
            file_id,
            ExportKind::Wildcard,
            None,
            None,
            source_module,
            None,
            import_id,
            node.range().into(),
            index,
        );
        return;
    }

    if has_direct_child_kind(node, "default") {
        if let Some(value) = node.child_by_field_name("value") {
            push_typescript_export(
                file_id,
                ExportKind::Default,
                Some("default".to_owned()),
                Some(node_text(source, value).to_owned()),
                None,
                None,
                None,
                node.range().into(),
                index,
            );
        }
        return;
    }

    if node_text(source, node).trim_start().starts_with("export =") {
        let local_name =
            last_identifier_child(node).map(|identifier| node_text(source, identifier).to_owned());
        push_typescript_export(
            file_id,
            ExportKind::ExportEquals,
            local_name.clone(),
            local_name,
            None,
            None,
            None,
            node.range().into(),
            index,
        );
    }
}

fn push_typescript_export_declaration(
    file_id: u32,
    source: &str,
    declaration: Node<'_>,
    index: &mut TypeScriptIndex,
) -> Vec<u32> {
    match declaration.kind() {
        "function_declaration"
        | "generator_function_declaration"
        | "class_declaration"
        | "abstract_class_declaration"
        | "interface_declaration"
        | "type_alias_declaration"
        | "enum_declaration"
        | "internal_module" => push_typescript_symbol(file_id, source, declaration, index)
            .into_iter()
            .collect(),
        "lexical_declaration" | "variable_declaration" => {
            push_typescript_variable_symbols(file_id, source, declaration, index)
        }
        _ => Vec::new(),
    }
}

fn push_typescript_export_clause(
    file_id: u32,
    source: &str,
    export_statement: Node<'_>,
    export_clause: Node<'_>,
    source_module: Option<String>,
    index: &mut TypeScriptIndex,
) {
    let mut cursor = export_clause.walk();
    for specifier in export_clause
        .named_children(&mut cursor)
        .filter(|child| child.kind() == "export_specifier")
    {
        let Some(name_node) = specifier.child_by_field_name("name") else {
            continue;
        };
        let local_name = node_text(source, name_node).to_owned();
        let exported_name = specifier
            .child_by_field_name("alias")
            .map(|alias| node_text(source, alias).to_owned())
            .unwrap_or_else(|| local_name.clone());
        let import_id = source_module.as_ref().map(|module| {
            push_typescript_import(
                file_id,
                ImportKind::NamedImport,
                Some(module.clone()),
                Some(local_name.clone()),
                Some(exported_name.clone()),
                specifier.range().into(),
                index,
            )
        });
        push_typescript_export(
            file_id,
            if exported_name == "default" {
                ExportKind::Default
            } else {
                ExportKind::Named
            },
            Some(exported_name),
            Some(local_name),
            source_module.clone(),
            None,
            import_id,
            export_statement.range().into(),
            index,
        );
    }
}

fn push_typescript_import(
    file_id: u32,
    kind: ImportKind,
    module: Option<String>,
    name: Option<String>,
    alias: Option<String>,
    range: SourceRange,
    index: &mut TypeScriptIndex,
) -> u32 {
    let import_id = index.imports.len() as u32;
    let module = module.map(|value| index.intern(value));
    let name = name.map(|value| index.intern(value));
    let alias = alias.map(|value| index.intern(value));
    index.imports.push(ImportRecord {
        id: import_id,
        file_id,
        kind,
        module,
        name,
        alias,
        range,
    });
    import_id
}

fn push_typescript_export(
    file_id: u32,
    kind: ExportKind,
    name: Option<String>,
    local_name: Option<String>,
    source_module: Option<String>,
    symbol_id: Option<u32>,
    import_id: Option<u32>,
    range: SourceRange,
    index: &mut TypeScriptIndex,
) {
    let name = name.map(|value| index.intern(value));
    let local_name = local_name.map(|value| index.intern(value));
    let source_module = source_module.map(|value| index.intern(value));
    index.exports.push(ExportRecord {
        id: index.exports.len() as u32,
        file_id,
        kind,
        name,
        local_name,
        source_module,
        symbol_id,
        import_id,
        range,
    });
}

fn collect_typescript_reference_candidates(
    file_id: u32,
    source: &str,
    root: Node<'_>,
    index: &TypeScriptIndex,
    out: &mut Vec<ReferenceCandidate>,
) {
    let symbol_ranges = index
        .symbols
        .iter()
        .filter(|symbol| symbol.file_id == file_id)
        .map(|symbol| (symbol.id, symbol.range))
        .collect::<Vec<_>>();
    let excluded_ranges = index
        .symbols
        .iter()
        .filter(|symbol| symbol.file_id == file_id)
        .map(|symbol| symbol.name_range)
        .collect::<Vec<_>>();
    let indexed_local_symbols = IndexedLocalSymbols::from_symbols(
        index
            .symbols
            .iter()
            .filter(|symbol| symbol.file_id == file_id),
    );
    let (local_bindings_by_symbol_id, local_binding_scopes) =
        collect_typescript_local_bindings(file_id, source, root, index, &symbol_ranges);

    collect_typescript_identifier_candidates(
        file_id,
        source,
        root,
        &symbol_ranges,
        &local_bindings_by_symbol_id,
        &local_binding_scopes,
        &excluded_ranges,
        &indexed_local_symbols,
        out,
    );
    collect_typescript_type_reference_candidates(
        file_id,
        source,
        root,
        &symbol_ranges,
        &local_bindings_by_symbol_id,
        &local_binding_scopes,
        &excluded_ranges,
        &indexed_local_symbols,
        out,
    );
    collect_typescript_heritage_reference_candidates(
        file_id,
        source,
        root,
        &symbol_ranges,
        &local_bindings_by_symbol_id,
        &local_binding_scopes,
        &excluded_ranges,
        &indexed_local_symbols,
        out,
    );
}

fn collect_typescript_local_bindings(
    file_id: u32,
    source: &str,
    root: Node<'_>,
    index: &TypeScriptIndex,
    symbol_ranges: &[(u32, SourceRange)],
) -> (HashMap<u32, HashSet<String>>, Vec<LocalBindingScope>) {
    let mut bindings = HashMap::new();
    let mut scoped_bindings = Vec::new();
    let file_symbols = index
        .symbols
        .iter()
        .filter(|symbol| symbol.file_id == file_id)
        .collect::<Vec<_>>();
    for symbol in file_symbols {
        let mut names = HashSet::new();
        collect_typescript_local_bindings_for_symbol(source, root, symbol.range, &mut names);
        names.remove(symbol.name.as_ref());
        if !names.is_empty() {
            bindings.insert(symbol.id, names);
        }
    }

    for (symbol_id, _) in symbol_ranges {
        bindings.entry(*symbol_id).or_default();
    }
    collect_typescript_scoped_local_bindings_from_node(
        source,
        root,
        symbol_ranges,
        &mut scoped_bindings,
    );
    (bindings, scoped_bindings)
}

fn collect_typescript_local_bindings_for_symbol(
    source: &str,
    node: Node<'_>,
    symbol_range: SourceRange,
    out: &mut HashSet<String>,
) {
    let node_range = node.range().into();
    if !ranges_overlap(symbol_range, node_range) {
        return;
    }

    match node.kind() {
        "import_statement" => return,
        "variable_declarator" => {
            if contains_range(symbol_range, node_range)
                && !typescript_variable_declarator_is_lexical(node)
            {
                if let Some(name_node) = node.child_by_field_name("name") {
                    let mut targets = Vec::new();
                    collect_typescript_binding_targets(name_node, &mut targets);
                    for target in targets {
                        if let Ok(name) = target.utf8_text(source.as_bytes()) {
                            out.insert(name.to_owned());
                        }
                    }
                }
            }
        }
        "required_parameter" | "optional_parameter" | "rest_pattern" => {
            if contains_range(symbol_range, node_range)
                && typescript_parameter_is_symbol_wide(node, symbol_range)
            {
                let binding_node = node.child_by_field_name("pattern").or_else(|| {
                    node.child_by_field_name("name")
                        .or_else(|| first_named_child(node))
                });
                if let Some(binding_node) = binding_node {
                    let mut targets = Vec::new();
                    collect_typescript_binding_targets(binding_node, &mut targets);
                    for target in targets {
                        if let Ok(name) = target.utf8_text(source.as_bytes()) {
                            out.insert(name.to_owned());
                        }
                    }
                }
            }
        }
        _ => {}
    }

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_typescript_local_bindings_for_symbol(source, child, symbol_range, out);
    }
}

fn typescript_variable_declarator_is_lexical(node: Node<'_>) -> bool {
    node.parent()
        .is_some_and(|parent| parent.kind() == "lexical_declaration")
}

fn typescript_parameter_is_symbol_wide(node: Node<'_>, symbol_range: SourceRange) -> bool {
    let mut current = Some(node);
    while let Some(parent) = current {
        if is_typescript_function_like(parent) {
            return SourceRange::from(parent.range()) == symbol_range;
        }
        current = parent.parent();
    }
    false
}

fn is_typescript_function_like(node: Node<'_>) -> bool {
    matches!(
        node.kind(),
        "function_declaration"
            | "generator_function_declaration"
            | "method_definition"
            | "function_signature"
            | "arrow_function"
            | "function_expression"
            | "generator_function"
    )
}

fn collect_typescript_scoped_local_bindings_from_node(
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    scoped_bindings: &mut Vec<LocalBindingScope>,
) {
    match node.kind() {
        "function_declaration"
        | "generator_function_declaration"
        | "class_declaration"
        | "abstract_class_declaration" => {
            push_typescript_nested_declaration_binding_scope(
                source,
                node,
                symbol_ranges,
                scoped_bindings,
            );
        }
        "lexical_declaration" => {
            push_typescript_lexical_declaration_binding_scope(
                source,
                node,
                symbol_ranges,
                scoped_bindings,
            );
        }
        "for_in_statement" => {
            if let Some(left) = node
                .child_by_field_name("left")
                .or_else(|| first_named_child(node))
            {
                let scope = node
                    .child_by_field_name("body")
                    .or_else(|| first_child_of_kind(node, &["statement_block"]))
                    .unwrap_or(node);
                push_typescript_local_binding_scope(
                    source,
                    left,
                    scope.range().into(),
                    symbol_ranges,
                    scoped_bindings,
                );
            }
        }
        "catch_clause" => {
            if let Some(parameter) = node
                .child_by_field_name("parameter")
                .or_else(|| first_named_child(node))
            {
                let scope = node
                    .child_by_field_name("body")
                    .or_else(|| first_child_of_kind(node, &["statement_block"]))
                    .unwrap_or(node);
                push_typescript_local_binding_scope(
                    source,
                    parameter,
                    scope.range().into(),
                    symbol_ranges,
                    scoped_bindings,
                );
            }
        }
        "arrow_function" | "function_expression" | "generator_function" => {
            push_typescript_function_parameter_binding_scope(
                source,
                node,
                symbol_ranges,
                scoped_bindings,
            );
        }
        _ => {}
    }

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_typescript_scoped_local_bindings_from_node(
            source,
            child,
            symbol_ranges,
            scoped_bindings,
        );
    }
}

fn push_typescript_lexical_declaration_binding_scope(
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    scoped_bindings: &mut Vec<LocalBindingScope>,
) {
    let node_range = SourceRange::from(node.range());
    let Some((source_symbol_id, symbol_range)) =
        innermost_symbol_range_for_range(symbol_ranges, node_range)
    else {
        return;
    };
    let mut targets = Vec::new();
    collect_typescript_binding_targets(node, &mut targets);
    let Some(first_target) = targets.iter().min_by_key(|target| target.start_byte()) else {
        return;
    };
    let scope_end = typescript_lexical_declaration_scope_end(node).unwrap_or(symbol_range);
    let scope_range = SourceRange {
        start_byte: first_target.start_byte(),
        end_byte: scope_end.end_byte,
        start_row: first_target.start_position().row,
        start_column: first_target.start_position().column,
        end_row: scope_end.end_row,
        end_column: scope_end.end_column,
    };
    let mut names = HashSet::new();
    for target in targets {
        if let Ok(name) = target.utf8_text(source.as_bytes()) {
            names.insert(name.to_owned());
        }
    }
    if !names.is_empty() {
        scoped_bindings.push(LocalBindingScope {
            source_symbol_id,
            range: scope_range,
            names,
        });
    }
}

fn typescript_lexical_declaration_scope_end(node: Node<'_>) -> Option<SourceRange> {
    let mut current = node.parent();
    while let Some(parent) = current {
        if matches!(
            parent.kind(),
            "for_statement" | "for_in_statement" | "statement_block" | "switch_body"
        ) {
            return Some(parent.range().into());
        }
        current = parent.parent();
    }
    None
}

fn push_typescript_nested_declaration_binding_scope(
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    scoped_bindings: &mut Vec<LocalBindingScope>,
) {
    let node_range = SourceRange::from(node.range());
    let Some((source_symbol_id, symbol_range)) =
        innermost_symbol_range_for_range(symbol_ranges, node_range)
    else {
        return;
    };
    if node_range == symbol_range {
        return;
    }
    let Some(name) = node.child_by_field_name("name") else {
        return;
    };
    let scope_range = SourceRange {
        start_byte: name.start_byte(),
        end_byte: symbol_range.end_byte,
        start_row: name.start_position().row,
        start_column: name.start_position().column,
        end_row: symbol_range.end_row,
        end_column: symbol_range.end_column,
    };
    let mut names = HashSet::new();
    if let Ok(name) = name.utf8_text(source.as_bytes()) {
        names.insert(name.to_owned());
    }
    if !names.is_empty() {
        scoped_bindings.push(LocalBindingScope {
            source_symbol_id,
            range: scope_range,
            names,
        });
    }
}

fn push_typescript_function_parameter_binding_scope(
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    scoped_bindings: &mut Vec<LocalBindingScope>,
) {
    let Some(parameters) = node
        .child_by_field_name("parameters")
        .or_else(|| first_child_of_kind(node, &["formal_parameters"]))
        .or_else(|| first_named_child(node))
    else {
        return;
    };
    let Some(body) = typescript_function_body_node(node) else {
        return;
    };
    push_typescript_local_binding_scope(
        source,
        parameters,
        body.range().into(),
        symbol_ranges,
        scoped_bindings,
    );
}

fn typescript_function_body_node(node: Node<'_>) -> Option<Node<'_>> {
    node.child_by_field_name("body")
        .or_else(|| first_child_of_kind(node, &["statement_block"]))
        .or_else(|| {
            let mut cursor = node.walk();
            node.named_children(&mut cursor)
                .filter(|child| child.kind() != "formal_parameters")
                .last()
        })
}

fn push_typescript_local_binding_scope(
    source: &str,
    binding_root: Node<'_>,
    scope_range: SourceRange,
    symbol_ranges: &[(u32, SourceRange)],
    scoped_bindings: &mut Vec<LocalBindingScope>,
) {
    let Some(source_symbol_id) = innermost_symbol_for_range(symbol_ranges, scope_range) else {
        return;
    };
    let mut targets = Vec::new();
    collect_typescript_binding_targets(binding_root, &mut targets);
    let mut names = HashSet::new();
    for target in targets {
        if let Ok(name) = target.utf8_text(source.as_bytes()) {
            names.insert(name.to_owned());
        }
    }
    if !names.is_empty() {
        scoped_bindings.push(LocalBindingScope {
            source_symbol_id,
            range: binding_root.range().into(),
            names: names.clone(),
        });
        scoped_bindings.push(LocalBindingScope {
            source_symbol_id,
            range: scope_range,
            names,
        });
    }
}

fn collect_typescript_identifier_candidates(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    excluded_ranges: &[SourceRange],
    indexed_local_symbols: &IndexedLocalSymbols,
    out: &mut Vec<ReferenceCandidate>,
) {
    match node.kind() {
        "import_statement"
        | "export_clause"
        | "namespace_export"
        | "extends_clause"
        | "implements_clause"
        | "extends_type_clause" => return,
        "call_expression" => {
            let function_node = node.child_by_field_name("function");
            if let Some(function_node) = function_node {
                push_typescript_call_reference_candidate(
                    file_id,
                    source,
                    node,
                    function_node,
                    symbol_ranges,
                    local_bindings_by_symbol_id,
                    local_binding_scopes,
                    excluded_ranges,
                    indexed_local_symbols,
                    out,
                );
                collect_typescript_call_function_operands(
                    file_id,
                    source,
                    function_node,
                    symbol_ranges,
                    local_bindings_by_symbol_id,
                    local_binding_scopes,
                    excluded_ranges,
                    indexed_local_symbols,
                    out,
                );
            }

            let function_range = function_node.map(|function| SourceRange::from(function.range()));
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                if function_range.is_some_and(|range| SourceRange::from(child.range()) == range) {
                    continue;
                }
                collect_typescript_identifier_candidates(
                    file_id,
                    source,
                    child,
                    symbol_ranges,
                    local_bindings_by_symbol_id,
                    local_binding_scopes,
                    excluded_ranges,
                    indexed_local_symbols,
                    out,
                );
            }
            return;
        }
        "member_expression" => {
            if let (Some(object), Some(property)) = (
                node.child_by_field_name("object"),
                node.child_by_field_name("property"),
            ) {
                let range = property.range().into();
                if matches!(property.kind(), "identifier" | "property_identifier")
                    && !range_matches_any(range, excluded_ranges)
                {
                    if let (Ok(qualifier), Ok(name)) = (
                        object.utf8_text(source.as_bytes()),
                        property.utf8_text(source.as_bytes()),
                    ) {
                        let source_symbol_id = innermost_symbol_for_range(symbol_ranges, range);
                        if !typescript_reference_is_shadowed(
                            source_symbol_id,
                            qualifier.split('.').next().unwrap_or(qualifier),
                            range,
                            local_bindings_by_symbol_id,
                            local_binding_scopes,
                            indexed_local_symbols,
                        ) {
                            out.push(ReferenceCandidate {
                                source_file_id: file_id,
                                source_symbol_id,
                                name: name.to_owned(),
                                qualifier: Some(qualifier.to_owned()),
                                range,
                                is_subclass: false,
                                call_range: None,
                            });
                        }
                    }
                }
            }
            if let Some(object) = node.child_by_field_name("object") {
                collect_typescript_identifier_candidates(
                    file_id,
                    source,
                    object,
                    symbol_ranges,
                    local_bindings_by_symbol_id,
                    local_binding_scopes,
                    excluded_ranges,
                    indexed_local_symbols,
                    out,
                );
            }
            return;
        }
        _ => {}
    }

    let range = node.range().into();
    if node.kind() == "identifier" && !range_matches_any(range, excluded_ranges) {
        if let Ok(name) = node.utf8_text(source.as_bytes()) {
            let source_symbol_id = innermost_symbol_for_range(symbol_ranges, range);
            if !typescript_reference_is_shadowed(
                source_symbol_id,
                name,
                range,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                indexed_local_symbols,
            ) {
                out.push(ReferenceCandidate {
                    source_file_id: file_id,
                    source_symbol_id,
                    name: name.to_owned(),
                    qualifier: None,
                    range,
                    is_subclass: false,
                    call_range: None,
                });
            }
        }
    }

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_typescript_identifier_candidates(
            file_id,
            source,
            child,
            symbol_ranges,
            local_bindings_by_symbol_id,
            local_binding_scopes,
            excluded_ranges,
            indexed_local_symbols,
            out,
        );
    }
}

fn collect_typescript_call_function_operands(
    file_id: u32,
    source: &str,
    function_node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    excluded_ranges: &[SourceRange],
    indexed_local_symbols: &IndexedLocalSymbols,
    out: &mut Vec<ReferenceCandidate>,
) {
    match function_node.kind() {
        "member_expression" => {
            if let Some(object) = function_node.child_by_field_name("object") {
                collect_typescript_identifier_candidates(
                    file_id,
                    source,
                    object,
                    symbol_ranges,
                    local_bindings_by_symbol_id,
                    local_binding_scopes,
                    excluded_ranges,
                    indexed_local_symbols,
                    out,
                );
            }
        }
        "call_expression" => {
            collect_typescript_identifier_candidates(
                file_id,
                source,
                function_node,
                symbol_ranges,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                excluded_ranges,
                indexed_local_symbols,
                out,
            );
        }
        "identifier" => {}
        _ => {
            let mut cursor = function_node.walk();
            for child in function_node.named_children(&mut cursor) {
                collect_typescript_identifier_candidates(
                    file_id,
                    source,
                    child,
                    symbol_ranges,
                    local_bindings_by_symbol_id,
                    local_binding_scopes,
                    excluded_ranges,
                    indexed_local_symbols,
                    out,
                );
            }
        }
    }
}

fn push_typescript_call_reference_candidate(
    file_id: u32,
    source: &str,
    call_node: Node<'_>,
    function_node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    excluded_ranges: &[SourceRange],
    indexed_local_symbols: &IndexedLocalSymbols,
    out: &mut Vec<ReferenceCandidate>,
) {
    match function_node.kind() {
        "identifier" | "property_identifier" | "private_property_identifier" => {
            push_typescript_named_call_reference_candidate(
                file_id,
                source,
                call_node.range().into(),
                function_node,
                None,
                function_node,
                symbol_ranges,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                excluded_ranges,
                indexed_local_symbols,
                out,
            );
        }
        "member_expression" => {
            let (Some(object), Some(property)) = (
                function_node.child_by_field_name("object"),
                function_node.child_by_field_name("property"),
            ) else {
                return;
            };
            if !matches!(
                property.kind(),
                "identifier" | "property_identifier" | "private_property_identifier"
            ) {
                return;
            }
            push_typescript_named_call_reference_candidate(
                file_id,
                source,
                call_node.range().into(),
                property,
                Some(object),
                property,
                symbol_ranges,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                excluded_ranges,
                indexed_local_symbols,
                out,
            );
        }
        _ => {}
    }
}

fn push_typescript_named_call_reference_candidate(
    file_id: u32,
    source: &str,
    call_range: SourceRange,
    name_node: Node<'_>,
    qualifier_node: Option<Node<'_>>,
    shadow_name_node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    excluded_ranges: &[SourceRange],
    indexed_local_symbols: &IndexedLocalSymbols,
    out: &mut Vec<ReferenceCandidate>,
) {
    let name_range = SourceRange::from(name_node.range());
    if range_matches_any(name_range, excluded_ranges) {
        return;
    }
    let Ok(name) = name_node.utf8_text(source.as_bytes()) else {
        return;
    };
    let qualifier = qualifier_node.and_then(|qualifier_node| {
        qualifier_node
            .utf8_text(source.as_bytes())
            .ok()
            .map(|qualifier| qualifier.to_owned())
    });
    let source_symbol_id = innermost_symbol_for_range(symbol_ranges, name_range);
    let shadow_name = qualifier
        .as_deref()
        .map(|qualifier| qualifier.split('.').next().unwrap_or(qualifier))
        .unwrap_or(name);
    let shadow_range = qualifier_node
        .map(|qualifier_node| SourceRange::from(qualifier_node.range()))
        .unwrap_or_else(|| SourceRange::from(shadow_name_node.range()));
    if typescript_reference_is_shadowed(
        source_symbol_id,
        shadow_name,
        shadow_range,
        local_bindings_by_symbol_id,
        local_binding_scopes,
        indexed_local_symbols,
    ) {
        return;
    }
    out.push(ReferenceCandidate {
        source_file_id: file_id,
        source_symbol_id,
        name: name.to_owned(),
        qualifier,
        range: name_range,
        is_subclass: false,
        call_range: Some(call_range),
    });
}

fn collect_typescript_type_reference_candidates(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    excluded_ranges: &[SourceRange],
    indexed_local_symbols: &IndexedLocalSymbols,
    out: &mut Vec<ReferenceCandidate>,
) {
    match node.kind() {
        "import_statement"
        | "export_clause"
        | "namespace_export"
        | "extends_clause"
        | "implements_clause"
        | "extends_type_clause" => return,
        "type_identifier" => {
            push_typescript_type_reference_candidate(
                file_id,
                source,
                node,
                symbol_ranges,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                excluded_ranges,
                indexed_local_symbols,
                out,
            );
            return;
        }
        "nested_type_identifier" => {
            push_typescript_nested_type_reference_candidate(
                file_id,
                source,
                node,
                symbol_ranges,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                excluded_ranges,
                indexed_local_symbols,
                out,
                false,
            );
            return;
        }
        "type_parameter" => {
            let name_range = node
                .child_by_field_name("name")
                .map(|name| SourceRange::from(name.range()));
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                if name_range.is_some_and(|range| SourceRange::from(child.range()) == range) {
                    continue;
                }
                collect_typescript_type_reference_candidates(
                    file_id,
                    source,
                    child,
                    symbol_ranges,
                    local_bindings_by_symbol_id,
                    local_binding_scopes,
                    excluded_ranges,
                    indexed_local_symbols,
                    out,
                );
            }
            return;
        }
        _ => {}
    }

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_typescript_type_reference_candidates(
            file_id,
            source,
            child,
            symbol_ranges,
            local_bindings_by_symbol_id,
            local_binding_scopes,
            excluded_ranges,
            indexed_local_symbols,
            out,
        );
    }
}

fn push_typescript_type_reference_candidate(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    excluded_ranges: &[SourceRange],
    indexed_local_symbols: &IndexedLocalSymbols,
    out: &mut Vec<ReferenceCandidate>,
) {
    let range = SourceRange::from(node.range());
    if range_matches_any(range, excluded_ranges) {
        return;
    }
    let Ok(name) = node.utf8_text(source.as_bytes()) else {
        return;
    };
    let source_symbol_id = innermost_symbol_for_range(symbol_ranges, range);
    if !typescript_reference_is_shadowed(
        source_symbol_id,
        name,
        range,
        local_bindings_by_symbol_id,
        local_binding_scopes,
        indexed_local_symbols,
    ) {
        out.push(ReferenceCandidate {
            source_file_id: file_id,
            source_symbol_id,
            name: name.to_owned(),
            qualifier: None,
            range,
            is_subclass: false,
            call_range: None,
        });
    }
}

fn push_typescript_nested_type_reference_candidate(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    excluded_ranges: &[SourceRange],
    indexed_local_symbols: &IndexedLocalSymbols,
    out: &mut Vec<ReferenceCandidate>,
    is_subclass: bool,
) {
    let Some(name_node) = node.child_by_field_name("name") else {
        return;
    };
    let Some(module_node) = node.child_by_field_name("module") else {
        return;
    };
    let range = SourceRange::from(name_node.range());
    if range_matches_any(range, excluded_ranges) {
        return;
    }
    let Ok(name) = name_node.utf8_text(source.as_bytes()) else {
        return;
    };
    let Ok(module) = module_node.utf8_text(source.as_bytes()) else {
        return;
    };
    let qualifier = module.split('.').next().unwrap_or(module);
    let source_symbol_id = innermost_symbol_for_range(symbol_ranges, range);
    if !typescript_reference_is_shadowed(
        source_symbol_id,
        qualifier,
        range,
        local_bindings_by_symbol_id,
        local_binding_scopes,
        indexed_local_symbols,
    ) {
        out.push(ReferenceCandidate {
            source_file_id: file_id,
            source_symbol_id,
            name: name.to_owned(),
            qualifier: Some(qualifier.to_owned()),
            range,
            is_subclass,
            call_range: None,
        });
    }
}

fn collect_typescript_heritage_reference_candidates(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    excluded_ranges: &[SourceRange],
    indexed_local_symbols: &IndexedLocalSymbols,
    out: &mut Vec<ReferenceCandidate>,
) {
    if node.kind() == "extends_clause" {
        let mut cursor = node.walk();
        for child in node.named_children(&mut cursor) {
            if child.kind() == "type_arguments" {
                continue;
            }
            push_typescript_heritage_expression_reference_candidate(
                file_id,
                source,
                child,
                symbol_ranges,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                excluded_ranges,
                indexed_local_symbols,
                out,
            );
            break;
        }
        return;
    }

    if matches!(node.kind(), "implements_clause" | "extends_type_clause") {
        let mut cursor = node.walk();
        for child in node.named_children(&mut cursor) {
            push_typescript_heritage_type_reference_candidate(
                file_id,
                source,
                child,
                symbol_ranges,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                excluded_ranges,
                indexed_local_symbols,
                out,
            );
        }
        return;
    }

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_typescript_heritage_reference_candidates(
            file_id,
            source,
            child,
            symbol_ranges,
            local_bindings_by_symbol_id,
            local_binding_scopes,
            excluded_ranges,
            indexed_local_symbols,
            out,
        );
    }
}

fn push_typescript_heritage_expression_reference_candidate(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    excluded_ranges: &[SourceRange],
    indexed_local_symbols: &IndexedLocalSymbols,
    out: &mut Vec<ReferenceCandidate>,
) {
    match node.kind() {
        "identifier" => {
            let range = SourceRange::from(node.range());
            if range_matches_any(range, excluded_ranges) {
                return;
            }
            let Ok(name) = node.utf8_text(source.as_bytes()) else {
                return;
            };
            let source_symbol_id = innermost_symbol_for_range(symbol_ranges, range);
            if !typescript_reference_is_shadowed(
                source_symbol_id,
                name,
                range,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                indexed_local_symbols,
            ) {
                out.push(ReferenceCandidate {
                    source_file_id: file_id,
                    source_symbol_id,
                    name: name.to_owned(),
                    qualifier: None,
                    range,
                    is_subclass: true,
                    call_range: None,
                });
            }
        }
        "member_expression" => {
            let (Some(object), Some(property)) = (
                node.child_by_field_name("object"),
                node.child_by_field_name("property"),
            ) else {
                return;
            };
            let range = SourceRange::from(property.range());
            if range_matches_any(range, excluded_ranges) {
                return;
            }
            let Ok(name) = property.utf8_text(source.as_bytes()) else {
                return;
            };
            let Ok(qualifier) = object.utf8_text(source.as_bytes()) else {
                return;
            };
            let qualifier = qualifier.split('.').next().unwrap_or(qualifier);
            let source_symbol_id = innermost_symbol_for_range(symbol_ranges, range);
            if !typescript_reference_is_shadowed(
                source_symbol_id,
                qualifier,
                range,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                indexed_local_symbols,
            ) {
                out.push(ReferenceCandidate {
                    source_file_id: file_id,
                    source_symbol_id,
                    name: name.to_owned(),
                    qualifier: Some(qualifier.to_owned()),
                    range,
                    is_subclass: true,
                    call_range: None,
                });
            }
        }
        _ => {}
    }
}

fn push_typescript_heritage_type_reference_candidate(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    excluded_ranges: &[SourceRange],
    indexed_local_symbols: &IndexedLocalSymbols,
    out: &mut Vec<ReferenceCandidate>,
) {
    match node.kind() {
        "type_identifier" => {
            let range = SourceRange::from(node.range());
            if range_matches_any(range, excluded_ranges) {
                return;
            }
            let Ok(name) = node.utf8_text(source.as_bytes()) else {
                return;
            };
            let source_symbol_id = innermost_symbol_for_range(symbol_ranges, range);
            if !typescript_reference_is_shadowed(
                source_symbol_id,
                name,
                range,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                indexed_local_symbols,
            ) {
                out.push(ReferenceCandidate {
                    source_file_id: file_id,
                    source_symbol_id,
                    name: name.to_owned(),
                    qualifier: None,
                    range,
                    is_subclass: true,
                    call_range: None,
                });
            }
        }
        "generic_type" => {
            if let Some(name) = node.child_by_field_name("name") {
                push_typescript_heritage_type_reference_candidate(
                    file_id,
                    source,
                    name,
                    symbol_ranges,
                    local_bindings_by_symbol_id,
                    local_binding_scopes,
                    excluded_ranges,
                    indexed_local_symbols,
                    out,
                );
            }
        }
        "nested_type_identifier" => {
            let Some(name_node) = node.child_by_field_name("name") else {
                return;
            };
            let Some(module_node) = node.child_by_field_name("module") else {
                return;
            };
            let range = SourceRange::from(name_node.range());
            if range_matches_any(range, excluded_ranges) {
                return;
            }
            let Ok(name) = name_node.utf8_text(source.as_bytes()) else {
                return;
            };
            let Ok(module) = module_node.utf8_text(source.as_bytes()) else {
                return;
            };
            let qualifier = module.split('.').next().unwrap_or(module);
            let source_symbol_id = innermost_symbol_for_range(symbol_ranges, range);
            if !typescript_reference_is_shadowed(
                source_symbol_id,
                qualifier,
                range,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                indexed_local_symbols,
            ) {
                out.push(ReferenceCandidate {
                    source_file_id: file_id,
                    source_symbol_id,
                    name: name.to_owned(),
                    qualifier: Some(qualifier.to_owned()),
                    range,
                    is_subclass: true,
                    call_range: None,
                });
            }
        }
        _ => {}
    }
}

fn ranges_overlap(left: SourceRange, right: SourceRange) -> bool {
    left.start_byte < right.end_byte && right.start_byte < left.end_byte
}

fn typescript_reference_is_shadowed(
    source_symbol_id: Option<u32>,
    name: &str,
    range: SourceRange,
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    indexed_local_symbols: &IndexedLocalSymbols,
) -> bool {
    if typescript_indexed_local_symbol_for_reference(
        source_symbol_id,
        name,
        range,
        indexed_local_symbols,
    )
    .is_some()
    {
        return false;
    }
    is_shadowed_local_binding(
        source_symbol_id,
        name,
        range,
        local_bindings_by_symbol_id,
        local_binding_scopes,
    )
}

fn typescript_indexed_local_symbol_for_reference(
    source_symbol_id: Option<u32>,
    name: &str,
    range: SourceRange,
    indexed_local_symbols: &IndexedLocalSymbols,
) -> Option<u32> {
    let owner_symbol_id =
        typescript_local_scope_owner_symbol_id(source_symbol_id, indexed_local_symbols)?;
    indexed_local_symbols
        .symbols_by_parent_and_name
        .get(&(owner_symbol_id, name.to_owned()))?
        .iter()
        .rev()
        .find(|symbol| {
            symbol.name_range.start_byte < range.start_byte
                && !range_matches_any(range, &[symbol.name_range])
        })
        .map(|symbol| symbol.id)
}

fn typescript_local_scope_owner_symbol_id(
    source_symbol_id: Option<u32>,
    indexed_local_symbols: &IndexedLocalSymbols,
) -> Option<u32> {
    let source_symbol_id = source_symbol_id?;
    indexed_local_symbols
        .parent_symbol_by_id
        .get(&source_symbol_id)
        .copied()
        .or(Some(source_symbol_id))
}

fn resolve_typescript_imports(index: &mut TypeScriptIndex, ts_configs: &[TypeScriptConfig]) {
    let file_by_path: HashMap<String, u32> = index
        .files
        .iter()
        .map(|file| (file.path.to_string(), file.id))
        .collect();
    let symbol_by_file_and_name: HashMap<(u32, String), u32> = index
        .symbols
        .iter()
        .filter(|symbol| symbol.is_top_level)
        .map(|symbol| ((symbol.file_id, symbol.name.to_string()), symbol.id))
        .collect();
    let mut resolutions = Vec::new();
    for import in &index.imports {
        let Some(module) = import.module.as_deref() else {
            continue;
        };
        let Some(source_file) = index.files.get(import.file_id as usize) else {
            continue;
        };
        let target_file_id = if module.starts_with('.') {
            resolve_typescript_relative_module(source_file, module, &file_by_path)
        } else {
            resolve_typescript_config_module(source_file, module, &file_by_path, ts_configs)
        };
        let Some(target_file_id) = target_file_id else {
            continue;
        };
        resolutions.push(ImportResolutionRecord {
            id: resolutions.len() as u32,
            import_id: import.id,
            source_file_id: import.file_id,
            target_file_id,
            target_symbol_id: None,
        });
    }
    resolve_typescript_import_symbols(index, &symbol_by_file_and_name, &mut resolutions);
    index.import_resolutions = resolutions;
    index.external_modules = build_external_modules(&index.imports, &index.import_resolutions);
}

fn build_external_modules(
    imports: &[ImportRecord],
    import_resolutions: &[ImportResolutionRecord],
) -> Vec<ExternalModuleRecord> {
    let resolved_import_ids: HashSet<u32> = import_resolutions
        .iter()
        .map(|resolution| resolution.import_id)
        .collect();
    imports
        .iter()
        .filter(|import| !resolved_import_ids.contains(&import.id))
        .filter(|import| import_is_external_candidate(import))
        .filter_map(|import| {
            Some(ExternalModuleRecord {
                id: 0,
                import_id: import.id,
                file_id: import.file_id,
                module: import.module.clone(),
                name: external_module_name(import)?,
                alias: import.alias.clone(),
                range: import.range,
            })
        })
        .enumerate()
        .map(|(id, mut record)| {
            record.id = id as u32;
            record
        })
        .collect()
}

fn import_is_external_candidate(import: &ImportRecord) -> bool {
    if import.kind == ImportKind::FutureImport {
        return false;
    }
    if let Some(module) = import.module.as_deref() {
        return !module.starts_with('.');
    }
    import
        .name
        .as_deref()
        .is_some_and(|name| !name.starts_with('.'))
}

fn external_module_name(import: &ImportRecord) -> Option<InternedString> {
    import.name.clone().or_else(|| import.module.clone())
}

fn typescript_local_exported_symbol_map(
    index: &TypeScriptIndex,
    symbol_by_file_and_name: &HashMap<(u32, String), u32>,
) -> HashMap<(u32, String), u32> {
    let mut exported_symbols = HashMap::new();
    for export in &index.exports {
        if export.source_module.is_some() {
            continue;
        }
        let Some(name) = export.name.as_deref() else {
            continue;
        };
        let symbol_id = export.symbol_id.or_else(|| {
            export.local_name.as_deref().and_then(|local_name| {
                symbol_by_file_and_name
                    .get(&(export.file_id, local_name.to_owned()))
                    .copied()
            })
        });
        if let Some(symbol_id) = symbol_id {
            exported_symbols.insert((export.file_id, name.to_owned()), symbol_id);
        }
    }
    exported_symbols
}

fn resolve_typescript_import_symbols(
    index: &TypeScriptIndex,
    symbol_by_file_and_name: &HashMap<(u32, String), u32>,
    resolutions: &mut [ImportResolutionRecord],
) {
    let local_exported_symbols =
        typescript_local_exported_symbol_map(index, symbol_by_file_and_name);
    let import_by_id: HashMap<u32, &ImportRecord> = index
        .imports
        .iter()
        .map(|import| (import.id, import))
        .collect();
    let mut exported_symbol_by_file_and_name = local_exported_symbols.clone();

    for _ in 0..=index.exports.len() {
        let mut changed = false;
        for resolution in resolutions.iter_mut() {
            let Some(import) = import_by_id.get(&resolution.import_id) else {
                continue;
            };
            let target_symbol_id = resolve_typescript_import_symbol(
                import,
                resolution.target_file_id,
                &exported_symbol_by_file_and_name,
                symbol_by_file_and_name,
            );
            if resolution.target_symbol_id != target_symbol_id {
                resolution.target_symbol_id = target_symbol_id;
                changed = true;
            }
        }

        let next_exported_symbol_by_file_and_name =
            typescript_resolved_exported_symbol_map(index, &local_exported_symbols, resolutions);
        if next_exported_symbol_by_file_and_name != exported_symbol_by_file_and_name {
            exported_symbol_by_file_and_name = next_exported_symbol_by_file_and_name;
            changed = true;
        }
        if !changed {
            break;
        }
    }
}

fn typescript_resolved_exported_symbol_map(
    index: &TypeScriptIndex,
    local_exported_symbols: &HashMap<(u32, String), u32>,
    resolutions: &[ImportResolutionRecord],
) -> HashMap<(u32, String), u32> {
    let mut exported_symbols = local_exported_symbols.clone();
    for _ in 0..=index.exports.len() {
        let next_exported_symbols = typescript_exported_symbol_map(
            index,
            local_exported_symbols,
            &exported_symbols,
            resolutions,
        );
        if next_exported_symbols == exported_symbols {
            break;
        }
        exported_symbols = next_exported_symbols;
    }
    exported_symbols
}

fn typescript_exported_symbol_map(
    index: &TypeScriptIndex,
    local_exported_symbols: &HashMap<(u32, String), u32>,
    previous_exported_symbols: &HashMap<(u32, String), u32>,
    resolutions: &[ImportResolutionRecord],
) -> HashMap<(u32, String), u32> {
    let resolution_by_import_id: HashMap<u32, &ImportResolutionRecord> = resolutions
        .iter()
        .map(|resolution| (resolution.import_id, resolution))
        .collect();
    let mut exported_symbols = local_exported_symbols.clone();

    for export in &index.exports {
        let Some(import_id) = export.import_id else {
            continue;
        };
        let Some(resolution) = resolution_by_import_id.get(&import_id) else {
            continue;
        };
        match export.kind {
            ExportKind::Named | ExportKind::Default | ExportKind::ExportEquals => {
                let Some(name) = export.name.as_deref() else {
                    continue;
                };
                if let Some(symbol_id) = resolution.target_symbol_id {
                    exported_symbols.insert((export.file_id, name.to_owned()), symbol_id);
                }
            }
            ExportKind::Wildcard => {
                for ((file_id, name), symbol_id) in previous_exported_symbols {
                    if *file_id == resolution.target_file_id && name != "default" {
                        exported_symbols.insert((export.file_id, name.clone()), *symbol_id);
                    }
                }
            }
            ExportKind::Namespace => {}
        }
    }

    exported_symbols
}

fn typescript_namespace_export_file_map(
    index: &TypeScriptIndex,
    resolutions: &[ImportResolutionRecord],
) -> HashMap<(u32, String), u32> {
    let resolution_by_import_id: HashMap<u32, &ImportResolutionRecord> = resolutions
        .iter()
        .map(|resolution| (resolution.import_id, resolution))
        .collect();
    let mut namespace_exports = HashMap::new();
    for export in &index.exports {
        if export.kind != ExportKind::Namespace {
            continue;
        }
        let Some(name) = export.name.as_deref() else {
            continue;
        };
        let Some(import_id) = export.import_id else {
            continue;
        };
        let Some(resolution) = resolution_by_import_id.get(&import_id) else {
            continue;
        };
        namespace_exports.insert((export.file_id, name.to_owned()), resolution.target_file_id);
    }
    namespace_exports
}

fn resolve_typescript_import_symbol(
    import: &ImportRecord,
    target_file_id: u32,
    exported_symbol_by_file_and_name: &HashMap<(u32, String), u32>,
    symbol_by_file_and_name: &HashMap<(u32, String), u32>,
) -> Option<u32> {
    let export_name = match import.kind {
        ImportKind::DefaultImport => "default",
        ImportKind::NamedImport => import.name.as_deref()?,
        ImportKind::Import
        | ImportKind::FromImport
        | ImportKind::FutureImport
        | ImportKind::SideEffect
        | ImportKind::NamespaceImport
        | ImportKind::DynamicImport => return None,
    };
    exported_symbol_by_file_and_name
        .get(&(target_file_id, export_name.to_owned()))
        .copied()
        .or_else(|| {
            symbol_by_file_and_name
                .get(&(target_file_id, export_name.to_owned()))
                .copied()
        })
}

fn resolve_typescript_relative_module(
    source_file: &FileRecord,
    module: &str,
    file_by_path: &HashMap<String, u32>,
) -> Option<u32> {
    let base = normalize_typescript_relative_module(&source_file.path, module)?;
    for candidate in typescript_module_candidates(&base) {
        if let Some(file_id) = file_by_path.get(candidate.as_str()).copied() {
            return Some(file_id);
        }
    }
    None
}

fn normalize_typescript_relative_module(source_path: &str, module: &str) -> Option<String> {
    let source_dir = source_path
        .rsplit_once('/')
        .map(|(dir, _)| dir)
        .unwrap_or("");
    let raw_path = if source_dir.is_empty() {
        module.to_owned()
    } else {
        format!("{source_dir}/{module}")
    };
    let mut parts = Vec::new();
    for part in raw_path.split('/') {
        match part {
            "" | "." => {}
            ".." => {
                parts.pop()?;
            }
            _ => parts.push(part),
        }
    }
    Some(parts.join("/"))
}

fn resolve_typescript_config_module(
    source_file: &FileRecord,
    module: &str,
    file_by_path: &HashMap<String, u32>,
    ts_configs: &[TypeScriptConfig],
) -> Option<u32> {
    let config = typescript_config_for_file(&source_file.path, ts_configs)?;

    for mapping in &config.paths {
        let Some(target) = mapping.apply(module) else {
            continue;
        };
        let Some(base) = normalize_typescript_config_path(&config.path_base, &target) else {
            continue;
        };
        if let Some(file_id) = resolve_typescript_module_base(&base, file_by_path) {
            return Some(file_id);
        }
    }

    let base_url = config.base_url.as_deref()?;
    let base = normalize_typescript_config_path(base_url, module)?;
    resolve_typescript_module_base(&base, file_by_path)
}

fn resolve_typescript_module_base(base: &str, file_by_path: &HashMap<String, u32>) -> Option<u32> {
    for candidate in typescript_module_candidates(base) {
        if let Some(file_id) = file_by_path.get(candidate.as_str()).copied() {
            return Some(file_id);
        }
    }
    None
}

fn typescript_config_for_file<'a>(
    file_path: &str,
    ts_configs: &'a [TypeScriptConfig],
) -> Option<&'a TypeScriptConfig> {
    ts_configs
        .iter()
        .filter(|config| typescript_file_is_under_config(file_path, &config.dir))
        .max_by_key(|config| config.dir.len())
}

fn typescript_file_is_under_config(file_path: &str, config_dir: &str) -> bool {
    config_dir.is_empty()
        || file_path == config_dir
        || file_path
            .strip_prefix(config_dir)
            .is_some_and(|rest| rest.starts_with('/'))
}

fn typescript_module_candidates(base: &str) -> Vec<String> {
    const EXTENSIONS: &[&str] = &["ts", "tsx", "d.ts", "js", "jsx"];
    let mut candidates = vec![base.to_owned()];
    if !has_typescript_module_suffix(base, EXTENSIONS) {
        candidates.extend(
            EXTENSIONS
                .iter()
                .map(|extension| format!("{base}.{extension}")),
        );
    }
    candidates.extend(
        EXTENSIONS
            .iter()
            .map(|extension| format!("{base}/index.{extension}")),
    );
    candidates
}

fn has_typescript_module_suffix(path: &str, suffixes: &[&str]) -> bool {
    suffixes.iter().any(|suffix| {
        path.strip_suffix(suffix)
            .is_some_and(|prefix| prefix.ends_with('.'))
    })
}

fn resolve_typescript_references(index: &mut TypeScriptIndex, candidates: Vec<ReferenceCandidate>) {
    let mut strings = std::mem::take(&mut index.strings);
    let symbol_by_file_and_name: HashMap<(u32, String), u32> = index
        .symbols
        .iter()
        .filter(|symbol| symbol.is_top_level)
        .map(|symbol| ((symbol.file_id, symbol.name.to_string()), symbol.id))
        .collect();
    let local_exported_symbols =
        typescript_local_exported_symbol_map(index, &symbol_by_file_and_name);
    let exported_symbol_by_file_and_name = typescript_resolved_exported_symbol_map(
        index,
        &local_exported_symbols,
        &index.import_resolutions,
    );
    let namespace_export_file_by_file_and_name =
        typescript_namespace_export_file_map(index, &index.import_resolutions);
    let resolution_by_import_id: HashMap<u32, &ImportResolutionRecord> = index
        .import_resolutions
        .iter()
        .map(|resolution| (resolution.import_id, resolution))
        .collect();
    let mut imported_symbol_by_binding: HashMap<(u32, String), (u32, u32)> = HashMap::new();
    let mut imported_module_by_qualifier: HashMap<(u32, String), (u32, u32)> = HashMap::new();
    let external_import_ids: HashSet<u32> = index
        .external_modules
        .iter()
        .map(|external_module| external_module.import_id)
        .collect();
    let mut external_import_by_binding: HashMap<(u32, String), u32> = HashMap::new();

    for import in &index.imports {
        if external_import_ids.contains(&import.id) {
            if let Some(binding) = typescript_import_binding_name(import) {
                external_import_by_binding.insert((import.file_id, binding), import.id);
            }
        }
        let Some(resolution) = resolution_by_import_id.get(&import.id) else {
            continue;
        };
        if import.kind == ImportKind::NamespaceImport {
            if let Some(alias) = import.alias.as_deref() {
                imported_module_by_qualifier.insert(
                    (import.file_id, alias.to_owned()),
                    (resolution.target_file_id, import.id),
                );
            }
        } else if import.kind == ImportKind::NamedImport {
            if let (Some(binding), Some(name)) = (
                typescript_import_binding_name(import),
                import.name.as_deref(),
            ) {
                if let Some(target_file_id) = namespace_export_file_by_file_and_name
                    .get(&(resolution.target_file_id, name.to_owned()))
                    .copied()
                {
                    imported_module_by_qualifier
                        .insert((import.file_id, binding), (target_file_id, import.id));
                }
            }
        }
        let Some(target_symbol_id) = resolution.target_symbol_id else {
            continue;
        };
        let Some(binding) = typescript_import_binding_name(import) else {
            continue;
        };
        imported_symbol_by_binding.insert((import.file_id, binding), (target_symbol_id, import.id));
    }

    let symbol_file_ids: HashMap<u32, u32> = index
        .symbols
        .iter()
        .map(|symbol| (symbol.id, symbol.file_id))
        .collect();
    let indexed_local_symbols = IndexedLocalSymbols::from_symbols(index.symbols.iter());
    let mut references = Vec::new();
    let mut external_references = Vec::new();
    let mut function_calls = Vec::new();
    let mut subclass_edges = Vec::new();
    let mut subclass_edge_pairs = HashSet::new();
    for candidate in candidates {
        let resolved_target = if let Some(qualifier) = candidate.qualifier.as_ref() {
            imported_module_by_qualifier
                .get(&(candidate.source_file_id, qualifier.clone()))
                .and_then(|(target_file_id, import_id)| {
                    exported_symbol_by_file_and_name
                        .get(&(*target_file_id, candidate.name.clone()))
                        .or_else(|| {
                            symbol_by_file_and_name.get(&(*target_file_id, candidate.name.clone()))
                        })
                        .copied()
                        .map(|symbol_id| (symbol_id, Some(*import_id)))
                })
        } else {
            let local_target = typescript_indexed_local_symbol_for_reference(
                candidate.source_symbol_id,
                &candidate.name,
                candidate.range,
                &indexed_local_symbols,
            )
            .map(|symbol_id| (symbol_id, None));
            let imported_target = imported_symbol_by_binding
                .get(&(candidate.source_file_id, candidate.name.clone()))
                .copied();
            let same_file_target = symbol_by_file_and_name
                .get(&(candidate.source_file_id, candidate.name.clone()))
                .copied()
                .map(|symbol_id| (symbol_id, None));
            local_target.or(imported_target
                .map(|(symbol_id, import_id)| (symbol_id, Some(import_id)))
                .or(same_file_target))
        };
        let Some((target_symbol_id, import_id)) = resolved_target else {
            let mut call_import_id = None;
            if candidate.qualifier.is_none() {
                if let Some(import_id) = external_import_by_binding
                    .get(&(candidate.source_file_id, candidate.name.clone()))
                {
                    let name = strings.intern(&candidate.name);
                    call_import_id = Some(*import_id);
                    external_references.push(ExternalReferenceRecord {
                        id: external_references.len() as u32,
                        source_file_id: candidate.source_file_id,
                        source_symbol_id: candidate.source_symbol_id,
                        import_id: *import_id,
                        name,
                        range: candidate.range,
                    });
                }
            } else if let Some(qualifier) = candidate.qualifier.as_ref() {
                call_import_id = external_import_by_binding
                    .get(&(candidate.source_file_id, qualifier.clone()))
                    .copied();
            }
            if let Some(call_range) = candidate.call_range {
                let name = strings.intern(&candidate.name);
                function_calls.push(FunctionCallRecord {
                    id: function_calls.len() as u32,
                    source_file_id: candidate.source_file_id,
                    source_symbol_id: candidate.source_symbol_id,
                    target_symbol_id: None,
                    import_id: call_import_id,
                    name,
                    range: call_range,
                    name_range: candidate.range,
                });
            }
            continue;
        };
        if let Some(call_range) = candidate.call_range {
            let name = strings.intern(&candidate.name);
            function_calls.push(FunctionCallRecord {
                id: function_calls.len() as u32,
                source_file_id: candidate.source_file_id,
                source_symbol_id: candidate.source_symbol_id,
                target_symbol_id: Some(target_symbol_id),
                import_id,
                name,
                range: call_range,
                name_range: candidate.range,
            });
        }
        if candidate.source_symbol_id == Some(target_symbol_id) {
            continue;
        }

        let reference_id = references.len() as u32;
        let name = strings.intern(&candidate.name);
        references.push(ReferenceRecord {
            id: reference_id,
            source_file_id: candidate.source_file_id,
            source_symbol_id: candidate.source_symbol_id,
            target_symbol_id,
            import_id,
            name,
            range: candidate.range,
        });
        if candidate.is_subclass {
            if let Some(source_symbol_id) = candidate.source_symbol_id {
                if subclass_edge_pairs.insert((source_symbol_id, target_symbol_id)) {
                    let Some(source_file_id) = symbol_file_ids.get(&source_symbol_id).copied()
                    else {
                        continue;
                    };
                    let Some(target_file_id) = symbol_file_ids.get(&target_symbol_id).copied()
                    else {
                        continue;
                    };
                    subclass_edges.push(SubclassRecord {
                        id: subclass_edges.len() as u32,
                        source_symbol_id,
                        target_symbol_id,
                        source_file_id,
                        target_file_id,
                        reference_id,
                    });
                }
            }
        }
    }
    index.references = references;
    index.external_references = external_references;
    index.function_calls = function_calls;
    index.subclass_edges = subclass_edges;
    index.strings = strings;
}

fn typescript_import_binding_name(import: &ImportRecord) -> Option<String> {
    if let Some(alias) = import.alias.as_deref() {
        return Some(alias.to_owned());
    }
    match import.kind {
        ImportKind::DefaultImport | ImportKind::NamedImport | ImportKind::DynamicImport => {
            import.name.as_ref().map(|name| name.to_string())
        }
        ImportKind::NamespaceImport => import.alias.as_ref().map(|alias| alias.to_string()),
        ImportKind::Import
        | ImportKind::FromImport
        | ImportKind::FutureImport
        | ImportKind::SideEffect => None,
    }
}

fn build_typescript_dependencies(index: &mut TypeScriptIndex) {
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

fn typescript_string_literal_value(text: &str) -> Option<String> {
    let trimmed = text.trim();
    for quote in ["'", "\"", "`"] {
        if let Some(value) = trimmed
            .strip_prefix(quote)
            .and_then(|value| value.strip_suffix(quote))
        {
            return Some(value.to_owned());
        }
    }
    None
}

fn first_identifier_child(node: Node<'_>) -> Option<Node<'_>> {
    let mut cursor = node.walk();
    let child = node
        .named_children(&mut cursor)
        .find(|child| matches!(child.kind(), "identifier" | "type_identifier"));
    child
}

fn last_identifier_child(node: Node<'_>) -> Option<Node<'_>> {
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .filter(|child| matches!(child.kind(), "identifier" | "type_identifier"))
        .last()
}

fn has_direct_child_kind(node: Node<'_>, kind: &str) -> bool {
    let mut cursor = node.walk();
    let has_kind = node.children(&mut cursor).any(|child| child.kind() == kind);
    has_kind
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
    collect_nested_python_imports(file_id, source, root, index, true);
    let symbol_ranges = index
        .symbols
        .iter()
        .filter(|symbol| symbol.file_id == file_id)
        .map(|symbol| (symbol.id, symbol.range))
        .collect::<Vec<_>>();
    let (local_bindings_by_symbol_id, local_binding_scopes) =
        collect_local_bindings(file_id, source, root, index, &symbol_ranges);
    collect_identifier_candidates(
        file_id,
        source,
        root,
        &symbol_ranges,
        &local_bindings_by_symbol_id,
        &local_binding_scopes,
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

fn collect_nested_python_imports(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    index: &mut PythonIndex,
    is_root: bool,
) {
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        if !is_root {
            match child.kind() {
                "import_statement" => {
                    push_import_statement(file_id, source, child, index);
                    continue;
                }
                "import_from_statement" | "future_import_statement" => {
                    push_from_import_statement(file_id, source, child, index);
                    continue;
                }
                _ => {}
            }
        }
        collect_nested_python_imports(file_id, source, child, index, false);
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
    let name = index.intern(name);
    index.symbols.push(SymbolRecord {
        id: symbol_id,
        file_id,
        parent_symbol_id,
        is_top_level: parent_symbol_id.is_none(),
        name,
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
    let defines_static_all_exports = targets.iter().any(|target| {
        target
            .utf8_text(source.as_bytes())
            .is_ok_and(|name| name == "__all__")
    });
    if defines_static_all_exports {
        if let Some(exports) = node
            .child_by_field_name("right")
            .and_then(|right| collect_static_all_exports(source, right))
        {
            index.all_exports_by_file.insert(file_id, exports);
        }
    }
    for target in targets {
        let Ok(name) = target.utf8_text(source.as_bytes()) else {
            continue;
        };
        let name = index.intern(name);
        index.symbols.push(SymbolRecord {
            id: index.symbols.len() as u32,
            file_id,
            parent_symbol_id: None,
            is_top_level: true,
            name,
            kind: SymbolKind::GlobalVariable,
            range: node.range().into(),
            name_range: target.range().into(),
        });
        excluded_name_ranges.push(target.range().into());
    }
}

fn collect_static_all_exports(source: &str, node: Node<'_>) -> Option<BTreeSet<String>> {
    match node.kind() {
        "list" | "tuple" | "set" => {
            let mut exports = BTreeSet::new();
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                if child.kind() != "string" {
                    return None;
                }
                let value = python_string_literal_value(node_text(source, child))?;
                exports.insert(value);
            }
            Some(exports)
        }
        "parenthesized_expression" => {
            first_named_child(node).and_then(|child| collect_static_all_exports(source, child))
        }
        _ => None,
    }
}

fn python_string_literal_value(text: &str) -> Option<String> {
    let mut literal = text.trim();
    let mut has_f_prefix = false;
    while let Some(prefix) = literal.chars().next() {
        if matches!(prefix, '\'' | '"') {
            break;
        }
        if matches!(prefix, 'f' | 'F') {
            has_f_prefix = true;
        }
        if matches!(prefix, 'r' | 'R' | 'b' | 'B' | 'u' | 'U' | 'f' | 'F') {
            literal = &literal[prefix.len_utf8()..];
        } else {
            return None;
        }
    }
    if has_f_prefix {
        return None;
    }
    for quote in ["'''", "\"\"\"", "'", "\""] {
        if let Some(value) = literal
            .strip_prefix(quote)
            .and_then(|value| value.strip_suffix(quote))
        {
            return Some(value.to_owned());
        }
    }
    None
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
) -> (HashMap<u32, HashSet<String>>, Vec<LocalBindingScope>) {
    let mut bindings: HashMap<u32, HashSet<String>> = HashMap::new();
    let mut global_declarations: HashMap<u32, HashSet<String>> = HashMap::new();
    let mut scoped_bindings: Vec<LocalBindingScope> = Vec::new();

    for symbol in index
        .symbols
        .iter()
        .filter(|symbol| symbol.file_id == file_id)
    {
        if let Some(parent_symbol_id) = symbol.parent_symbol_id {
            bindings
                .entry(parent_symbol_id)
                .or_default()
                .insert(symbol.name.to_string());
        }
    }

    collect_local_bindings_from_node(
        source,
        root,
        symbol_ranges,
        &mut bindings,
        &mut global_declarations,
        &mut scoped_bindings,
    );
    for (symbol_id, names) in global_declarations {
        if let Some(bindings) = bindings.get_mut(&symbol_id) {
            bindings.retain(|name| !names.contains(name));
        }
    }
    (bindings, scoped_bindings)
}

fn collect_local_bindings_from_node(
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    bindings: &mut HashMap<u32, HashSet<String>>,
    global_declarations: &mut HashMap<u32, HashSet<String>>,
    scoped_bindings: &mut Vec<LocalBindingScope>,
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
        "lambda" => {
            push_lambda_binding_scope(source, node, symbol_ranges, scoped_bindings);
        }
        "list_comprehension"
        | "set_comprehension"
        | "dictionary_comprehension"
        | "generator_expression" => {
            push_comprehension_binding_scope(source, node, symbol_ranges, scoped_bindings);
        }
        "global_statement" => {
            if let Some(source_symbol_id) =
                innermost_symbol_for_range(symbol_ranges, node.range().into())
            {
                for name in declaration_names(source, node) {
                    global_declarations
                        .entry(source_symbol_id)
                        .or_default()
                        .insert(name);
                }
            }
            return;
        }
        "nonlocal_statement" => {
            if let Some(source_symbol_id) =
                innermost_symbol_for_range(symbol_ranges, node.range().into())
            {
                bindings
                    .entry(source_symbol_id)
                    .or_default()
                    .extend(declaration_names(source, node));
            }
            return;
        }
        "assignment" | "annotated_assignment" | "augmented_assignment" => {
            if let Some(left) = node.child_by_field_name("left") {
                push_local_binding_targets(source, left, symbol_ranges, bindings);
            }
            if let Some(right) = node.child_by_field_name("right") {
                collect_local_bindings_from_node(
                    source,
                    right,
                    symbol_ranges,
                    bindings,
                    global_declarations,
                    scoped_bindings,
                );
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
        "case_clause" => {
            push_match_pattern_binding_targets(source, node, symbol_ranges, bindings);
        }
        "import_statement" | "import_from_statement" | "future_import_statement" => {
            return;
        }
        _ => {}
    }

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_local_bindings_from_node(
            source,
            child,
            symbol_ranges,
            bindings,
            global_declarations,
            scoped_bindings,
        );
    }
}

fn declaration_names(source: &str, node: Node<'_>) -> Vec<String> {
    let mut names = Vec::new();
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        if child.kind() != "identifier" {
            continue;
        }
        if let Ok(name) = child.utf8_text(source.as_bytes()) {
            names.push(name.to_owned());
        }
    }
    names
}

fn push_comprehension_binding_scope(
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    scoped_bindings: &mut Vec<LocalBindingScope>,
) {
    let Some(source_symbol_id) = innermost_symbol_for_range(symbol_ranges, node.range().into())
    else {
        return;
    };

    let mut targets = Vec::new();
    collect_comprehension_targets(node, &mut targets);
    let mut names = HashSet::new();
    for target in targets {
        if let Ok(name) = target.utf8_text(source.as_bytes()) {
            names.insert(name.to_owned());
        }
    }
    if !names.is_empty() {
        scoped_bindings.push(LocalBindingScope {
            source_symbol_id,
            range: node.range().into(),
            names,
        });
    }
}

fn collect_comprehension_targets<'tree>(node: Node<'tree>, out: &mut Vec<Node<'tree>>) {
    if node.kind() == "for_in_clause" {
        if let Some(left) = node.child_by_field_name("left") {
            collect_assignment_targets(left, out);
        }
        return;
    }

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        collect_comprehension_targets(child, out);
    }
}

fn push_lambda_binding_scope(
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    scoped_bindings: &mut Vec<LocalBindingScope>,
) {
    let Some(parameters) = node.child_by_field_name("parameters") else {
        return;
    };
    let Some(body) = node.child_by_field_name("body") else {
        return;
    };
    let Some(source_symbol_id) = innermost_symbol_for_range(symbol_ranges, body.range().into())
    else {
        return;
    };

    let mut targets = Vec::new();
    collect_parameter_targets(parameters, &mut targets);
    let mut names = HashSet::new();
    for target in targets {
        if let Ok(name) = target.utf8_text(source.as_bytes()) {
            names.insert(name.to_owned());
        }
    }
    if !names.is_empty() {
        scoped_bindings.push(LocalBindingScope {
            source_symbol_id,
            range: body.range().into(),
            names,
        });
    }
}

fn push_match_pattern_binding_targets(
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    bindings: &mut HashMap<u32, HashSet<String>>,
) {
    let mut targets = Vec::new();
    collect_case_clause_binding_targets(node, &mut targets);
    for target in targets {
        push_local_binding_targets(source, target, symbol_ranges, bindings);
    }
}

fn collect_case_clause_binding_targets<'tree>(node: Node<'tree>, out: &mut Vec<Node<'tree>>) {
    let mut cursor = node.walk();
    for (index, child) in node.children(&mut cursor).enumerate() {
        if !child.is_named() || node.field_name_for_child(index as u32).is_some() {
            continue;
        }
        if child.kind() == "case_pattern" {
            collect_match_pattern_targets(child, out);
        }
    }
}

fn collect_match_pattern_targets<'tree>(node: Node<'tree>, out: &mut Vec<Node<'tree>>) {
    match node.kind() {
        "identifier" => out.push(node),
        "dotted_name" => {
            let mut cursor = node.walk();
            let identifiers: Vec<_> = node
                .named_children(&mut cursor)
                .filter(|child| child.kind() == "identifier")
                .collect();
            if identifiers.len() == 1 {
                out.push(identifiers[0]);
            }
        }
        "dict_pattern" => {
            let mut cursor = node.walk();
            for child in node.children_by_field_name("value", &mut cursor) {
                collect_match_pattern_targets(child, out);
            }
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                if child.kind() == "splat_pattern" {
                    collect_match_pattern_targets(child, out);
                }
            }
        }
        "class_pattern" => {
            let mut seen_constructor = false;
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                if !seen_constructor && child.kind() == "dotted_name" {
                    seen_constructor = true;
                    continue;
                }
                collect_match_pattern_targets(child, out);
            }
        }
        "keyword_pattern" => {
            let mut skipped_keyword = false;
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                if !skipped_keyword && child.kind() == "identifier" {
                    skipped_keyword = true;
                    continue;
                }
                collect_match_pattern_targets(child, out);
            }
        }
        "case_pattern" | "as_pattern" | "list_pattern" | "tuple_pattern" | "splat_pattern"
        | "union_pattern" => {
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                collect_match_pattern_targets(child, out);
            }
        }
        _ => {}
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
        "parameters" | "lambda_parameters" => {
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

fn collect_identifier_candidates(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    excluded_ranges: &[SourceRange],
    out: &mut Vec<ReferenceCandidate>,
) {
    if node.kind() == "lambda_parameters" {
        collect_lambda_parameter_value_identifier_candidates(
            file_id,
            source,
            node,
            symbol_ranges,
            local_bindings_by_symbol_id,
            local_binding_scopes,
            excluded_ranges,
            out,
        );
        return;
    }

    if node.kind() == "attribute" {
        if let (Some(object), Some(attribute)) = (
            node.child_by_field_name("object"),
            node.child_by_field_name("attribute"),
        ) {
            let range = attribute.range().into();
            if attribute.kind() == "identifier" && !range_matches_any(range, excluded_ranges) {
                if let (Ok(qualifier), Ok(name)) = (
                    object.utf8_text(source.as_bytes()),
                    attribute.utf8_text(source.as_bytes()),
                ) {
                    let source_symbol_id = innermost_symbol_for_range(symbol_ranges, range);
                    if !qualified_reference_is_shadowed(
                        source_symbol_id,
                        qualifier,
                        object.range().into(),
                        local_bindings_by_symbol_id,
                        local_binding_scopes,
                    ) {
                        out.push(ReferenceCandidate {
                            source_file_id: file_id,
                            source_symbol_id,
                            name: name.to_owned(),
                            qualifier: Some(qualifier.to_owned()),
                            range,
                            is_subclass: false,
                            call_range: None,
                        });
                    }
                }
            }
        }
        if let Some(object) = node.child_by_field_name("object") {
            collect_identifier_candidates(
                file_id,
                source,
                object,
                symbol_ranges,
                local_bindings_by_symbol_id,
                local_binding_scopes,
                excluded_ranges,
                out,
            );
        }
        return;
    }

    if matches!(
        node.kind(),
        "import_statement"
            | "import_from_statement"
            | "future_import_statement"
            | "global_statement"
            | "nonlocal_statement"
    ) {
        return;
    }

    let range = node.range().into();
    if node.kind() == "identifier" && !range_matches_any(range, excluded_ranges) {
        if let Ok(name) = node.utf8_text(source.as_bytes()) {
            let source_symbol_id = innermost_symbol_for_range(symbol_ranges, range);
            if is_shadowed_local_binding(
                source_symbol_id,
                name,
                range,
                local_bindings_by_symbol_id,
                local_binding_scopes,
            ) {
                return;
            }
            out.push(ReferenceCandidate {
                source_file_id: file_id,
                source_symbol_id,
                name: name.to_owned(),
                qualifier: None,
                range,
                is_subclass: false,
                call_range: None,
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
            local_binding_scopes,
            excluded_ranges,
            out,
        );
    }
}

fn qualified_reference_is_shadowed(
    source_symbol_id: Option<u32>,
    qualifier: &str,
    range: SourceRange,
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
) -> bool {
    let binding = qualifier.split('.').next().unwrap_or(qualifier);
    is_shadowed_local_binding(
        source_symbol_id,
        binding,
        range,
        local_bindings_by_symbol_id,
        local_binding_scopes,
    )
}

fn collect_lambda_parameter_value_identifier_candidates(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    symbol_ranges: &[(u32, SourceRange)],
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
    excluded_ranges: &[SourceRange],
    out: &mut Vec<ReferenceCandidate>,
) {
    match node.kind() {
        "default_parameter" | "typed_default_parameter" => {
            if let Some(value) = node.child_by_field_name("value") {
                collect_identifier_candidates(
                    file_id,
                    source,
                    value,
                    symbol_ranges,
                    local_bindings_by_symbol_id,
                    local_binding_scopes,
                    excluded_ranges,
                    out,
                );
            }
        }
        "lambda_parameters" => {
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                collect_lambda_parameter_value_identifier_candidates(
                    file_id,
                    source,
                    child,
                    symbol_ranges,
                    local_bindings_by_symbol_id,
                    local_binding_scopes,
                    excluded_ranges,
                    out,
                );
            }
        }
        _ => {}
    }
}

fn is_shadowed_local_binding(
    source_symbol_id: Option<u32>,
    name: &str,
    range: SourceRange,
    local_bindings_by_symbol_id: &HashMap<u32, HashSet<String>>,
    local_binding_scopes: &[LocalBindingScope],
) -> bool {
    let Some(source_symbol_id) = source_symbol_id else {
        return false;
    };
    if local_bindings_by_symbol_id
        .get(&source_symbol_id)
        .is_some_and(|bindings| bindings.contains(name))
    {
        return true;
    }
    local_binding_scopes.iter().any(|scope| {
        scope.source_symbol_id == source_symbol_id
            && contains_range(scope.range, range)
            && scope.names.contains(name)
    })
}

fn innermost_symbol_for_range(
    symbol_ranges: &[(u32, SourceRange)],
    range: SourceRange,
) -> Option<u32> {
    innermost_symbol_range_for_range(symbol_ranges, range).map(|(symbol_id, _)| symbol_id)
}

fn innermost_symbol_range_for_range(
    symbol_ranges: &[(u32, SourceRange)],
    range: SourceRange,
) -> Option<(u32, SourceRange)> {
    symbol_ranges
        .iter()
        .filter(|(_, symbol_range)| contains_range(*symbol_range, range))
        .min_by_key(|(_, symbol_range)| symbol_range.end_byte - symbol_range.start_byte)
        .map(|(symbol_id, symbol_range)| (*symbol_id, *symbol_range))
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
        let name = index.intern(name);
        let alias = alias.map(|value| index.intern(value));
        index.imports.push(ImportRecord {
            id: index.imports.len() as u32,
            file_id,
            kind: ImportKind::Import,
            module: None,
            name: Some(name),
            alias,
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
        let module = index.intern(module.trim());
        let name = index.intern(name);
        let alias = alias.map(|value| index.intern(value));
        index.imports.push(ImportRecord {
            id: index.imports.len() as u32,
            file_id,
            kind,
            module: Some(module),
            name: Some(name),
            alias,
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
        .map(|symbol| ((symbol.file_id, symbol.name.as_ref()), symbol.id))
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
            ImportKind::SideEffect
            | ImportKind::DefaultImport
            | ImportKind::NamedImport
            | ImportKind::NamespaceImport
            | ImportKind::DynamicImport => None,
        };
        if let Some(resolution) = resolution {
            resolutions.push(resolution);
        }
    }
    index.import_resolutions = resolutions;
    resolve_python_reexport_imports(index);
    index.external_modules = build_external_modules(&index.imports, &index.import_resolutions);
}

fn resolve_python_reexport_imports(index: &mut PythonIndex) {
    let import_by_id: HashMap<u32, &ImportRecord> = index
        .imports
        .iter()
        .map(|import| (import.id, import))
        .collect();

    for _ in 0..index.import_resolutions.len() {
        let exported_symbols_by_file = python_exported_symbols_by_file(index);

        let mut changed = false;
        for resolution in &mut index.import_resolutions {
            if resolution.target_symbol_id.is_some() {
                continue;
            }
            let Some(import) = import_by_id.get(&resolution.import_id) else {
                continue;
            };
            if import.kind != ImportKind::FromImport {
                continue;
            }
            let Some(name) = import.name.as_deref() else {
                continue;
            };
            if name == "*" {
                continue;
            }
            if let Some(target_symbol_id) = exported_symbols_by_file
                .get(&resolution.target_file_id)
                .and_then(|exports| exports.get(name))
            {
                resolution.target_symbol_id = Some(*target_symbol_id);
                changed = true;
            }
        }

        if !changed {
            break;
        }
    }
}

fn python_exported_symbols_by_file(index: &PythonIndex) -> ExportedSymbolsByFile {
    let resolution_by_import_id: HashMap<u32, &ImportResolutionRecord> = index
        .import_resolutions
        .iter()
        .map(|resolution| (resolution.import_id, resolution))
        .collect();
    let mut exports: ExportedSymbolsByFile = HashMap::new();

    for symbol in index.symbols.iter().filter(|symbol| symbol.is_top_level) {
        exports
            .entry(symbol.file_id)
            .or_default()
            .insert(symbol.name.to_string(), symbol.id);
    }

    for _ in 0..index.imports.len().max(1) {
        let previous_exports = exports.clone();

        for import in &index.imports {
            if import.kind == ImportKind::FutureImport {
                continue;
            }
            let Some(resolution) = resolution_by_import_id.get(&import.id) else {
                continue;
            };
            if is_wildcard_import(import) {
                let Some(target_exports) = previous_exports.get(&resolution.target_file_id) else {
                    continue;
                };
                let file_exports = exports.entry(import.file_id).or_default();
                for (name, target_symbol_id) in
                    wildcard_visible_exports(index, resolution.target_file_id, target_exports)
                {
                    file_exports.insert(name.clone(), *target_symbol_id);
                }
                continue;
            }

            let Some(binding) = import_binding_name(import) else {
                continue;
            };
            let Some(target_symbol_id) = resolution.target_symbol_id else {
                continue;
            };
            exports
                .entry(import.file_id)
                .or_default()
                .insert(binding, target_symbol_id);
        }

        if exports == previous_exports {
            break;
        }
    }

    exports
}

fn wildcard_visible_exports<'a>(
    index: &'a PythonIndex,
    file_id: u32,
    exports: &'a BTreeMap<String, u32>,
) -> Vec<(&'a String, &'a u32)> {
    let Some(all_exports) = index.all_exports_by_file.get(&file_id) else {
        return exports.iter().collect();
    };
    all_exports
        .iter()
        .filter_map(|name| exports.get_key_value(name))
        .collect()
}

fn resolve_python_references(index: &mut PythonIndex, candidates: Vec<ReferenceCandidate>) {
    let mut strings = std::mem::take(&mut index.strings);
    let module_to_file: HashMap<&str, u32> = index
        .files
        .iter()
        .filter_map(|file| file.module_name.as_deref().map(|module| (module, file.id)))
        .collect();
    let internal_module_prefixes = internal_python_module_prefixes(&index.files);
    let symbol_to_id: HashMap<(u32, &str), u32> = index
        .symbols
        .iter()
        .filter(|symbol| symbol.is_top_level)
        .map(|symbol| ((symbol.file_id, symbol.name.as_ref()), symbol.id))
        .collect();
    let resolution_by_import_id: HashMap<u32, &ImportResolutionRecord> = index
        .import_resolutions
        .iter()
        .map(|resolution| (resolution.import_id, resolution))
        .collect();
    let exported_symbols_by_file = python_exported_symbols_by_file(index);
    let mut imported_symbol_by_binding: HashMap<(u32, String), (u32, u32)> = HashMap::new();
    let mut local_imported_symbol_by_binding: HashMap<(u32, String), (u32, u32)> = HashMap::new();
    let mut imported_module_by_qualifier: HashMap<(u32, String), (u32, u32)> = HashMap::new();
    let mut imported_module_prefix_by_binding: HashMap<(u32, String), (String, u32)> =
        HashMap::new();
    let external_import_ids: HashSet<u32> = index
        .external_modules
        .iter()
        .map(|external_module| external_module.import_id)
        .collect();
    let mut external_import_by_binding: HashMap<(u32, String), u32> = HashMap::new();
    let mut local_external_import_by_binding: HashMap<(u32, String), u32> = HashMap::new();
    let symbol_ranges_by_file: HashMap<u32, Vec<(u32, SourceRange)>> =
        symbol_ranges_by_file(&index.symbols);

    for import in &index.imports {
        let import_source_symbol_id = symbol_ranges_by_file
            .get(&import.file_id)
            .and_then(|symbol_ranges| innermost_symbol_for_range(symbol_ranges, import.range));
        if external_import_ids.contains(&import.id) {
            if let Some(binding) = import_binding_name(import) {
                if let Some(source_symbol_id) = import_source_symbol_id {
                    local_external_import_by_binding.insert((source_symbol_id, binding), import.id);
                } else {
                    external_import_by_binding.insert((import.file_id, binding), import.id);
                }
            }
        }
        if let Some(source_file) = index.files.get(import.file_id as usize) {
            for (binding, module_prefix) in
                import_module_prefix_bindings(import, source_file, &internal_module_prefixes)
            {
                imported_module_prefix_by_binding
                    .insert((import.file_id, binding), (module_prefix, import.id));
            }
        }
        let resolution = resolution_by_import_id.get(&import.id);
        if is_wildcard_import(import) {
            if let Some(resolution) = resolution {
                if let Some(target_exports) =
                    exported_symbols_by_file.get(&resolution.target_file_id)
                {
                    for (binding, target_symbol_id) in
                        wildcard_visible_exports(index, resolution.target_file_id, target_exports)
                    {
                        imported_symbol_by_binding.insert(
                            (import.file_id, binding.clone()),
                            (*target_symbol_id, import.id),
                        );
                    }
                }
            }
            continue;
        }
        let Some(resolution) = resolution else {
            continue;
        };
        if resolution.target_symbol_id.is_none() {
            for qualifier in import_module_qualifiers(import) {
                imported_module_by_qualifier.insert(
                    (import.file_id, qualifier),
                    (resolution.target_file_id, import.id),
                );
            }
        }
        let Some(target_symbol_id) = resolution.target_symbol_id else {
            continue;
        };
        let Some(binding) = import_binding_name(import) else {
            continue;
        };
        if let Some(source_symbol_id) = import_source_symbol_id {
            local_imported_symbol_by_binding
                .insert((source_symbol_id, binding), (target_symbol_id, import.id));
        } else {
            imported_symbol_by_binding
                .insert((import.file_id, binding), (target_symbol_id, import.id));
        }
    }

    let mut references = Vec::new();
    let mut external_references = Vec::new();
    for candidate in candidates {
        let resolved_target = if let Some(qualifier) = candidate.qualifier.as_ref() {
            imported_module_by_qualifier
                .get(&(candidate.source_file_id, qualifier.clone()))
                .and_then(|(target_file_id, import_id)| {
                    symbol_to_id
                        .get(&(*target_file_id, candidate.name.as_str()))
                        .copied()
                        .map(|symbol_id| (symbol_id, Some(*import_id)))
                })
                .or_else(|| {
                    resolve_imported_module_attribute(
                        candidate.source_file_id,
                        qualifier,
                        &candidate.name,
                        &imported_module_prefix_by_binding,
                        &module_to_file,
                        &symbol_to_id,
                    )
                })
        } else {
            let local_external_import_id =
                candidate.source_symbol_id.and_then(|source_symbol_id| {
                    local_external_import_by_binding
                        .get(&(source_symbol_id, candidate.name.clone()))
                        .copied()
                });
            let local_imported_target = candidate.source_symbol_id.and_then(|source_symbol_id| {
                local_imported_symbol_by_binding
                    .get(&(source_symbol_id, candidate.name.clone()))
                    .copied()
            });
            let imported_target = imported_symbol_by_binding
                .get(&(candidate.source_file_id, candidate.name.clone()))
                .copied();
            let same_file_target = symbol_to_id
                .get(&(candidate.source_file_id, candidate.name.as_str()))
                .copied()
                .map(|symbol_id| (symbol_id, None));
            if local_external_import_id.is_some() {
                None
            } else {
                local_imported_target
                    .or(imported_target)
                    .map(|(symbol_id, import_id)| (symbol_id, Some(import_id)))
                    .or(same_file_target)
            }
        };
        let Some((target_symbol_id, import_id)) = resolved_target else {
            if candidate.qualifier.is_none() {
                let local_import_id = candidate.source_symbol_id.and_then(|source_symbol_id| {
                    local_external_import_by_binding
                        .get(&(source_symbol_id, candidate.name.clone()))
                        .copied()
                });
                if let Some(import_id) = local_import_id.or_else(|| {
                    external_import_by_binding
                        .get(&(candidate.source_file_id, candidate.name.clone()))
                        .copied()
                }) {
                    let name = strings.intern(&candidate.name);
                    external_references.push(ExternalReferenceRecord {
                        id: external_references.len() as u32,
                        source_file_id: candidate.source_file_id,
                        source_symbol_id: candidate.source_symbol_id,
                        import_id,
                        name,
                        range: candidate.range,
                    });
                }
            }
            continue;
        };
        if candidate.source_symbol_id == Some(target_symbol_id) {
            continue;
        }

        let name = strings.intern(&candidate.name);
        references.push(ReferenceRecord {
            id: references.len() as u32,
            source_file_id: candidate.source_file_id,
            source_symbol_id: candidate.source_symbol_id,
            target_symbol_id,
            import_id,
            name,
            range: candidate.range,
        });
    }
    index.references = references;
    index.external_references = external_references;
    index.strings = strings;
}

fn symbol_ranges_by_file(symbols: &[SymbolRecord]) -> HashMap<u32, Vec<(u32, SourceRange)>> {
    let mut ranges_by_file: HashMap<u32, Vec<(u32, SourceRange)>> = HashMap::new();
    for symbol in symbols {
        ranges_by_file
            .entry(symbol.file_id)
            .or_default()
            .push((symbol.id, symbol.range));
    }
    ranges_by_file
}

fn internal_python_module_prefixes(files: &[FileRecord]) -> HashSet<String> {
    let mut prefixes = HashSet::new();
    for module in files.iter().filter_map(|file| file.module_name.as_deref()) {
        let parts = module.split('.').collect::<Vec<_>>();
        for i in 1..=parts.len() {
            prefixes.insert(parts[..i].join("."));
        }
    }
    prefixes
}

fn import_module_prefix_bindings(
    import: &ImportRecord,
    source_file: &FileRecord,
    internal_module_prefixes: &HashSet<String>,
) -> Vec<(String, String)> {
    if is_wildcard_import(import) || import.kind == ImportKind::FutureImport {
        return Vec::new();
    }

    let mut bindings = Vec::new();
    match import.kind {
        ImportKind::Import => {
            let Some(name) = import.name.as_deref() else {
                return bindings;
            };
            if let Some(alias) = import.alias.as_deref() {
                if internal_module_prefixes.contains(name) {
                    bindings.push((alias.to_owned(), name.to_owned()));
                }
            } else if let Some(root) = name.split('.').next() {
                if internal_module_prefixes.contains(root) {
                    bindings.push((root.to_owned(), root.to_owned()));
                }
            }
        }
        ImportKind::FromImport => {
            let Some(module) = import
                .module
                .as_deref()
                .and_then(|module| resolve_module_name(source_file, module))
            else {
                return bindings;
            };
            let Some(name) = import.name.as_deref() else {
                return bindings;
            };
            let binding = import.alias.as_deref().unwrap_or(name);
            let module_prefix = join_module(&module, name);
            if internal_module_prefixes.contains(&module_prefix) {
                bindings.push((binding.to_owned(), module_prefix));
            }
        }
        ImportKind::FutureImport => {}
        ImportKind::SideEffect
        | ImportKind::DefaultImport
        | ImportKind::NamedImport
        | ImportKind::NamespaceImport
        | ImportKind::DynamicImport => {}
    }
    bindings
}

fn resolve_imported_module_attribute(
    source_file_id: u32,
    qualifier: &str,
    name: &str,
    imported_module_prefix_by_binding: &HashMap<(u32, String), (String, u32)>,
    module_to_file: &HashMap<&str, u32>,
    symbol_to_id: &HashMap<(u32, &str), u32>,
) -> Option<(u32, Option<u32>)> {
    let (binding, suffix) = qualifier
        .split_once('.')
        .map_or((qualifier, None), |(binding, suffix)| {
            (binding, Some(suffix))
        });
    let (module_prefix, import_id) =
        imported_module_prefix_by_binding.get(&(source_file_id, binding.to_owned()))?;
    let target_module = suffix.map_or_else(
        || module_prefix.clone(),
        |suffix| join_module(module_prefix, suffix),
    );
    let target_file_id = module_to_file.get(target_module.as_str()).copied()?;
    let target_symbol_id = symbol_to_id.get(&(target_file_id, name)).copied()?;
    Some((target_symbol_id, Some(*import_id)))
}

fn import_module_qualifiers(import: &ImportRecord) -> Vec<String> {
    let mut qualifiers = Vec::new();
    if let Some(alias) = import.alias.as_deref() {
        qualifiers.push(alias.to_owned());
    }
    match import.kind {
        ImportKind::Import => {
            if let Some(name) = import.name.as_deref() {
                qualifiers.push(name.to_owned());
            }
        }
        ImportKind::FromImport | ImportKind::FutureImport => {
            if import.alias.is_none() {
                if let Some(name) = import.name.as_deref() {
                    qualifiers.push(name.to_owned());
                }
            }
        }
        ImportKind::SideEffect
        | ImportKind::DefaultImport
        | ImportKind::NamedImport
        | ImportKind::NamespaceImport
        | ImportKind::DynamicImport => {}
    }
    qualifiers.sort();
    qualifiers.dedup();
    qualifiers
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
        ImportKind::FromImport | ImportKind::FutureImport => import
            .name
            .as_ref()
            .filter(|name| name.as_ref() != "*")
            .map(|name| name.to_string()),
        ImportKind::SideEffect
        | ImportKind::DefaultImport
        | ImportKind::NamedImport
        | ImportKind::NamespaceImport
        | ImportKind::DynamicImport => None,
    }
}

fn is_wildcard_import(import: &ImportRecord) -> bool {
    matches!(
        import.kind,
        ImportKind::FromImport | ImportKind::FutureImport
    ) && import.name.as_deref() == Some("*")
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
    if file.path.ends_with("/__init__.py") || file.path.as_ref() == "__init__.py" {
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
        assert_eq!(
            info.enabled_features(),
            ["skeleton", "python-index", "typescript-index"]
        );
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
        assert_eq!(index.external_modules.len(), 2);
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
        assert!(index.external_modules.iter().any(|external_module| {
            external_module.name == "os" && external_module.alias.is_none()
        }));
        assert!(index.external_modules.iter().any(|external_module| {
            external_module.name == "sys" && external_module.alias.as_deref() == Some("system")
        }));
    }

    #[test]
    fn compact_python_records_intern_repeated_strings() {
        let repo = temp_repo_path("python-interned-record-strings");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(
            repo.join("pkg/a.py"),
            "import requests\n\ndef fetch_a():\n    return requests.get('/a')\n",
        )
        .unwrap();
        fs::write(
            repo.join("pkg/b.py"),
            "import requests\n\ndef fetch_b():\n    return requests.post('/b')\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.strings.len(), 0);
        let import_names = index
            .imports
            .iter()
            .filter_map(|import| import.name.as_ref())
            .filter(|name| name.as_ref() == "requests")
            .collect::<Vec<_>>();
        let external_module_names = index
            .external_modules
            .iter()
            .filter(|module| module.name.as_ref() == "requests")
            .map(|module| &module.name)
            .collect::<Vec<_>>();
        let external_reference_names = index
            .external_references
            .iter()
            .filter(|reference| reference.name.as_ref() == "requests")
            .map(|reference| &reference.name)
            .collect::<Vec<_>>();

        assert_eq!(import_names.len(), 2);
        assert_eq!(external_module_names.len(), 2);
        assert_eq!(external_reference_names.len(), 2);
        assert!(import_names[0].ptr_eq(import_names[1]));
        assert!(import_names[0].ptr_eq(external_module_names[0]));
        assert!(import_names[0].ptr_eq(external_reference_names[0]));
    }

    #[test]
    fn resolves_python_external_import_references() {
        let repo = temp_repo_path("python-external-import-references");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(
            repo.join("pkg/service.py"),
            "import requests\n\ndef run():\n    return requests.get('/health')\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 1);
        assert_eq!(index.summary().imports, 1);
        assert_eq!(index.external_modules.len(), 1);
        assert_eq!(index.summary().references, 0);
        assert_eq!(index.summary().dependencies, 0);
        assert_eq!(index.external_references.len(), 1);

        let import = index
            .imports
            .iter()
            .find(|import| import.name.as_deref() == Some("requests"))
            .unwrap();
        let run = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "run")
            .unwrap();
        let reference = &index.external_references[0];

        assert_eq!(reference.source_symbol_id, Some(run.id));
        assert_eq!(reference.import_id, import.id);
        assert_eq!(reference.name, "requests");
        assert_eq!(reference.range.start_row, 3);
        assert_eq!(reference.range.start_column, 11);
    }

    #[test]
    fn resolves_python_function_local_external_import_references() {
        let repo = temp_repo_path("python-local-external-import-references");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(
            repo.join("pkg/service.py"),
            "def load(name):\n    import importlib\n    return importlib.import_module(name)\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 1);
        assert_eq!(index.summary().imports, 1);
        assert_eq!(index.external_modules.len(), 1);
        assert_eq!(index.summary().references, 0);
        assert_eq!(index.summary().dependencies, 0);
        assert_eq!(index.external_references.len(), 1);

        let import = index
            .imports
            .iter()
            .find(|import| import.name.as_deref() == Some("importlib"))
            .unwrap();
        let load = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "load")
            .unwrap();
        let reference = &index.external_references[0];

        assert_eq!(reference.source_symbol_id, Some(load.id));
        assert_eq!(reference.import_id, import.id);
        assert_eq!(reference.name, "importlib");
        assert_eq!(reference.range.start_row, 2);
        assert_eq!(reference.range.start_column, 11);
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
    fn indexes_typescript_syntax_records_without_resolution() {
        let repo = temp_repo_path("index-typescript");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.tsx"),
            r#"import React, { useState as useStateAlias, type FC } from "react";
import * as utils from "./utils";
import "./setup";

export { helper as publicHelper } from "./utils";
export * as allUtils from "./utils";
export const value = 1;
export function run() {}
export default function Page() {}
interface Props {}
type Alias = string;
enum Mode { A }
namespace Inner { export const x = 1 }
const loader = await import("./loader");
const { parse, format: fmt } = require("./format");
const Component = () => <div />;
"#,
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 1);
        assert_eq!(index.summary().classes, 0);
        assert_eq!(index.summary().functions, 3);
        assert_eq!(index.summary().global_variables, 5);
        assert_eq!(index.files[0].path, "src/app.tsx");
        assert_eq!(index.imports.len(), 10);
        assert_eq!(index.exports.len(), 5);
        assert_eq!(index.summary().import_resolutions, 0);
        assert_eq!(index.external_modules.len(), 3);
        assert_eq!(index.summary().references, 0);
        assert_eq!(index.summary().dependencies, 0);

        let symbols = index
            .symbols
            .iter()
            .map(|symbol| (symbol.name.as_ref(), symbol.kind))
            .collect::<Vec<_>>();
        assert!(symbols.contains(&("run", SymbolKind::Function)));
        assert!(symbols.contains(&("Page", SymbolKind::Function)));
        assert!(symbols.contains(&("Component", SymbolKind::Function)));
        assert!(symbols.contains(&("Props", SymbolKind::Interface)));
        assert!(symbols.contains(&("Alias", SymbolKind::TypeAlias)));
        assert!(symbols.contains(&("Mode", SymbolKind::Enum)));
        assert!(symbols.contains(&("Inner", SymbolKind::Namespace)));
        assert!(symbols.contains(&("x", SymbolKind::GlobalVariable)));
        assert!(symbols.contains(&("value", SymbolKind::GlobalVariable)));
        assert!(symbols.contains(&("loader", SymbolKind::GlobalVariable)));
        assert!(symbols.contains(&("parse", SymbolKind::GlobalVariable)));
        assert!(symbols.contains(&("fmt", SymbolKind::GlobalVariable)));
        let inner = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "Inner")
            .unwrap();
        let x = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "x")
            .unwrap();
        assert_eq!(x.parent_symbol_id, Some(inner.id));
        assert!(!x.is_top_level);

        assert!(index.imports.iter().any(|import| {
            import.kind == ImportKind::DefaultImport
                && import.module.as_deref() == Some("react")
                && import.name.as_deref() == Some("React")
                && import.alias.as_deref() == Some("React")
        }));
        assert!(index.imports.iter().any(|import| {
            import.kind == ImportKind::NamedImport
                && import.module.as_deref() == Some("react")
                && import.name.as_deref() == Some("useState")
                && import.alias.as_deref() == Some("useStateAlias")
        }));
        assert!(index.imports.iter().any(|import| {
            import.kind == ImportKind::NamespaceImport
                && import.module.as_deref() == Some("./utils")
                && import.alias.as_deref() == Some("utils")
        }));
        assert!(index.imports.iter().any(|import| {
            import.kind == ImportKind::SideEffect && import.module.as_deref() == Some("./setup")
        }));
        assert!(index.imports.iter().any(|import| {
            import.kind == ImportKind::DynamicImport
                && import.module.as_deref() == Some("./loader")
                && import.alias.as_deref() == Some("loader")
        }));
        assert!(index.imports.iter().any(|import| {
            import.kind == ImportKind::DynamicImport
                && import.module.as_deref() == Some("./format")
                && import.alias.as_deref() == Some("fmt")
        }));
        assert!(index.external_modules.iter().any(|external_module| {
            external_module.name == "React"
                && external_module.module.as_deref() == Some("react")
                && external_module.alias.as_deref() == Some("React")
        }));
        assert!(index
            .external_modules
            .iter()
            .any(|external_module| external_module.name == "useState"));
        assert!(index
            .external_modules
            .iter()
            .any(|external_module| external_module.name == "FC"));

        assert!(index.exports.iter().any(|export| {
            export.kind == ExportKind::Named
                && export.name.as_deref() == Some("publicHelper")
                && export.local_name.as_deref() == Some("helper")
                && export.source_module.as_deref() == Some("./utils")
                && export.import_id.is_some()
        }));
        assert!(index.exports.iter().any(|export| {
            export.kind == ExportKind::Namespace
                && export.name.as_deref() == Some("allUtils")
                && export.source_module.as_deref() == Some("./utils")
        }));
        assert!(index.exports.iter().any(|export| {
            export.kind == ExportKind::Named
                && export.name.as_deref() == Some("value")
                && export.symbol_id.is_some()
        }));
        assert!(index.exports.iter().any(|export| {
            export.kind == ExportKind::Named
                && export.name.as_deref() == Some("run")
                && export.symbol_id.is_some()
        }));
        assert!(index.exports.iter().any(|export| {
            export.kind == ExportKind::Default
                && export.name.as_deref() == Some("default")
                && export.local_name.as_deref() == Some("Page")
                && export.symbol_id.is_some()
        }));
    }

    #[test]
    fn indexes_only_requested_typescript_like_paths() {
        let repo = temp_repo_path("index-typescript-paths");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(repo.join("src/included.ts"), "export class Included {}\n").unwrap();
        fs::write(repo.join("src/skipped.ts"), "export class Skipped {}\n").unwrap();
        fs::write(
            repo.join("src/not-ts.py"),
            "class NotTypeScript:\n    pass\n",
        )
        .unwrap();

        let index = index_typescript_paths(&repo, ["src/included.ts", "src/not-ts.py"]).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 1);
        assert_eq!(index.files[0].path, "src/included.ts");
        assert_eq!(index.summary().classes, 1);
        assert_eq!(index.symbols[0].name, "Included");
        assert_eq!(index.exports[0].name.as_deref(), Some("Included"));
    }

    #[test]
    fn resolves_relative_typescript_imports_to_files_and_symbols() {
        let repo = temp_repo_path("resolve-typescript-imports");
        fs::create_dir_all(repo.join("src/feature")).unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "import DefaultThing, { helper } from './utils';\n\
import * as utils from './utils';\n\
import { dotted } from './foo.test';\n\
import './setup';\n\
export { helper as publicHelper } from './utils';\n\
export * from './feature';\n\
",
        )
        .unwrap();
        fs::write(repo.join("src/setup.ts"), "window.__ready = true;\n").unwrap();
        fs::write(
            repo.join("src/utils.ts"),
            "export const helper = 1;\nexport default function DefaultThing() {}\n",
        )
        .unwrap();
        fs::write(repo.join("src/foo.test.ts"), "export const dotted = 1;\n").unwrap();
        fs::write(
            repo.join("src/feature/index.ts"),
            "export const feature = 1;\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 5);
        assert_eq!(index.summary().imports, 7);
        assert_eq!(index.summary().import_resolutions, 7);

        let utils_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/utils.ts")
            .unwrap()
            .id;
        let setup_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/setup.ts")
            .unwrap()
            .id;
        let feature_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/feature/index.ts")
            .unwrap()
            .id;
        let dotted_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/foo.test.ts")
            .unwrap()
            .id;
        let helper_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == utils_file_id && symbol.name == "helper")
            .unwrap()
            .id;
        let default_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == utils_file_id && symbol.name == "DefaultThing")
            .unwrap()
            .id;
        let dotted_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == dotted_file_id && symbol.name == "dotted")
            .unwrap()
            .id;

        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.target_file_id == utils_file_id
                && resolution.target_symbol_id == Some(default_symbol_id)
        }));
        assert_eq!(
            index
                .import_resolutions
                .iter()
                .filter(|resolution| {
                    resolution.target_file_id == utils_file_id
                        && resolution.target_symbol_id == Some(helper_symbol_id)
                })
                .count(),
            2
        );
        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.target_file_id == utils_file_id && resolution.target_symbol_id.is_none()
        }));
        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.target_file_id == setup_file_id && resolution.target_symbol_id.is_none()
        }));
        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.target_file_id == feature_file_id && resolution.target_symbol_id.is_none()
        }));
        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.target_file_id == dotted_file_id
                && resolution.target_symbol_id == Some(dotted_symbol_id)
        }));
    }

    #[test]
    fn resolves_typescript_barrel_reexports_to_symbols() {
        let repo = temp_repo_path("resolve-typescript-barrel-reexports");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "import { publicHelper, wildcarded } from './barrel';\n\
import { nestedHelper } from './nested';\n\
import * as barrel from './barrel';\n\
\n\
export function run() {\n\
  return publicHelper() + nestedHelper() + wildcarded + barrel.wildcarded;\n\
}\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/barrel.ts"),
            "export { helper as publicHelper } from './leaf';\n\
export * from './extra';\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/nested.ts"),
            "export { publicHelper as nestedHelper } from './barrel';\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/leaf.ts"),
            "export function helper() { return 1; }\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/extra.ts"),
            "export const wildcarded = 2;\nexport default function hidden() { return 0; }\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 5);
        assert_eq!(index.summary().imports, 7);
        assert_eq!(index.summary().import_resolutions, 7);
        assert_eq!(index.summary().references, 4);
        assert_eq!(index.summary().dependencies, 2);

        let leaf_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/leaf.ts")
            .unwrap()
            .id;
        let extra_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/extra.ts")
            .unwrap()
            .id;
        let helper_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == leaf_file_id && symbol.name == "helper")
            .unwrap()
            .id;
        let wildcarded_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == extra_file_id && symbol.name == "wildcarded")
            .unwrap()
            .id;

        let public_helper_import_id = index
            .imports
            .iter()
            .find(|import| {
                import.module.as_deref() == Some("./barrel")
                    && import.name.as_deref() == Some("publicHelper")
            })
            .unwrap()
            .id;
        let nested_helper_import_id = index
            .imports
            .iter()
            .find(|import| import.name.as_deref() == Some("nestedHelper"))
            .unwrap()
            .id;
        let wildcarded_import_id = index
            .imports
            .iter()
            .find(|import| {
                import.module.as_deref() == Some("./barrel")
                    && import.name.as_deref() == Some("wildcarded")
            })
            .unwrap()
            .id;
        let barrel_namespace_import_id = index
            .imports
            .iter()
            .find(|import| {
                import.kind == ImportKind::NamespaceImport
                    && import.alias.as_deref() == Some("barrel")
            })
            .unwrap()
            .id;

        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.import_id == public_helper_import_id
                && resolution.target_symbol_id == Some(helper_symbol_id)
        }));
        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.import_id == nested_helper_import_id
                && resolution.target_symbol_id == Some(helper_symbol_id)
        }));
        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.import_id == wildcarded_import_id
                && resolution.target_symbol_id == Some(wildcarded_symbol_id)
        }));
        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.import_id == barrel_namespace_import_id
                && resolution.target_symbol_id.is_none()
        }));
        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| reference.target_symbol_id == helper_symbol_id)
                .count(),
            2
        );
        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| reference.target_symbol_id == wildcarded_symbol_id)
                .count(),
            2
        );
    }

    #[test]
    fn resolves_typescript_named_namespace_reexport_member_references() {
        let repo = temp_repo_path("resolve-typescript-named-namespace-reexport");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "import { utils } from './barrel';\n\
\n\
export function run() {\n\
  return utils.helper();\n\
}\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/barrel.ts"),
            "export * as utils from './leaf';\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/leaf.ts"),
            "export function helper() { return 1; }\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 3);
        assert_eq!(index.summary().imports, 2);
        assert_eq!(index.summary().import_resolutions, 2);
        assert_eq!(index.summary().references, 1);
        assert_eq!(index.summary().dependencies, 1);

        let app_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/app.ts")
            .unwrap()
            .id;
        let barrel_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/barrel.ts")
            .unwrap()
            .id;
        let leaf_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/leaf.ts")
            .unwrap()
            .id;
        let run_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == app_file_id && symbol.name == "run")
            .unwrap()
            .id;
        let helper_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == leaf_file_id && symbol.name == "helper")
            .unwrap()
            .id;
        let utils_import_id = index
            .imports
            .iter()
            .find(|import| {
                import.file_id == app_file_id
                    && import.kind == ImportKind::NamedImport
                    && import.module.as_deref() == Some("./barrel")
                    && import.name.as_deref() == Some("utils")
                    && import.alias.as_deref() == Some("utils")
            })
            .unwrap()
            .id;
        let barrel_namespace_import_id = index
            .imports
            .iter()
            .find(|import| {
                import.file_id == barrel_file_id
                    && import.kind == ImportKind::NamespaceImport
                    && import.module.as_deref() == Some("./leaf")
                    && import.name.as_deref() == Some("*")
                    && import.alias.as_deref() == Some("utils")
            })
            .unwrap()
            .id;

        assert!(index.exports.iter().any(|export| {
            export.file_id == barrel_file_id
                && export.kind == ExportKind::Namespace
                && export.name.as_deref() == Some("utils")
                && export.import_id == Some(barrel_namespace_import_id)
        }));
        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.import_id == utils_import_id
                && resolution.target_file_id == barrel_file_id
                && resolution.target_symbol_id.is_none()
        }));
        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.import_id == barrel_namespace_import_id
                && resolution.target_file_id == leaf_file_id
                && resolution.target_symbol_id.is_none()
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(run_symbol_id)
                && reference.target_symbol_id == helper_symbol_id
                && reference.import_id == Some(utils_import_id)
                && reference.name == "helper"
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == run_symbol_id
                && dependency.target_symbol_id == helper_symbol_id
                && dependency.reference_count == 1
        }));
    }

    #[test]
    fn extracts_typescript_namespace_member_symbols() {
        let repo = temp_repo_path("extract-typescript-namespace-members");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "export namespace Math {\n\
  export function add(a: number, b: number) { return a + b; }\n\
  export interface Shape { area: number }\n\
  export type Mode = 'simple';\n\
  export enum Operation { Add }\n\
  export namespace Advanced { export const pi = 3.14; export function pow() {} }\n\
}\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        let file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/app.ts")
            .unwrap()
            .id;
        let math = index
            .symbols
            .iter()
            .find(|symbol| {
                symbol.file_id == file_id
                    && symbol.name == "Math"
                    && symbol.kind == SymbolKind::Namespace
                    && symbol.is_top_level
            })
            .unwrap();
        let advanced = index
            .symbols
            .iter()
            .find(|symbol| {
                symbol.file_id == file_id
                    && symbol.name == "Advanced"
                    && symbol.kind == SymbolKind::Namespace
                    && symbol.parent_symbol_id == Some(math.id)
                    && !symbol.is_top_level
            })
            .unwrap();
        let child_names = index
            .symbols
            .iter()
            .filter(|symbol| symbol.parent_symbol_id == Some(math.id))
            .map(|symbol| (symbol.name.to_string(), symbol.kind))
            .collect::<Vec<_>>();
        assert_eq!(
            child_names,
            vec![
                ("add".to_owned(), SymbolKind::Function),
                ("Shape".to_owned(), SymbolKind::Interface),
                ("Mode".to_owned(), SymbolKind::TypeAlias),
                ("Operation".to_owned(), SymbolKind::Enum),
                ("Advanced".to_owned(), SymbolKind::Namespace),
            ]
        );
        assert_eq!(
            index
                .symbols
                .iter()
                .filter(|symbol| symbol.parent_symbol_id == Some(advanced.id))
                .map(|symbol| (symbol.name.to_string(), symbol.kind))
                .collect::<Vec<_>>(),
            vec![
                ("pi".to_owned(), SymbolKind::GlobalVariable),
                ("pow".to_owned(), SymbolKind::Function),
            ]
        );
        assert_eq!(index.summary().symbols, 8);
        assert_eq!(index.summary().functions, 2);
        assert_eq!(index.summary().global_variables, 1);
    }

    #[test]
    fn excludes_typescript_references_shadowed_by_scoped_loop_and_catch_bindings() {
        let repo = temp_repo_path("resolve-typescript-scoped-bindings");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "import { Imported, Other } from './values';\n\
\n\
export function run(items: number[]) {\n\
  for (const Imported of items) {\n\
    Imported;\n\
  }\n\
  try {\n\
    throw new Error();\n\
  } catch (Other) {\n\
    Other;\n\
  }\n\
  return Imported + Other;\n\
}\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/values.ts"),
            "export const Imported = 1;\nexport const Other = 2;\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 2);
        assert_eq!(index.summary().imports, 2);
        assert_eq!(index.summary().import_resolutions, 2);
        assert_eq!(index.summary().references, 2);
        assert_eq!(index.summary().dependencies, 2);

        let values_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/values.ts")
            .unwrap()
            .id;
        let imported_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == values_file_id && symbol.name == "Imported")
            .unwrap()
            .id;
        let other_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == values_file_id && symbol.name == "Other")
            .unwrap()
            .id;

        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| reference.target_symbol_id == imported_symbol_id)
                .count(),
            1
        );
        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| reference.target_symbol_id == other_symbol_id)
                .count(),
            1
        );
    }

    #[test]
    fn scopes_typescript_nested_callback_parameter_shadows_to_callback_body() {
        let repo = temp_repo_path("resolve-typescript-nested-callback-params");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "import { Imported } from './values';\n\
\n\
export function run(items: number[]) {\n\
  const before = Imported;\n\
  items.map((Imported) => Imported + 1);\n\
  return Imported + before;\n\
}\n",
        )
        .unwrap();
        fs::write(repo.join("src/values.ts"), "export const Imported = 1;\n").unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 2);
        assert_eq!(index.summary().imports, 1);
        assert_eq!(index.summary().import_resolutions, 1);
        assert_eq!(index.summary().references, 2);
        assert_eq!(index.summary().dependencies, 1);

        let values_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/values.ts")
            .unwrap()
            .id;
        let imported_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == values_file_id && symbol.name == "Imported")
            .unwrap()
            .id;

        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| reference.target_symbol_id == imported_symbol_id)
                .count(),
            2
        );
    }

    #[test]
    fn excludes_typescript_references_shadowed_by_nested_declarations() {
        let repo = temp_repo_path("resolve-typescript-nested-declaration-shadows");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "import { Imported, Other, StillImported } from './values';\n\
\n\
export function run() {\n\
  function Imported() { return 1; }\n\
  class Other {}\n\
  return Imported() + new Other() + StillImported;\n\
}\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/values.ts"),
            "export const Imported = 1;\nexport const Other = 2;\nexport const StillImported = 3;\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 2);
        assert_eq!(index.summary().imports, 3);
        assert_eq!(index.summary().import_resolutions, 3);
        assert_eq!(index.summary().references, 1);
        assert_eq!(index.summary().dependencies, 1);

        let values_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/values.ts")
            .unwrap()
            .id;
        let still_imported_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == values_file_id && symbol.name == "StillImported")
            .unwrap()
            .id;

        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| reference.target_symbol_id == still_imported_symbol_id)
                .count(),
            1
        );
    }

    #[test]
    fn excludes_typescript_references_shadowed_by_destructuring_defaults() {
        let repo = temp_repo_path("resolve-typescript-destructuring-default-shadows");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "import { Foo, Bar, Baz, Quux, Inner, StillImported, DefaultValue } from './values';\n\
\n\
export function run({ Foo = DefaultValue, alias: Bar = DefaultValue }: any, [Baz = DefaultValue]: any) {\n\
  const { Quux = DefaultValue, nested: { Inner = DefaultValue } = {} } = {} as any;\n\
  return Foo + Bar + Baz + Quux + Inner + StillImported + DefaultValue;\n\
}\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/values.ts"),
            "export const Foo = 1;\nexport const Bar = 2;\nexport const Baz = 3;\nexport const Quux = 4;\nexport const Inner = 5;\nexport const StillImported = 6;\nexport const DefaultValue = 7;\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 2);
        assert_eq!(index.summary().imports, 7);
        assert_eq!(index.summary().import_resolutions, 7);
        assert_eq!(index.summary().references, 7);
        assert_eq!(index.summary().dependencies, 2);

        let values_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/values.ts")
            .unwrap()
            .id;
        let still_imported_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == values_file_id && symbol.name == "StillImported")
            .unwrap()
            .id;
        let default_value_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == values_file_id && symbol.name == "DefaultValue")
            .unwrap()
            .id;

        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| reference.target_symbol_id == still_imported_symbol_id)
                .count(),
            1
        );
        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| reference.target_symbol_id == default_value_symbol_id)
                .count(),
            6
        );
    }

    #[test]
    fn scopes_typescript_lexical_declaration_shadows_to_blocks() {
        let repo = temp_repo_path("resolve-typescript-lexical-block-shadows");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "import { Imported } from './values';\n\
\n\
export function run(flag: boolean) {\n\
  const before = Imported;\n\
  if (flag) {\n\
    const Imported = 1;\n\
    Imported;\n\
  }\n\
  return Imported + before;\n\
}\n\
\n\
export function loop() {\n\
  for (let Imported = 0; Imported < 1; Imported++) {\n\
    Imported;\n\
  }\n\
  return Imported;\n\
}\n",
        )
        .unwrap();
        fs::write(repo.join("src/values.ts"), "export const Imported = 1;\n").unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 2);
        assert_eq!(index.summary().imports, 1);
        assert_eq!(index.summary().import_resolutions, 1);
        assert_eq!(index.summary().references, 3);
        assert_eq!(index.summary().dependencies, 2);

        let values_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/values.ts")
            .unwrap()
            .id;
        let imported_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == values_file_id && symbol.name == "Imported")
            .unwrap()
            .id;

        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| reference.target_symbol_id == imported_symbol_id)
                .count(),
            3
        );
    }

    #[test]
    fn resolves_typescript_type_annotation_references_and_dependencies() {
        let repo = temp_repo_path("resolve-typescript-type-annotation-references");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.tsx"),
            "import type { FlightRouterState } from './types';\n\
import { runtimeValue } from './values';\n\
\n\
export function AppRouterAnnouncer({ tree }: { tree: FlightRouterState }) {\n\
  return runtimeValue + tree.length;\n\
}\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/types.ts"),
            "export interface FlightRouterState { length: number }\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/values.ts"),
            "export const runtimeValue = 1;\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 3);
        assert_eq!(index.summary().imports, 2);
        assert_eq!(index.summary().import_resolutions, 2);
        assert_eq!(index.summary().references, 2);
        assert_eq!(index.summary().dependencies, 2);

        let app_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/app.tsx")
            .unwrap()
            .id;
        let types_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/types.ts")
            .unwrap()
            .id;
        let values_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/values.ts")
            .unwrap()
            .id;
        let announcer_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == app_file_id && symbol.name == "AppRouterAnnouncer")
            .unwrap()
            .id;
        let flight_router_state_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == types_file_id && symbol.name == "FlightRouterState")
            .unwrap()
            .id;
        let runtime_value_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == values_file_id && symbol.name == "runtimeValue")
            .unwrap()
            .id;

        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(announcer_symbol_id)
                && reference.target_symbol_id == flight_router_state_symbol_id
                && reference.name == "FlightRouterState"
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == announcer_symbol_id
                && dependency.target_symbol_id == flight_router_state_symbol_id
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == announcer_symbol_id
                && dependency.target_symbol_id == runtime_value_symbol_id
        }));
    }

    #[test]
    fn resolves_typescript_nested_local_assignment_dependencies() {
        let repo = temp_repo_path("resolve-typescript-nested-local-assignment-dependencies");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.tsx"),
            "import { useEffect, useState } from 'react';\n\
\n\
const ANNOUNCER_TYPE = 'next-route-announcer';\n\
\n\
function getAnnouncerNode() {\n\
  return document.createElement(ANNOUNCER_TYPE);\n\
}\n\
\n\
export function AppRouterAnnouncer() {\n\
  const [portalNode, setPortalNode] = useState<HTMLElement | null>(null);\n\
\n\
  useEffect(() => {\n\
    const announcer = getAnnouncerNode();\n\
    setPortalNode(announcer);\n\
    return () => {\n\
      const container = document.getElementsByTagName(ANNOUNCER_TYPE)[0];\n\
      if (container?.isConnected) {\n\
        document.body.removeChild(container);\n\
      }\n\
    };\n\
  }, []);\n\
\n\
  useEffect(() => {\n\
    let currentTitle = '';\n\
    const pageHeader = document.querySelector('h1');\n\
    if (pageHeader) {\n\
      currentTitle = pageHeader.textContent || '';\n\
    }\n\
    if (currentTitle) {\n\
      setPortalNode(currentTitle as unknown as HTMLElement);\n\
    }\n\
  }, []);\n\
\n\
  return portalNode;\n\
}\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        let symbol_id = |name: &str, top_level: Option<bool>| {
            index
                .symbols
                .iter()
                .find(|symbol| {
                    symbol.name == name
                        && top_level.is_none_or(|expected| symbol.is_top_level == expected)
                })
                .unwrap_or_else(|| panic!("missing symbol {name}"))
                .id
        };
        let dependency_exists = |source_symbol_id: u32, target_symbol_id: u32| {
            index.dependencies.iter().any(|dependency| {
                dependency.source_symbol_id == source_symbol_id
                    && dependency.target_symbol_id == target_symbol_id
            })
        };
        let dependency_exists_by_name = |source_symbol_id: u32, target_name: &str| {
            index.dependencies.iter().any(|dependency| {
                dependency.source_symbol_id == source_symbol_id
                    && index.symbols.iter().any(|symbol| {
                        symbol.id == dependency.target_symbol_id
                            && !symbol.is_top_level
                            && symbol.name == target_name
                    })
            })
        };

        let app_router_announcer = symbol_id("AppRouterAnnouncer", Some(true));
        let announcer_type = symbol_id("ANNOUNCER_TYPE", Some(true));
        let get_announcer_node = symbol_id("getAnnouncerNode", Some(true));
        let announcer = symbol_id("announcer", Some(false));
        let container = symbol_id("container", Some(false));
        let current_title = symbol_id("currentTitle", Some(false));
        let page_header = symbol_id("pageHeader", Some(false));

        for local_symbol_id in [announcer, container, current_title, page_header] {
            let symbol = index
                .symbols
                .iter()
                .find(|symbol| symbol.id == local_symbol_id)
                .unwrap();
            assert_eq!(symbol.parent_symbol_id, Some(app_router_announcer));
            assert!(!symbol.is_top_level);
            assert_eq!(symbol.kind, SymbolKind::GlobalVariable);
            assert!(
                dependency_exists_by_name(app_router_announcer, symbol.name.as_ref()),
                "missing AppRouterAnnouncer dependency on {}",
                symbol.name
            );
        }

        assert!(!dependency_exists(app_router_announcer, announcer_type));
        assert!(!dependency_exists(app_router_announcer, get_announcer_node));
        assert!(dependency_exists(announcer, get_announcer_node));
        assert!(dependency_exists(container, announcer_type));
    }

    #[test]
    fn resolves_typescript_tsconfig_path_aliases() {
        let repo = temp_repo_path("resolve-typescript-tsconfig-paths");
        fs::create_dir_all(repo.join("src/lib")).unwrap();
        fs::create_dir_all(repo.join("src/lib/special")).unwrap();
        fs::create_dir_all(repo.join("src/special")).unwrap();
        fs::create_dir_all(repo.join("src/components")).unwrap();
        fs::write(
            repo.join("tsconfig.json"),
            "{\n\
  // JSONC comments and trailing commas are common in tsconfig files.\n\
  \"compilerOptions\": {\n\
    \"baseUrl\": \"src\",\n\
    \"paths\": {\n\
      \"@lib/*\": [\"lib/*\"],\n\
      \"@lib/special/*\": [\"special/*\"],\n\
      \"components\": [\"components/index\"],\n\
    },\n\
  },\n\
}\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "import { helper } from '@lib/helper';\n\
import { specialHelper } from '@lib/special/helper';\n\
import { Button } from 'components';\n\
import { shared } from 'shared';\n\
import { Nope } from 'components-extra';\n\
\n\
export function run() {\n\
  return helper() + specialHelper() + Button + shared;\n\
}\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/lib/helper.ts"),
            "export function helper() { return 1; }\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/lib/special/helper.ts"),
            "export function wrongSpecial() { return 0; }\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/special/helper.ts"),
            "export function specialHelper() { return 4; }\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/components/index.ts"),
            "export const Button = 2;\n",
        )
        .unwrap();
        fs::write(repo.join("src/shared.ts"), "export const shared = 3;\n").unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 6);
        assert_eq!(index.summary().imports, 5);
        assert_eq!(index.summary().import_resolutions, 4);
        assert_eq!(index.summary().references, 4);
        assert_eq!(index.summary().dependencies, 4);

        let helper_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/lib/helper.ts")
            .unwrap()
            .id;
        let special_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/special/helper.ts")
            .unwrap()
            .id;
        let wrong_special_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/lib/special/helper.ts")
            .unwrap()
            .id;
        let components_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/components/index.ts")
            .unwrap()
            .id;
        let shared_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/shared.ts")
            .unwrap()
            .id;
        let unresolved_import_id = index
            .imports
            .iter()
            .find(|import| import.module.as_deref() == Some("components-extra"))
            .unwrap()
            .id;

        assert!(index
            .import_resolutions
            .iter()
            .any(|resolution| resolution.target_file_id == helper_file_id));
        assert!(index
            .import_resolutions
            .iter()
            .any(|resolution| resolution.target_file_id == special_file_id));
        assert!(!index
            .import_resolutions
            .iter()
            .any(|resolution| resolution.target_file_id == wrong_special_file_id));
        assert!(index
            .import_resolutions
            .iter()
            .any(|resolution| resolution.target_file_id == components_file_id));
        assert!(index
            .import_resolutions
            .iter()
            .any(|resolution| resolution.target_file_id == shared_file_id));
        assert!(!index
            .import_resolutions
            .iter()
            .any(|resolution| resolution.import_id == unresolved_import_id));
    }

    #[test]
    fn resolves_typescript_references_and_dependencies() {
        let repo = temp_repo_path("resolve-typescript-references");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "import Service, { helper as localHelper, format } from './utils';\n\
import * as utils from './utils';\n\
\n\
const sameFile = () => localHelper;\n\
export function run(value: number) {\n\
  const local = sameFile();\n\
  return format(new Service(), local, utils.helper, value);\n\
}\n\
export function shadow(localHelper: number) {\n\
  return localHelper;\n\
}\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/utils.ts"),
            "export const helper = 1;\nexport function format(...values: unknown[]) { return values; }\nexport default class Service {}\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        let app_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/app.ts")
            .unwrap()
            .id;
        let utils_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/utils.ts")
            .unwrap()
            .id;
        let run_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == app_file_id && symbol.name == "run")
            .unwrap()
            .id;
        let shadow_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == app_file_id && symbol.name == "shadow")
            .unwrap()
            .id;
        let same_file_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == app_file_id && symbol.name == "sameFile")
            .unwrap()
            .id;
        let helper_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == utils_file_id && symbol.name == "helper")
            .unwrap()
            .id;
        let format_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == utils_file_id && symbol.name == "format")
            .unwrap()
            .id;
        let service_symbol_id = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == utils_file_id && symbol.name == "Service")
            .unwrap()
            .id;

        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(run_symbol_id)
                && reference.target_symbol_id == format_symbol_id
                && reference.import_id.is_some()
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(run_symbol_id)
                && reference.target_symbol_id == service_symbol_id
                && reference.import_id.is_some()
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(run_symbol_id)
                && reference.target_symbol_id == helper_symbol_id
                && reference.import_id.is_some()
                && reference.name == "helper"
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(run_symbol_id)
                && reference.target_symbol_id == same_file_symbol_id
                && reference.import_id.is_none()
        }));
        assert!(!index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(shadow_symbol_id)
                && reference.target_symbol_id == helper_symbol_id
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == run_symbol_id
                && dependency.target_symbol_id == format_symbol_id
                && dependency.reference_count == 1
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == run_symbol_id
                && dependency.target_symbol_id == helper_symbol_id
                && dependency.reference_count == 1
        }));
    }

    #[test]
    fn extracts_typescript_function_call_records() {
        let repo = temp_repo_path("typescript-function-call-records");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/util.ts"),
            "export function helper(value: number): number { return value; }\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "import { helper } from './util';\n\n\
function local(value: number) {\n  return helper(value);\n}\n\n\
export function run() {\n  local(helper(1));\n  return run();\n}\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        let helper = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "helper")
            .unwrap();
        let local = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "local")
            .unwrap();
        let run = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "run")
            .unwrap();

        assert!(index.function_calls.iter().any(|call| {
            call.name == "helper"
                && call.source_symbol_id == Some(local.id)
                && call.target_symbol_id == Some(helper.id)
                && call.import_id.is_some()
        }));
        assert!(index.function_calls.iter().any(|call| {
            call.name == "local"
                && call.source_symbol_id == Some(run.id)
                && call.target_symbol_id == Some(local.id)
                && call.import_id.is_none()
        }));
        assert!(index.function_calls.iter().any(|call| {
            call.name == "helper"
                && call.source_symbol_id == Some(run.id)
                && call.target_symbol_id == Some(helper.id)
                && call.import_id.is_some()
        }));
        assert!(index.function_calls.iter().any(|call| {
            call.name == "run"
                && call.source_symbol_id == Some(run.id)
                && call.target_symbol_id == Some(run.id)
        }));
        assert!(!index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(run.id)
                && reference.target_symbol_id == run.id
                && reference.name == "run"
        }));
    }

    #[test]
    fn resolves_typescript_external_import_references() {
        let repo = temp_repo_path("typescript-external-import-references");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.tsx"),
            "import React from 'react';\nexport function run() {\n  return React.createElement('div');\n}\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 1);
        assert_eq!(index.summary().imports, 1);
        assert_eq!(index.external_modules.len(), 1);
        assert_eq!(index.summary().references, 0);
        assert_eq!(index.summary().dependencies, 0);
        assert_eq!(index.external_references.len(), 1);

        let import = index
            .imports
            .iter()
            .find(|import| import.alias.as_deref() == Some("React"))
            .unwrap();
        let run = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "run")
            .unwrap();
        let reference = &index.external_references[0];

        assert_eq!(reference.source_symbol_id, Some(run.id));
        assert_eq!(reference.import_id, import.id);
        assert_eq!(reference.name, "React");
        assert_eq!(reference.range.start_row, 2);
        assert_eq!(reference.range.start_column, 9);
    }

    #[test]
    fn resolves_typescript_heritage_references_and_dependencies() {
        let repo = temp_repo_path("resolve-typescript-heritage-references");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.ts"),
            "import { Base, IFace, IExtra } from './base';\n\
import * as base from './base';\n\
\n\
export interface Local extends IFace {}\n\
export class Child extends Base implements IFace, base.Other {}\n\
export interface Derived extends Local, IExtra {}\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/base.ts"),
            "export class Base {}\n\
export interface IFace {}\n\
export interface IExtra {}\n\
export interface Other {}\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 2);
        assert_eq!(index.summary().imports, 4);
        assert_eq!(index.summary().import_resolutions, 4);
        assert_eq!(index.summary().references, 6);
        assert_eq!(index.summary().dependencies, 6);
        assert_eq!(index.subclass_edges.len(), 6);

        let app_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/app.ts")
            .unwrap()
            .id;
        let base_file_id = index
            .files
            .iter()
            .find(|file| file.path == "src/base.ts")
            .unwrap()
            .id;
        let local = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == app_file_id && symbol.name == "Local")
            .unwrap();
        let child = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == app_file_id && symbol.name == "Child")
            .unwrap();
        let derived = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == app_file_id && symbol.name == "Derived")
            .unwrap();
        let base = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == base_file_id && symbol.name == "Base")
            .unwrap();
        let iface = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == base_file_id && symbol.name == "IFace")
            .unwrap();
        let iextra = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == base_file_id && symbol.name == "IExtra")
            .unwrap();
        let other = index
            .symbols
            .iter()
            .find(|symbol| symbol.file_id == base_file_id && symbol.name == "Other")
            .unwrap();

        for (source_symbol_id, target_symbol_id, name) in [
            (local.id, iface.id, "IFace"),
            (child.id, base.id, "Base"),
            (child.id, iface.id, "IFace"),
            (child.id, other.id, "Other"),
            (derived.id, local.id, "Local"),
            (derived.id, iextra.id, "IExtra"),
        ] {
            assert!(index.references.iter().any(|reference| {
                reference.source_symbol_id == Some(source_symbol_id)
                    && reference.target_symbol_id == target_symbol_id
                    && reference.name == name
            }));
            assert!(index.dependencies.iter().any(|dependency| {
                dependency.source_symbol_id == source_symbol_id
                    && dependency.target_symbol_id == target_symbol_id
            }));
            assert!(index.subclass_edges.iter().any(|edge| {
                edge.source_symbol_id == source_symbol_id
                    && edge.target_symbol_id == target_symbol_id
                    && index.references.iter().any(|reference| {
                        reference.id == edge.reference_id
                            && reference.source_symbol_id == Some(source_symbol_id)
                            && reference.target_symbol_id == target_symbol_id
                            && reference.name == name
                    })
            }));
        }
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
    fn resolves_python_package_reexports_to_symbols() {
        let repo = temp_repo_path("resolve-python-reexports");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(repo.join("pkg/__init__.py"), "from .base import Base\n").unwrap();
        fs::write(repo.join("pkg/base.py"), "class Base:\n    pass\n").unwrap();
        fs::write(
            repo.join("pkg/service.py"),
            "from pkg import Base\n\nclass Service(Base):\n    pass\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

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
        let service = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "Service")
            .unwrap();

        assert_eq!(
            index
                .import_resolutions
                .iter()
                .filter(|resolution| resolution.target_symbol_id == Some(base_symbol_id))
                .count(),
            2
        );
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(service.id)
                && reference.name == "Base"
                && reference.target_symbol_id == base_symbol_id
                && reference.import_id.is_some()
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == service.id
                && dependency.target_symbol_id == base_symbol_id
        }));
    }

    #[test]
    fn resolves_python_wildcard_import_chains_to_symbols() {
        let repo = temp_repo_path("resolve-python-wildcard-reexports");
        fs::create_dir_all(repo.join("pkg/inner")).unwrap();
        fs::write(
            repo.join("pkg/base.py"),
            "CONSTANT = 1\nclass Base:\n    pass\n\ndef helper():\n    return CONSTANT\n",
        )
        .unwrap();
        fs::write(
            repo.join("pkg/inner/__init__.py"),
            "from ..base import *\nINNER = CONSTANT\n",
        )
        .unwrap();
        fs::write(repo.join("pkg/__init__.py"), "from .inner import *\n").unwrap();
        fs::write(repo.join("facade.py"), "from pkg import *\n").unwrap();
        fs::write(
            repo.join("service.py"),
            "from pkg import Base\nfrom facade import *\n\nclass Service(Base):\n    def run(self):\n        return helper(), CONSTANT\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        let base = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "Base")
            .unwrap();
        let constant = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "CONSTANT")
            .unwrap();
        let helper = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "helper")
            .unwrap();
        let inner = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "INNER")
            .unwrap();
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

        assert!(index
            .import_resolutions
            .iter()
            .any(|resolution| { resolution.target_symbol_id == Some(base.id) }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(inner.id)
                && reference.name == "CONSTANT"
                && reference.target_symbol_id == constant.id
                && reference.import_id.is_some()
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(service.id)
                && reference.name == "Base"
                && reference.target_symbol_id == base.id
                && reference.import_id.is_some()
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(run.id)
                && reference.name == "helper"
                && reference.target_symbol_id == helper.id
                && reference.import_id.is_some()
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(run.id)
                && reference.name == "CONSTANT"
                && reference.target_symbol_id == constant.id
                && reference.import_id.is_some()
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == service.id && dependency.target_symbol_id == base.id
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == run.id && dependency.target_symbol_id == helper.id
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == run.id && dependency.target_symbol_id == constant.id
        }));
    }

    #[test]
    fn restricts_python_wildcard_imports_with_static_all_exports() {
        let repo = temp_repo_path("resolve-python-wildcard-all-exports");
        fs::create_dir_all(&repo).unwrap();
        fs::write(
            repo.join("provider.py"),
            "__all__ = ['Public']\nclass Public:\n    pass\nclass Hidden:\n    pass\n",
        )
        .unwrap();
        fs::write(
            repo.join("wildcard_consumer.py"),
            "from provider import *\n\nclass UsesPublic(Public):\n    pass\n\ndef unresolved():\n    return Hidden\n",
        )
        .unwrap();
        fs::write(
            repo.join("named_consumer.py"),
            "from provider import Hidden\n\nclass UsesHidden(Hidden):\n    pass\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        let public = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "Public")
            .unwrap();
        let hidden = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "Hidden")
            .unwrap();
        let uses_public = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "UsesPublic")
            .unwrap();
        let uses_hidden = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "UsesHidden")
            .unwrap();
        let unresolved = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "unresolved")
            .unwrap();

        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(uses_public.id)
                && reference.name == "Public"
                && reference.target_symbol_id == public.id
                && reference.import_id.is_some()
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(uses_hidden.id)
                && reference.name == "Hidden"
                && reference.target_symbol_id == hidden.id
                && reference.import_id.is_some()
        }));
        assert!(!index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(unresolved.id)
                && reference.name == "Hidden"
                && reference.target_symbol_id == hidden.id
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
    fn resolves_python_module_attribute_references() {
        let repo = temp_repo_path("python-module-attribute-references");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(repo.join("pkg/__init__.py"), "").unwrap();
        fs::write(
            repo.join("pkg/base.py"),
            "class Base:\n    pass\n\ndef helper():\n    return Base\n",
        )
        .unwrap();
        fs::write(
            repo.join("pkg/service.py"),
            "from . import base\nimport pkg.base as base_alias\nimport pkg.base\n\n\
def caller():\n    return base.helper(), base_alias.Base, pkg.base.helper()\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        let caller = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "caller")
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

        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| {
                    reference.source_symbol_id == Some(caller.id)
                        && reference.name == "helper"
                        && reference.target_symbol_id == helper.id
                        && reference.import_id.is_some()
                })
                .count(),
            2
        );
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(caller.id)
                && reference.name == "Base"
                && reference.target_symbol_id == base.id
                && reference.import_id.is_some()
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == caller.id
                && dependency.target_symbol_id == helper.id
                && dependency.reference_count == 2
        }));
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == caller.id
                && dependency.target_symbol_id == base.id
                && dependency.reference_count == 1
        }));
    }

    #[test]
    fn resolves_python_nested_module_attribute_references() {
        let repo = temp_repo_path("python-nested-module-attribute-references");
        fs::create_dir_all(repo.join("a/b")).unwrap();
        fs::write(repo.join("a/b/c.py"), "def d():\n    pass\n").unwrap();
        fs::write(
            repo.join("consumer.py"),
            "from a import b\nimport a.b\nimport a.b.c as c_alias\n\n\
def caller():\n    return b.c.d(), a.b.c.d(), c_alias.d()\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        let caller = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "caller")
            .unwrap();
        let d = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "d")
            .unwrap();

        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| {
                    reference.source_symbol_id == Some(caller.id)
                        && reference.name == "d"
                        && reference.target_symbol_id == d.id
                        && reference.import_id.is_some()
                })
                .count(),
            3
        );
        assert!(index.dependencies.iter().any(|dependency| {
            dependency.source_symbol_id == caller.id
                && dependency.target_symbol_id == d.id
                && dependency.reference_count == 3
        }));
    }

    #[test]
    fn skips_references_shadowed_by_python_parameters_and_locals() {
        let repo = temp_repo_path("python-shadowed-reference-sources");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(repo.join("pkg/__init__.py"), "").unwrap();
        fs::write(
            repo.join("pkg/base.py"),
            "class Base:\n    pass\n\nclass Point:\n    pass\n\ndef helper():\n    return Base\n",
        )
        .unwrap();
        fs::write(
            repo.join("pkg/service.py"),
            "from .base import Base, helper, Point\n\n\
other = object()\n\n\
Error = Exception\n\n\
def shadowed(Base):\n    helper = Base\n    return helper, Base\n\n\
def import_shadowed():\n    import other.module\n    import other.module as helper\n    from other import Base\n    return helper, Base, other\n\n\
def control_flow_shadowed(items, manager):\n    for Base, helper in items:\n        pass\n    with manager as other:\n        pass\n    try:\n        pass\n    except Error as helper:\n        return Base, helper, other\n\n\
def comprehension_shadowed(items):\n    return [Base + helper + other for Base, helper, other in items if Base]\n\n\
def comprehension_scope_does_not_leak(items):\n    values = [Base + helper for Base, helper in items]\n    return Base, helper, other\n\n\
def match_shadowed(subject):\n    match subject:\n        case Point(x=Base, y=helper) as other if Base:\n            return Base, helper, other\n        case {\"base\": Base, \"helper\": helper, **other}:\n            return Base, helper, other\n\n\
def lambda_shadowed():\n    return (lambda Base, helper, *other: (Base, helper, other))\n\n\
def lambda_default_ref():\n    return (lambda local=Base: local)\n\n\
def nonlocal_declared():\n    helper = Base\n    def inner():\n        nonlocal helper\n        helper = Base\n        return helper\n    return inner\n\n\
def global_declared():\n    global other\n    other = Base\n    return other\n\n\
def attribute_names_are_not_bare_references(obj):\n    return obj.helper, other.helper, helper.attr\n\n\
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
        let comprehension_shadowed = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "comprehension_shadowed")
            .unwrap();
        let comprehension_scope_does_not_leak = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "comprehension_scope_does_not_leak")
            .unwrap();
        let match_shadowed = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "match_shadowed")
            .unwrap();
        let lambda_shadowed = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "lambda_shadowed")
            .unwrap();
        let lambda_default_ref = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "lambda_default_ref")
            .unwrap();
        let nonlocal_declared_inner = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "inner")
            .unwrap();
        let global_declared = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "global_declared")
            .unwrap();
        let attribute_names = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "attribute_names_are_not_bare_references")
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
        let point = index
            .symbols
            .iter()
            .find(|symbol| symbol.name == "Point")
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
        assert!(!index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(comprehension_shadowed.id)
                && (reference.target_symbol_id == base.id
                    || reference.target_symbol_id == helper.id
                    || reference.target_symbol_id == other.id)
        }));
        for (name, target_symbol_id) in [
            ("Base", base.id),
            ("helper", helper.id),
            ("other", other.id),
        ] {
            assert_eq!(
                index
                    .references
                    .iter()
                    .filter(|reference| {
                        reference.source_symbol_id == Some(comprehension_scope_does_not_leak.id)
                            && reference.name == name
                            && reference.target_symbol_id == target_symbol_id
                    })
                    .count(),
                1
            );
        }
        assert!(!index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(match_shadowed.id)
                && (reference.target_symbol_id == base.id
                    || reference.target_symbol_id == helper.id
                    || reference.target_symbol_id == other.id)
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(match_shadowed.id)
                && reference.name == "Point"
                && reference.target_symbol_id == point.id
        }));
        assert!(!index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(lambda_shadowed.id)
                && (reference.target_symbol_id == base.id
                    || reference.target_symbol_id == helper.id
                    || reference.target_symbol_id == other.id)
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(lambda_default_ref.id)
                && reference.name == "Base"
                && reference.target_symbol_id == base.id
        }));
        assert!(!index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(nonlocal_declared_inner.id)
                && reference.name == "helper"
                && reference.target_symbol_id == helper.id
        }));
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(nonlocal_declared_inner.id)
                && reference.name == "Base"
                && reference.target_symbol_id == base.id
        }));
        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| {
                    reference.source_symbol_id == Some(global_declared.id)
                        && reference.name == "other"
                        && reference.target_symbol_id == other.id
                })
                .count(),
            2
        );
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(global_declared.id)
                && reference.name == "Base"
                && reference.target_symbol_id == base.id
        }));
        assert_eq!(
            index
                .references
                .iter()
                .filter(|reference| {
                    reference.source_symbol_id == Some(attribute_names.id)
                        && reference.name == "helper"
                        && reference.target_symbol_id == helper.id
                })
                .count(),
            1
        );
        assert!(index.references.iter().any(|reference| {
            reference.source_symbol_id == Some(attribute_names.id)
                && reference.name == "other"
                && reference.target_symbol_id == other.id
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
                    "language": file.language,
                    "content_hash": file.content_hash,
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
                    {"id": 0, "path": "pkg/__init__.py", "module_name": "pkg", "language": "python", "content_hash": "cbf29ce484222325"},
                    {"id": 1, "path": "pkg/base.py", "module_name": "pkg.base", "language": "python", "content_hash": "aba9f9794b1c932b"},
                    {"id": 2, "path": "pkg/service.py", "module_name": "pkg.service", "language": "python", "content_hash": "aeab60e038068a85"}
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

    #[test]
    fn compact_typescript_syntax_snapshot_is_stable() {
        let repo = temp_repo_path("compact-typescript-syntax-snapshot");
        fs::create_dir_all(repo.join("src")).unwrap();
        fs::write(
            repo.join("src/app.tsx"),
            "import React, { useMemo as memo, ReactNode } from 'react';\n\
import * as path from 'path';\n\
import './polyfill';\n\
\n\
const lazy = require('./lazy');\n\
const dynamicModule = import('./dynamic');\n\
\n\
export interface Props { title: string; child?: ReactNode }\n\
export type Mode = 'light' | 'dark';\n\
export enum Status { Ready = 'ready' }\n\
export namespace Tokens { export const spacing = 8; }\n\
export const helper = (value: number) => value + 1;\n\
export function Page(props: Props) { return <main>{props.title}</main>; }\n\
export default class Widget {}\n\
export { helper as renamedHelper, Props };\n\
export * from './shared';\n\
export * as shared from './shared';\n",
        )
        .unwrap();
        fs::write(
            repo.join("src/shared.ts"),
            "export const sharedValue = 1;\nexport function sharedFn() { return sharedValue; }\n",
        )
        .unwrap();

        let index = index_typescript_path(&repo).unwrap();
        let actual = compact_typescript_snapshot_json(&index);
        let expected_path = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../rust-rewrite/golden/typescript-fixture-rust-compact.json");
        if std::env::var_os("GRAPH_SITTER_UPDATE_TYPESCRIPT_FIXTURE_SNAPSHOT").is_some() {
            fs::write(
                &expected_path,
                serde_json::to_string_pretty(&actual).unwrap() + "\n",
            )
            .unwrap();
        } else {
            let expected: serde_json::Value =
                serde_json::from_str(&fs::read_to_string(&expected_path).unwrap()).unwrap();
            assert_eq!(actual, expected);
        }
        fs::remove_dir_all(&repo).unwrap();
    }

    fn compact_typescript_snapshot_json(index: &TypeScriptIndex) -> serde_json::Value {
        let files = index
            .files
            .iter()
            .map(|file| {
                serde_json::json!({
                    "id": file.id,
                    "path": file.path,
                    "language": file.language,
                    "content_hash": file.content_hash,
                    "byte_len": file.byte_len,
                    "line_count": file.line_count,
                    "has_error": file.has_error,
                    "root_range": compact_range_json(file.root_range),
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
                    "range": compact_range_json(symbol.range),
                    "name_range": compact_range_json(symbol.name_range),
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
                    "range": compact_range_json(import.range),
                })
            })
            .collect::<Vec<_>>();
        let import_resolutions = index
            .import_resolutions
            .iter()
            .map(|resolution| {
                serde_json::json!({
                    "id": resolution.id,
                    "import_id": resolution.import_id,
                    "source_file_id": resolution.source_file_id,
                    "target_file_id": resolution.target_file_id,
                    "target_symbol_id": resolution.target_symbol_id,
                })
            })
            .collect::<Vec<_>>();
        let exports = index
            .exports
            .iter()
            .map(|export| {
                serde_json::json!({
                    "id": export.id,
                    "file_id": export.file_id,
                    "kind": export.kind,
                    "name": export.name,
                    "local_name": export.local_name,
                    "source_module": export.source_module,
                    "symbol_id": export.symbol_id,
                    "import_id": export.import_id,
                    "range": compact_range_json(export.range),
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
                    "range": compact_range_json(reference.range),
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
        let subclass_edges = index
            .subclass_edges
            .iter()
            .map(|edge| {
                serde_json::json!({
                    "id": edge.id,
                    "source_symbol_id": edge.source_symbol_id,
                    "target_symbol_id": edge.target_symbol_id,
                    "source_file_id": edge.source_file_id,
                    "target_file_id": edge.target_file_id,
                    "reference_id": edge.reference_id,
                })
            })
            .collect::<Vec<_>>();

        serde_json::json!({
            "summary": {
                "files": index.summary().files,
                "symbols": index.summary().symbols,
                "classes": index.summary().classes,
                "functions": index.summary().functions,
                "global_variables": index.summary().global_variables,
                "imports": index.summary().imports,
                "import_resolutions": index.summary().import_resolutions,
                "exports": index.exports.len(),
                "references": index.summary().references,
                "dependencies": index.summary().dependencies,
                "bytes": index.summary().bytes,
                "lines": index.summary().lines,
                "files_with_errors": index.summary().files_with_errors,
            },
            "files": files,
            "symbols": symbols,
            "imports": imports,
            "import_resolutions": import_resolutions,
            "exports": exports,
            "references": references,
            "dependencies": dependencies,
            "subclass_edges": subclass_edges,
        })
    }

    fn compact_range_json(range: SourceRange) -> serde_json::Value {
        serde_json::json!([
            range.start_byte,
            range.end_byte,
            range.start_row,
            range.start_column,
            range.end_row,
            range.end_column
        ])
    }

    fn temp_repo_path(prefix: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("graph-sitter-{prefix}-{nanos}"))
    }
}
