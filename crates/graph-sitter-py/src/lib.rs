#![cfg_attr(not(feature = "pyo3-bindings"), forbid(unsafe_code))]

pub fn engine_version() -> &'static str {
    graph_sitter_engine::engine_version()
}

pub fn enabled_features() -> &'static [&'static str] {
    graph_sitter_engine::debug_info().enabled_features()
}

#[cfg(feature = "pyo3-bindings")]
mod bindings {
    use graph_sitter_engine::{
        self, Engine, EngineInfo, IndexSummary, PythonIndex, TypeScriptIndex,
    };
    use pyo3::exceptions::{PyRuntimeError, PyValueError};
    use pyo3::prelude::*;
    use std::path::Path;

    #[pyclass(name = "EngineInfo", module = "graph_sitter_py")]
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct PyEngineInfo {
        version: String,
        enabled_features: Vec<String>,
    }

    impl From<EngineInfo> for PyEngineInfo {
        fn from(info: EngineInfo) -> Self {
            Self {
                version: info.version().to_owned(),
                enabled_features: info
                    .enabled_features()
                    .iter()
                    .map(|feature| (*feature).to_owned())
                    .collect(),
            }
        }
    }

    #[pymethods]
    impl PyEngineInfo {
        #[getter]
        fn version(&self) -> &str {
            &self.version
        }

        #[getter]
        fn enabled_features(&self) -> Vec<String> {
            self.enabled_features.clone()
        }

        fn __repr__(&self) -> String {
            format!(
                "EngineInfo(version={:?}, enabled_features={:?})",
                self.version, self.enabled_features
            )
        }
    }

    #[pyclass(name = "IndexSummary", module = "graph_sitter_py")]
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct PyIndexSummary {
        #[pyo3(get)]
        files: usize,
        #[pyo3(get)]
        symbols: usize,
        #[pyo3(get)]
        classes: usize,
        #[pyo3(get)]
        functions: usize,
        #[pyo3(get)]
        global_variables: usize,
        #[pyo3(get)]
        imports: usize,
        #[pyo3(get)]
        import_resolutions: usize,
        #[pyo3(get)]
        references: usize,
        #[pyo3(get)]
        dependencies: usize,
        #[pyo3(get)]
        bytes: usize,
        #[pyo3(get)]
        lines: usize,
        #[pyo3(get)]
        files_with_errors: usize,
    }

    impl From<IndexSummary> for PyIndexSummary {
        fn from(summary: IndexSummary) -> Self {
            Self {
                files: summary.files,
                symbols: summary.symbols,
                classes: summary.classes,
                functions: summary.functions,
                global_variables: summary.global_variables,
                imports: summary.imports,
                import_resolutions: summary.import_resolutions,
                references: summary.references,
                dependencies: summary.dependencies,
                bytes: summary.bytes,
                lines: summary.lines,
                files_with_errors: summary.files_with_errors,
            }
        }
    }

    #[pymethods]
    impl PyIndexSummary {
        fn as_dict(&self) -> std::collections::BTreeMap<&'static str, usize> {
            std::collections::BTreeMap::from([
                ("files", self.files),
                ("symbols", self.symbols),
                ("classes", self.classes),
                ("functions", self.functions),
                ("global_variables", self.global_variables),
                ("imports", self.imports),
                ("import_resolutions", self.import_resolutions),
                ("references", self.references),
                ("dependencies", self.dependencies),
                ("bytes", self.bytes),
                ("lines", self.lines),
                ("files_with_errors", self.files_with_errors),
            ])
        }

