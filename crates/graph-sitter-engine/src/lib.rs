#![forbid(unsafe_code)]

use serde::Serialize;
use std::collections::HashMap;
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
            imports: self.imports.len(),
            import_resolutions: self.import_resolutions.len(),
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
    pub imports: usize,
    pub import_resolutions: usize,
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
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SymbolRecord {
    pub id: u32,
    pub file_id: u32,
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
        };
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
            extract_python_file(file_id, &content, &tree, &mut index);
        }

        resolve_python_imports(&mut index);
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

fn extract_python_file(file_id: u32, source: &str, tree: &Tree, index: &mut PythonIndex) {
    let root = tree.root_node();
    let mut cursor = root.walk();
    for child in root.named_children(&mut cursor) {
        extract_top_level_node(file_id, source, child, index);
    }
}

fn extract_top_level_node(file_id: u32, source: &str, node: Node<'_>, index: &mut PythonIndex) {
    match node.kind() {
        "class_definition" => push_symbol(file_id, source, node, SymbolKind::Class, index),
        "function_definition" => push_symbol(file_id, source, node, SymbolKind::Function, index),
        "decorated_definition" => {
            if let Some(definition) =
                first_child_of_kind(node, &["class_definition", "function_definition"])
            {
                let kind = if definition.kind() == "class_definition" {
                    SymbolKind::Class
                } else {
                    SymbolKind::Function
                };
                push_symbol_with_range(file_id, source, definition, node.range(), kind, index);
            }
        }
        "import_statement" => push_import_statement(file_id, source, node, index),
        "import_from_statement" | "future_import_statement" => {
            push_from_import_statement(file_id, source, node, index)
        }
        _ => {}
    }
}

fn push_symbol(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    kind: SymbolKind,
    index: &mut PythonIndex,
) {
    push_symbol_with_range(file_id, source, node, node.range(), kind, index);
}

fn push_symbol_with_range(
    file_id: u32,
    source: &str,
    node: Node<'_>,
    declaration_range: Range,
    kind: SymbolKind,
    index: &mut PythonIndex,
) {
    let Some(name_node) = node.child_by_field_name("name") else {
        return;
    };
    let Ok(name) = name_node.utf8_text(source.as_bytes()) else {
        return;
    };
    index.symbols.push(SymbolRecord {
        id: index.symbols.len() as u32,
        file_id,
        name: name.to_owned(),
        kind,
        range: declaration_range.into(),
        name_range: name_node.range().into(),
    });
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
        assert_eq!(index.summary().imports, 4);
        assert_eq!(index.summary().import_resolutions, 0);
        assert_eq!(index.symbols[0].name, "Service");
        assert_eq!(index.symbols[1].name, "helper");
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
        fs::write(repo.join("pkg/base.py"), "class Base:\n    pass\n").unwrap();
        fs::write(
            repo.join("pkg/service.py"),
            "from __future__ import annotations\nfrom .base import Base\nfrom . import base\nimport pkg.base\nimport os\n\nclass Service(Base):\n    pass\n",
        )
        .unwrap();

        let index = index_python_path(&repo).unwrap();
        fs::remove_dir_all(&repo).unwrap();

        assert_eq!(index.summary().files, 3);
        assert_eq!(index.summary().classes, 2);
        assert_eq!(index.summary().imports, 5);
        assert_eq!(index.summary().import_resolutions, 3);

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
        assert!(index.import_resolutions.iter().any(|resolution| {
            resolution.target_file_id == base_file_id
                && resolution.target_symbol_id == Some(base_symbol_id)
        }));
        assert_eq!(
            index
                .import_resolutions
                .iter()
                .filter(|resolution| resolution.target_file_id == base_file_id)
                .count(),
            3
        );
    }

    #[test]
    fn compact_python_graph_snapshot_is_stable() {
        let repo = temp_repo_path("compact-python-graph-snapshot");
        fs::create_dir_all(repo.join("pkg")).unwrap();
        fs::write(repo.join("pkg/__init__.py"), "").unwrap();
        fs::write(repo.join("pkg/base.py"), "class Base:\n    pass\n").unwrap();
        fs::write(
            repo.join("pkg/service.py"),
            "from .base import Base\nfrom . import base\nimport pkg.base\nimport os\n\nclass Service(Base):\n    pass\n",
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

        assert_eq!(
            serde_json::json!({
                "files": files,
                "symbols": symbols,
                "imports": imports,
                "import_resolutions": index.import_resolutions,
            }),
            serde_json::json!({
                "files": [
                    {"id": 0, "path": "pkg/__init__.py", "module_name": "pkg"},
                    {"id": 1, "path": "pkg/base.py", "module_name": "pkg.base"},
                    {"id": 2, "path": "pkg/service.py", "module_name": "pkg.service"}
                ],
                "symbols": [
                    {"id": 0, "file_id": 1, "name": "Base", "kind": "class"},
                    {"id": 1, "file_id": 2, "name": "Service", "kind": "class"}
                ],
                "imports": [
                    {"id": 0, "file_id": 2, "kind": "from_import", "module": ".base", "name": "Base", "alias": null},
                    {"id": 1, "file_id": 2, "kind": "from_import", "module": ".", "name": "base", "alias": null},
                    {"id": 2, "file_id": 2, "kind": "import", "module": null, "name": "pkg.base", "alias": null},
                    {"id": 3, "file_id": 2, "kind": "import", "module": null, "name": "os", "alias": null}
                ],
                "import_resolutions": [
                    {"id": 0, "import_id": 0, "source_file_id": 2, "target_file_id": 1, "target_symbol_id": 0},
                    {"id": 1, "import_id": 1, "source_file_id": 2, "target_file_id": 1, "target_symbol_id": null},
                    {"id": 2, "import_id": 2, "source_file_id": 2, "target_file_id": 1, "target_symbol_id": null}
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