        fn __repr__(&self) -> String {
            format!(
                "IndexSummary(files={}, symbols={}, classes={}, functions={}, global_variables={}, imports={}, import_resolutions={}, references={}, dependencies={}, bytes={}, lines={}, files_with_errors={})",
                self.files,
                self.symbols,
                self.classes,
                self.functions,
                self.global_variables,
                self.imports,
                self.import_resolutions,
                self.references,
                self.dependencies,
                self.bytes,
                self.lines,
                self.files_with_errors
            )
        }
    }

    #[pyclass(name = "PythonIndex", module = "graph_sitter_py")]
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct PyPythonIndex {
        inner: PythonIndex,
    }

    impl From<PythonIndex> for PyPythonIndex {
        fn from(inner: PythonIndex) -> Self {
            Self { inner }
        }
    }

    #[pymethods]
    impl PyPythonIndex {
        fn summary(&self) -> PyIndexSummary {
            self.inner.summary().into()
        }

        fn to_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn files_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.files)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn symbols_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.symbols)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn imports_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.imports)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn import_resolutions_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.import_resolutions)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn external_modules_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.external_modules)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn references_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.references)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn dependencies_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.dependencies)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        #[getter]
        fn file_count(&self) -> usize {
            self.inner.files.len()
        }

        #[getter]
        fn symbol_count(&self) -> usize {
            self.inner.symbols.len()
        }

        #[getter]
        fn import_count(&self) -> usize {
            self.inner.imports.len()
        }

        #[getter]
        fn import_resolution_count(&self) -> usize {
            self.inner.import_resolutions.len()
        }

        #[getter]
        fn external_module_count(&self) -> usize {
            self.inner.external_modules.len()
        }

        #[getter]
        fn reference_count(&self) -> usize {
            self.inner.references.len()
        }

        #[getter]
        fn dependency_count(&self) -> usize {
            self.inner.dependencies.len()
        }

        fn __repr__(&self) -> String {
            let summary = self.inner.summary();
            format!(
                "PythonIndex(files={}, symbols={}, imports={}, import_resolutions={}, references={}, dependencies={})",
                summary.files,
                summary.symbols,
                summary.imports,
                summary.import_resolutions,
                summary.references,
                summary.dependencies
            )
        }
    }

    #[pyclass(name = "TypeScriptIndex", module = "graph_sitter_py")]
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct PyTypeScriptIndex {
        inner: TypeScriptIndex,
    }

    impl From<TypeScriptIndex> for PyTypeScriptIndex {
        fn from(inner: TypeScriptIndex) -> Self {
            Self { inner }
        }
    }

    #[pymethods]
    impl PyTypeScriptIndex {
        fn summary(&self) -> PyIndexSummary {
            self.inner.summary().into()
        }

        fn to_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn files_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.files)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn symbols_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.symbols)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn imports_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.imports)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn import_resolutions_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.import_resolutions)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn external_modules_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.external_modules)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn exports_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.exports)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn references_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.references)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn dependencies_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.dependencies)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn subclass_edges_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.subclass_edges)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        #[getter]
        fn file_count(&self) -> usize {
            self.inner.files.len()
        }

        #[getter]
        fn symbol_count(&self) -> usize {
            self.inner.symbols.len()
        }

        #[getter]
        fn import_count(&self) -> usize {
            self.inner.imports.len()
        }

        #[getter]
        fn import_resolution_count(&self) -> usize {
            self.inner.import_resolutions.len()
        }

        #[getter]
        fn external_module_count(&self) -> usize {
            self.inner.external_modules.len()
        }

        #[getter]
        fn export_count(&self) -> usize {
            self.inner.exports.len()
        }

        #[getter]
        fn reference_count(&self) -> usize {
            self.inner.references.len()
        }

        #[getter]
        fn dependency_count(&self) -> usize {
            self.inner.dependencies.len()
        }

        #[getter]
        fn subclass_edge_count(&self) -> usize {
            self.inner.subclass_edges.len()
        }

        fn __repr__(&self) -> String {
            let summary = self.inner.summary();
            format!(
                "TypeScriptIndex(files={}, symbols={}, imports={}, import_resolutions={}, exports={}, references={}, dependencies={})",
                summary.files,
                summary.symbols,
                summary.imports,
                summary.import_resolutions,
                self.inner.exports.len(),
                summary.references,
                summary.dependencies
            )
        }
    }

    #[pyclass(name = "Engine", module = "graph_sitter_py")]
    #[derive(Debug, Default, Clone)]
    pub struct PyEngine {
        inner: Engine,
    }

    #[pymethods]
    impl PyEngine {
        #[new]
        fn new() -> Self {
            Self {
                inner: Engine::new(),
            }
        }

        #[getter]
        fn version(&self) -> &str {
            self.inner.version()
        }

        fn enabled_features(&self) -> Vec<String> {
            self.inner
                .enabled_features()
                .iter()
                .map(|feature| (*feature).to_owned())
                .collect()
        }

        fn debug_info(&self) -> PyEngineInfo {
            self.inner.debug_info().into()
        }

        fn index_python_path(&self, repo_path: &str) -> PyResult<PyPythonIndex> {
            index_python_path_impl(repo_path)
        }

        fn index_python_paths(
            &self,
            repo_path: &str,
            file_paths: Vec<String>,
        ) -> PyResult<PyPythonIndex> {
            index_python_paths_impl(repo_path, file_paths)
        }

        fn index_typescript_path(&self, repo_path: &str) -> PyResult<PyTypeScriptIndex> {
            index_typescript_path_impl(repo_path)
        }

        fn index_typescript_paths(
            &self,
            repo_path: &str,
            file_paths: Vec<String>,
        ) -> PyResult<PyTypeScriptIndex> {
            index_typescript_paths_impl(repo_path, file_paths)
        }
    }

    #[pyfunction(name = "engine_version")]
    fn py_engine_version() -> &'static str {
        graph_sitter_engine::engine_version()
    }

    #[pyfunction(name = "debug_info")]
    fn py_debug_info() -> PyEngineInfo {
        graph_sitter_engine::debug_info().into()
    }

    #[pyfunction(name = "index_python_path")]
    fn py_index_python_path(repo_path: &str) -> PyResult<PyPythonIndex> {
        index_python_path_impl(repo_path)
    }

    #[pyfunction(name = "index_python_paths")]
    fn py_index_python_paths(repo_path: &str, file_paths: Vec<String>) -> PyResult<PyPythonIndex> {
        index_python_paths_impl(repo_path, file_paths)
    }

    #[pyfunction(name = "index_typescript_path")]
    fn py_index_typescript_path(repo_path: &str) -> PyResult<PyTypeScriptIndex> {
        index_typescript_path_impl(repo_path)
    }

    #[pyfunction(name = "index_typescript_paths")]
    fn py_index_typescript_paths(
        repo_path: &str,
        file_paths: Vec<String>,
    ) -> PyResult<PyTypeScriptIndex> {
        index_typescript_paths_impl(repo_path, file_paths)
    }

    fn index_python_path_impl(repo_path: &str) -> PyResult<PyPythonIndex> {
        let path = Path::new(repo_path);
        if !path.exists() {
            return Err(PyValueError::new_err(format!(
                "repo path does not exist: {repo_path}"
            )));
        }
        graph_sitter_engine::index_python_path(path)
            .map(PyPythonIndex::from)
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    fn index_python_paths_impl(
        repo_path: &str,
        file_paths: Vec<String>,
    ) -> PyResult<PyPythonIndex> {
        let path = Path::new(repo_path);
        if !path.exists() {
            return Err(PyValueError::new_err(format!(
                "repo path does not exist: {repo_path}"
            )));
        }
        graph_sitter_engine::index_python_paths(path, file_paths)
            .map(PyPythonIndex::from)
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    fn index_typescript_path_impl(repo_path: &str) -> PyResult<PyTypeScriptIndex> {
        let path = Path::new(repo_path);
        if !path.exists() {
            return Err(PyValueError::new_err(format!(
                "repo path does not exist: {repo_path}"
            )));
        }
        graph_sitter_engine::index_typescript_path(path)
            .map(PyTypeScriptIndex::from)
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    fn index_typescript_paths_impl(
        repo_path: &str,
        file_paths: Vec<String>,
    ) -> PyResult<PyTypeScriptIndex> {
        let path = Path::new(repo_path);
        if !path.exists() {
            return Err(PyValueError::new_err(format!(
                "repo path does not exist: {repo_path}"
            )));
        }
        graph_sitter_engine::index_typescript_paths(path, file_paths)
            .map(PyTypeScriptIndex::from)
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    #[pymodule]
    fn graph_sitter_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add_class::<PyEngine>()?;
        m.add_class::<PyEngineInfo>()?;
        m.add_class::<PyIndexSummary>()?;
        m.add_class::<PyPythonIndex>()?;
        m.add_class::<PyTypeScriptIndex>()?;
        m.add_function(wrap_pyfunction!(py_engine_version, m)?)?;
        m.add_function(wrap_pyfunction!(py_debug_info, m)?)?;
        m.add_function(wrap_pyfunction!(py_index_python_path, m)?)?;
        m.add_function(wrap_pyfunction!(py_index_python_paths, m)?)?;
        m.add_function(wrap_pyfunction!(py_index_typescript_path, m)?)?;
        m.add_function(wrap_pyfunction!(py_index_typescript_paths, m)?)?;
        Ok(())
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        use std::fs;
        use std::path::PathBuf;
        use std::time::{SystemTime, UNIX_EPOCH};

        #[test]
        fn debug_info_forwards_core_engine_metadata() {
            let info = py_debug_info();

            assert_eq!(info.version, graph_sitter_engine::engine_version());
            assert_eq!(
                info.enabled_features,
                vec![
                    "skeleton".to_owned(),
                    "python-index".to_owned(),
                    "typescript-index".to_owned()
                ]
            );
        }

        #[test]
        fn py_engine_indexes_python_path() {
            let repo = temp_repo_path("py-binding-index");
            fs::create_dir_all(repo.join("pkg")).unwrap();
            fs::write(
                repo.join("pkg/mod.py"),
                "import os\n\nclass Service:\n    pass\n\ndef helper():\n    return os.getcwd()\n",
            )
            .unwrap();

            let index = PyEngine::new()
                .index_python_path(repo.to_str().unwrap())
                .unwrap();
            fs::remove_dir_all(&repo).unwrap();

            let summary = index.summary();
            assert_eq!(summary.files, 1);
            assert_eq!(summary.classes, 1);
            assert_eq!(summary.functions, 1);
            assert_eq!(summary.imports, 1);
            assert!(index.to_json().unwrap().contains("\"Service\""));
        }

        #[test]
        fn py_engine_indexes_selected_python_paths() {
            let repo = temp_repo_path("py-binding-index-paths");
            fs::create_dir_all(repo.join("pkg")).unwrap();
            fs::write(repo.join("pkg/included.py"), "class Included:\n    pass\n").unwrap();
            fs::write(repo.join("pkg/skipped.py"), "class Skipped:\n    pass\n").unwrap();

            let index = PyEngine::new()
                .index_python_paths(repo.to_str().unwrap(), vec!["pkg/included.py".to_owned()])
                .unwrap();
            fs::remove_dir_all(&repo).unwrap();

            let summary = index.summary();
            assert_eq!(summary.files, 1);
            assert_eq!(summary.classes, 1);
            assert!(index.to_json().unwrap().contains("\"Included\""));
            assert!(!index.to_json().unwrap().contains("\"Skipped\""));
        }

        #[test]
        fn py_engine_exposes_import_resolution_count() {
            let repo = temp_repo_path("py-binding-import-resolution");
            fs::create_dir_all(repo.join("pkg")).unwrap();
            fs::write(repo.join("pkg/__init__.py"), "").unwrap();
            fs::write(
                repo.join("pkg/base.py"),
                "CONSTANT = 'base'\nclass Base:\n    pass\n",
            )
            .unwrap();
            fs::write(
                repo.join("pkg/service.py"),
                "from .base import Base, CONSTANT\n\nclass Service(Base):\n    pass\n",
            )
            .unwrap();

            let index = PyEngine::new()
                .index_python_path(repo.to_str().unwrap())
                .unwrap();
            fs::remove_dir_all(&repo).unwrap();

            let summary = index.summary();
            assert_eq!(summary.global_variables, 1);
            assert_eq!(summary.import_resolutions, 2);
            assert_eq!(summary.references, 1);
            assert_eq!(summary.dependencies, 1);
            assert_eq!(index.import_resolution_count(), 2);
            assert_eq!(index.external_module_count(), 0);
            assert_eq!(index.reference_count(), 1);
            assert_eq!(index.dependency_count(), 1);
            assert!(index.files_json().unwrap().contains("\"pkg/base.py\""));
            assert!(index.symbols_json().unwrap().contains("\"CONSTANT\""));
            assert!(index.symbols_json().unwrap().contains("\"Base\""));
            assert!(index.imports_json().unwrap().contains("\".base\""));
            assert!(index
                .import_resolutions_json()
                .unwrap()
                .contains("target_symbol_id"));
            assert_eq!(index.external_modules_json().unwrap(), "[]");
            assert!(index.references_json().unwrap().contains("\"Base\""));
            assert!(index
                .dependencies_json()
                .unwrap()
                .contains("reference_count"));
            assert!(index.to_json().unwrap().contains("import_resolutions"));
            assert!(index.to_json().unwrap().contains("references"));
            assert!(index.to_json().unwrap().contains("dependencies"));
        }

        #[test]
        fn py_engine_indexes_typescript_path() {
            let repo = temp_repo_path("py-binding-typescript-index");
            fs::create_dir_all(repo.join("src")).unwrap();
            fs::write(
                repo.join("src/app.tsx"),
                "import React from 'react';\nimport { helper } from './util';\nexport function Page() { return helper(<div />); }\n",
            )
            .unwrap();
            fs::write(
                repo.join("src/util.ts"),
                "export function helper(value: unknown) { return value; }\n",
            )
            .unwrap();
            fs::write(repo.join("src/skipped.py"), "class Skipped:\n    pass\n").unwrap();

            let index = PyEngine::new()
                .index_typescript_path(repo.to_str().unwrap())
                .unwrap();
            fs::remove_dir_all(&repo).unwrap();

            let summary = index.summary();
            assert_eq!(summary.files, 2);
            assert_eq!(summary.functions, 2);
            assert_eq!(summary.imports, 2);
            assert_eq!(summary.import_resolutions, 1);
            assert_eq!(summary.references, 1);
            assert_eq!(summary.dependencies, 1);
            assert_eq!(index.import_resolution_count(), 1);
            assert_eq!(index.external_module_count(), 1);
            assert_eq!(index.export_count(), 2);
            assert_eq!(index.reference_count(), 1);
            assert_eq!(index.dependency_count(), 1);
            assert_eq!(index.subclass_edge_count(), 0);
            assert!(index.files_json().unwrap().contains("\"src/app.tsx\""));
            assert!(index.symbols_json().unwrap().contains("\"Page\""));
            assert!(index.imports_json().unwrap().contains("\"default_import\""));
            assert!(index
                .import_resolutions_json()
                .unwrap()
                .contains("target_symbol_id"));
            assert!(index.external_modules_json().unwrap().contains("\"React\""));
            assert!(index.exports_json().unwrap().contains("\"Page\""));
            assert!(index.references_json().unwrap().contains("\"helper\""));
            assert!(index
                .dependencies_json()
                .unwrap()
                .contains("reference_count"));
            assert_eq!(index.subclass_edges_json().unwrap(), "[]");
            assert!(index.to_json().unwrap().contains("\"import_resolutions\""));
            assert!(index.to_json().unwrap().contains("\"external_modules\""));
            assert!(index.to_json().unwrap().contains("\"exports\""));
            assert!(index.to_json().unwrap().contains("\"references\""));
            assert!(index.to_json().unwrap().contains("\"dependencies\""));
            assert!(index.to_json().unwrap().contains("\"subclass_edges\""));
        }

        #[test]
        fn py_engine_indexes_selected_typescript_paths() {
            let repo = temp_repo_path("py-binding-typescript-paths");
            fs::create_dir_all(repo.join("src")).unwrap();
            fs::write(repo.join("src/included.ts"), "export class Included {}\n").unwrap();
            fs::write(repo.join("src/skipped.ts"), "export class Skipped {}\n").unwrap();

            let index = PyEngine::new()
                .index_typescript_paths(repo.to_str().unwrap(), vec!["src/included.ts".to_owned()])
                .unwrap();
            fs::remove_dir_all(&repo).unwrap();

            assert_eq!(index.file_count(), 1);
            assert_eq!(index.symbol_count(), 1);
            assert_eq!(index.export_count(), 1);
            assert!(index.to_json().unwrap().contains("\"Included\""));
            assert!(!index.to_json().unwrap().contains("\"Skipped\""));
        }

        fn temp_repo_path(prefix: &str) -> PathBuf {
            let nanos = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            std::env::temp_dir().join(format!("graph-sitter-{prefix}-{nanos}"))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn forwards_core_engine_metadata_without_python_linking() {
        assert_eq!(engine_version(), graph_sitter_engine::engine_version());
        assert_eq!(
            enabled_features(),
            ["skeleton", "python-index", "typescript-index"]
        );
    }
}
