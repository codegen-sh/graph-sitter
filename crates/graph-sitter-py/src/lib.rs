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
        self, Engine, EngineInfo, IndexSummary, PythonIndex, SymbolKind, SymbolRecord,
        TypeScriptIndex,
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
        external_modules: usize,
        #[pyo3(get)]
        exports: usize,
        #[pyo3(get)]
        references: usize,
        #[pyo3(get)]
        external_references: usize,
        #[pyo3(get)]
        dependencies: usize,
        #[pyo3(get)]
        subclass_edges: usize,
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
                external_modules: summary.external_modules,
                exports: summary.exports,
                references: summary.references,
                external_references: summary.external_references,
                dependencies: summary.dependencies,
                subclass_edges: summary.subclass_edges,
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
                ("external_modules", self.external_modules),
                ("exports", self.exports),
                ("references", self.references),
                ("external_references", self.external_references),
                ("dependencies", self.dependencies),
                ("subclass_edges", self.subclass_edges),
                ("bytes", self.bytes),
                ("lines", self.lines),
                ("files_with_errors", self.files_with_errors),
            ])
        }

        fn __repr__(&self) -> String {
            format!(
                "IndexSummary(files={}, symbols={}, classes={}, functions={}, global_variables={}, imports={}, import_resolutions={}, external_modules={}, exports={}, references={}, external_references={}, dependencies={}, subclass_edges={}, bytes={}, lines={}, files_with_errors={})",
                self.files,
                self.symbols,
                self.classes,
                self.functions,
                self.global_variables,
                self.imports,
                self.import_resolutions,
                self.external_modules,
                self.exports,
                self.references,
                self.external_references,
                self.dependencies,
                self.subclass_edges,
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

        fn debug_graph_json(&self) -> PyResult<String> {
            self.inner
                .debug_graph_json()
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

        fn external_references_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.external_references)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn dependencies_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.dependencies)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn file_by_id_json(&self, file_id: u32) -> PyResult<String> {
            serde_json::to_string(&self.inner.files.iter().find(|file| file.id == file_id))
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn file_by_path_json(&self, path: &str) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .files
                    .iter()
                    .find(|file| file.path.as_ref() == path),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn file_by_path_ignore_case_json(&self, path: &str) -> PyResult<String> {
            let normalized = path.to_lowercase();
            serde_json::to_string(
                &self
                    .inner
                    .files
                    .iter()
                    .find(|file| file.path.as_ref().to_lowercase() == normalized),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn symbols_for_file_json(&self, file_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .symbols
                .iter()
                .filter(|symbol| symbol.file_id == file_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn symbols_for_file_by_name_json(&self, file_id: u32, name: &str) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .symbols
                .iter()
                .filter(|symbol| symbol.file_id == file_id && symbol.name.as_ref() == name)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn symbols_for_file_by_byte_range_json(
            &self,
            file_id: u32,
            start_byte: usize,
            end_byte: usize,
        ) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .symbols
                .iter()
                .filter(|symbol| {
                    symbol.file_id == file_id
                        && ranges_overlap(
                            symbol.range.start_byte,
                            symbol.range.end_byte,
                            start_byte,
                            end_byte,
                        )
                })
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn symbols_for_parent_json(&self, parent_symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .symbols
                .iter()
                .filter(|symbol| symbol.parent_symbol_id == Some(parent_symbol_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn symbol_by_id_json(&self, symbol_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .symbols
                    .iter()
                    .find(|symbol| symbol.id == symbol_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn top_level_symbols_by_name_json(&self, name: &str) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .symbols
                .iter()
                .filter(|symbol| symbol.is_top_level && symbol.name.as_ref() == name)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn top_level_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, None)
        }

        fn top_level_class_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::Class))
        }

        fn top_level_function_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::Function))
        }

        fn top_level_global_variable_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::GlobalVariable))
        }

        fn top_level_interface_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::Interface))
        }

        fn top_level_type_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::TypeAlias))
        }

        fn top_level_enum_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::Enum))
        }

        fn top_level_namespace_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::Namespace))
        }

        fn imports_for_file_json(&self, file_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .imports
                .iter()
                .filter(|import| import.file_id == file_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn imports_for_file_by_lookup_json(&self, file_id: u32, lookup: &str) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .imports
                .iter()
                .filter(|import| {
                    import.file_id == file_id
                        && import_lookup_candidates(
                            import.module.as_ref().map(|value| value.as_ref()),
                            import.name.as_ref().map(|value| value.as_ref()),
                            import.alias.as_ref().map(|value| value.as_ref()),
                            lookup,
                        )
                })
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn imports_for_file_by_byte_range_json(
            &self,
            file_id: u32,
            start_byte: usize,
            end_byte: usize,
        ) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .imports
                .iter()
                .filter(|import| {
                    import.file_id == file_id
                        && ranges_overlap(
                            import.range.start_byte,
                            import.range.end_byte,
                            start_byte,
                            end_byte,
                        )
                })
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn import_by_id_json(&self, import_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .imports
                    .iter()
                    .find(|import| import.id == import_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn import_resolution_for_import_json(&self, import_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .import_resolutions
                    .iter()
                    .find(|resolution| resolution.import_id == import_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn import_resolutions_to_file_json(&self, file_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .import_resolutions
                .iter()
                .filter(|resolution| resolution.target_file_id == file_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn import_resolutions_to_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .import_resolutions
                .iter()
                .filter(|resolution| resolution.target_symbol_id == Some(symbol_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn external_module_for_import_json(&self, import_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .external_modules
                    .iter()
                    .find(|external_module| external_module.import_id == import_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn dependencies_from_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .dependencies
                .iter()
                .filter(|dependency| dependency.source_symbol_id == symbol_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn dependencies_for_file_json(&self, file_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .dependencies
                .iter()
                .filter(|dependency| dependency.source_file_id == file_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn dependencies_to_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .dependencies
                .iter()
                .filter(|dependency| dependency.target_symbol_id == symbol_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn reference_by_id_json(&self, reference_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .references
                    .iter()
                    .find(|reference| reference.id == reference_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn references_to_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .references
                .iter()
                .filter(|reference| reference.target_symbol_id == symbol_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn references_from_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .references
                .iter()
                .filter(|reference| reference.source_symbol_id == Some(symbol_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn references_for_import_json(&self, import_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .references
                .iter()
                .filter(|reference| reference.import_id == Some(import_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn external_references_from_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .external_references
                .iter()
                .filter(|reference| reference.source_symbol_id == Some(symbol_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn external_references_for_import_json(&self, import_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .external_references
                .iter()
                .filter(|reference| reference.import_id == import_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn file_ids(&self) -> Vec<u32> {
            self.inner.files.iter().map(|file| file.id).collect()
        }

        fn symbol_ids(&self) -> Vec<u32> {
            self.inner.symbols.iter().map(|symbol| symbol.id).collect()
        }

        fn top_level_symbol_ids(&self) -> Vec<u32> {
            self.inner
                .symbols
                .iter()
                .filter(|symbol| symbol.is_top_level)
                .map(|symbol| symbol.id)
                .collect()
        }

        #[getter]
        fn top_level_symbol_count(&self) -> usize {
            self.inner
                .symbols
                .iter()
                .filter(|symbol| symbol.is_top_level)
                .count()
        }

        #[getter]
        fn top_level_class_count(&self) -> usize {
            self.top_level_symbol_count_by_kind(SymbolKind::Class)
        }

        #[getter]
        fn top_level_function_count(&self) -> usize {
            self.top_level_symbol_count_by_kind(SymbolKind::Function)
        }

        #[getter]
        fn top_level_global_variable_count(&self) -> usize {
            self.top_level_symbol_count_by_kind(SymbolKind::GlobalVariable)
        }

        fn class_ids(&self) -> Vec<u32> {
            self.symbol_ids_by_kind(SymbolKind::Class)
        }

        fn function_ids(&self) -> Vec<u32> {
            self.symbol_ids_by_kind(SymbolKind::Function)
        }

        fn global_variable_ids(&self) -> Vec<u32> {
            self.symbol_ids_by_kind(SymbolKind::GlobalVariable)
        }

        fn import_ids(&self) -> Vec<u32> {
            self.inner.imports.iter().map(|import| import.id).collect()
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
            0
        }

        #[getter]
        fn reference_count(&self) -> usize {
            self.inner.references.len()
        }

        #[getter]
        fn external_reference_count(&self) -> usize {
            self.inner.external_references.len()
        }

        #[getter]
        fn function_call_count(&self) -> usize {
            0
        }

        #[getter]
        fn promise_chain_count(&self) -> usize {
            0
        }

        #[getter]
        fn dependency_count(&self) -> usize {
            self.inner.dependencies.len()
        }

        #[getter]
        fn subclass_edge_count(&self) -> usize {
            0
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

    impl PyPythonIndex {
        fn symbol_ids_by_kind(&self, kind: SymbolKind) -> Vec<u32> {
            self.inner
                .symbols
                .iter()
                .filter(|symbol| symbol.kind == kind)
                .map(|symbol| symbol.id)
                .collect()
        }

        fn top_level_symbol_count_by_kind(&self, kind: SymbolKind) -> usize {
            self.inner
                .symbols
                .iter()
                .filter(|symbol| symbol.is_top_level && symbol.kind == kind)
                .count()
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

        fn debug_graph_json(&self) -> PyResult<String> {
            self.inner
                .debug_graph_json()
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

        fn external_references_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.external_references)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn function_calls_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.function_calls)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn promise_chains_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.promise_chains)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn jsx_elements_json(&self) -> PyResult<String> {
            serde_json::to_string(&self.inner.jsx_elements)
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

        fn file_by_id_json(&self, file_id: u32) -> PyResult<String> {
            serde_json::to_string(&self.inner.files.iter().find(|file| file.id == file_id))
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn file_by_path_json(&self, path: &str) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .files
                    .iter()
                    .find(|file| file.path.as_ref() == path),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn file_by_path_ignore_case_json(&self, path: &str) -> PyResult<String> {
            let normalized = path.to_lowercase();
            serde_json::to_string(
                &self
                    .inner
                    .files
                    .iter()
                    .find(|file| file.path.as_ref().to_lowercase() == normalized),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn symbols_for_file_json(&self, file_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .symbols
                .iter()
                .filter(|symbol| symbol.file_id == file_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn symbols_for_file_by_name_json(&self, file_id: u32, name: &str) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .symbols
                .iter()
                .filter(|symbol| symbol.file_id == file_id && symbol.name.as_ref() == name)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn symbols_for_file_by_byte_range_json(
            &self,
            file_id: u32,
            start_byte: usize,
            end_byte: usize,
        ) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .symbols
                .iter()
                .filter(|symbol| {
                    symbol.file_id == file_id
                        && ranges_overlap(
                            symbol.range.start_byte,
                            symbol.range.end_byte,
                            start_byte,
                            end_byte,
                        )
                })
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn symbols_for_parent_json(&self, parent_symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .symbols
                .iter()
                .filter(|symbol| symbol.parent_symbol_id == Some(parent_symbol_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn symbol_by_id_json(&self, symbol_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .symbols
                    .iter()
                    .find(|symbol| symbol.id == symbol_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn top_level_symbols_by_name_json(&self, name: &str) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .symbols
                .iter()
                .filter(|symbol| symbol.is_top_level && symbol.name.as_ref() == name)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn top_level_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, None)
        }

        fn top_level_class_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::Class))
        }

        fn top_level_function_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::Function))
        }

        fn top_level_global_variable_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::GlobalVariable))
        }

        fn top_level_interface_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::Interface))
        }

        fn top_level_type_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::TypeAlias))
        }

        fn top_level_enum_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::Enum))
        }

        fn top_level_namespace_symbols_json(&self) -> PyResult<String> {
            top_level_symbols_json(&self.inner.symbols, Some(SymbolKind::Namespace))
        }

        fn imports_for_file_json(&self, file_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .imports
                .iter()
                .filter(|import| import.file_id == file_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn imports_for_file_by_lookup_json(&self, file_id: u32, lookup: &str) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .imports
                .iter()
                .filter(|import| {
                    import.file_id == file_id
                        && import_lookup_candidates(
                            import.module.as_ref().map(|value| value.as_ref()),
                            import.name.as_ref().map(|value| value.as_ref()),
                            import.alias.as_ref().map(|value| value.as_ref()),
                            lookup,
                        )
                })
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn imports_for_file_by_byte_range_json(
            &self,
            file_id: u32,
            start_byte: usize,
            end_byte: usize,
        ) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .imports
                .iter()
                .filter(|import| {
                    import.file_id == file_id
                        && ranges_overlap(
                            import.range.start_byte,
                            import.range.end_byte,
                            start_byte,
                            end_byte,
                        )
                })
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn import_by_id_json(&self, import_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .imports
                    .iter()
                    .find(|import| import.id == import_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn exports_for_file_json(&self, file_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .exports
                .iter()
                .filter(|export| export.file_id == file_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn exports_for_file_by_name_json(&self, file_id: u32, name: &str) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .exports
                .iter()
                .filter(|export| export.file_id == file_id && export.name.as_deref() == Some(name))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn exports_for_file_by_byte_range_json(
            &self,
            file_id: u32,
            start_byte: usize,
            end_byte: usize,
        ) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .exports
                .iter()
                .filter(|export| {
                    export.file_id == file_id
                        && ranges_overlap(
                            export.range.start_byte,
                            export.range.end_byte,
                            start_byte,
                            end_byte,
                        )
                })
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn exports_for_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .exports
                .iter()
                .filter(|export| export.symbol_id == Some(symbol_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn export_by_id_json(&self, export_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .exports
                    .iter()
                    .find(|export| export.id == export_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn import_resolution_for_import_json(&self, import_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .import_resolutions
                    .iter()
                    .find(|resolution| resolution.import_id == import_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn import_resolutions_to_file_json(&self, file_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .import_resolutions
                .iter()
                .filter(|resolution| resolution.target_file_id == file_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn import_resolutions_to_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .import_resolutions
                .iter()
                .filter(|resolution| resolution.target_symbol_id == Some(symbol_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn external_module_for_import_json(&self, import_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .external_modules
                    .iter()
                    .find(|external_module| external_module.import_id == import_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn dependencies_from_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .dependencies
                .iter()
                .filter(|dependency| dependency.source_symbol_id == symbol_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn dependencies_for_file_json(&self, file_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .dependencies
                .iter()
                .filter(|dependency| dependency.source_file_id == file_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn dependencies_to_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .dependencies
                .iter()
                .filter(|dependency| dependency.target_symbol_id == symbol_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn reference_by_id_json(&self, reference_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .references
                    .iter()
                    .find(|reference| reference.id == reference_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn references_to_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .references
                .iter()
                .filter(|reference| reference.target_symbol_id == symbol_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn references_from_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .references
                .iter()
                .filter(|reference| reference.source_symbol_id == Some(symbol_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn references_for_import_json(&self, import_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .references
                .iter()
                .filter(|reference| reference.import_id == Some(import_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn external_references_from_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .external_references
                .iter()
                .filter(|reference| reference.source_symbol_id == Some(symbol_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn external_references_for_import_json(&self, import_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .external_references
                .iter()
                .filter(|reference| reference.import_id == import_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn function_call_by_id_json(&self, call_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .function_calls
                    .iter()
                    .find(|call| call.id == call_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn function_calls_for_file_json(&self, file_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .function_calls
                .iter()
                .filter(|call| call.source_file_id == file_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn function_calls_for_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .function_calls
                .iter()
                .filter(|call| call.source_symbol_id == Some(symbol_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn promise_chain_by_id_json(&self, chain_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .promise_chains
                    .iter()
                    .find(|chain| chain.id == chain_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn promise_chains_for_file_json(&self, file_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .promise_chains
                .iter()
                .filter(|chain| chain.source_file_id == file_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn promise_chains_for_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .promise_chains
                .iter()
                .filter(|chain| chain.source_symbol_id == Some(symbol_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn jsx_element_by_id_json(&self, element_id: u32) -> PyResult<String> {
            serde_json::to_string(
                &self
                    .inner
                    .jsx_elements
                    .iter()
                    .find(|element| element.id == element_id),
            )
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn jsx_elements_for_file_json(&self, file_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .jsx_elements
                .iter()
                .filter(|element| element.source_file_id == file_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn jsx_elements_for_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .jsx_elements
                .iter()
                .filter(|element| element.source_symbol_id == Some(symbol_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn jsx_elements_for_parent_json(&self, parent_element_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .jsx_elements
                .iter()
                .filter(|element| element.parent_jsx_element_id == Some(parent_element_id))
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn subclass_edges_from_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .subclass_edges
                .iter()
                .filter(|edge| edge.source_symbol_id == symbol_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn subclass_edges_to_symbol_json(&self, symbol_id: u32) -> PyResult<String> {
            let records: Vec<_> = self
                .inner
                .subclass_edges
                .iter()
                .filter(|edge| edge.target_symbol_id == symbol_id)
                .collect();
            serde_json::to_string(&records)
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))
        }

        fn file_ids(&self) -> Vec<u32> {
            self.inner.files.iter().map(|file| file.id).collect()
        }

        fn symbol_ids(&self) -> Vec<u32> {
            self.inner.symbols.iter().map(|symbol| symbol.id).collect()
        }

        fn top_level_symbol_ids(&self) -> Vec<u32> {
            self.inner
                .symbols
                .iter()
                .filter(|symbol| symbol.is_top_level)
                .map(|symbol| symbol.id)
                .collect()
        }

        #[getter]
        fn top_level_symbol_count(&self) -> usize {
            self.inner
                .symbols
                .iter()
                .filter(|symbol| symbol.is_top_level)
                .count()
        }

        #[getter]
        fn top_level_class_count(&self) -> usize {
            self.top_level_symbol_count_by_kind(SymbolKind::Class)
        }

        #[getter]
        fn top_level_function_count(&self) -> usize {
            self.top_level_symbol_count_by_kind(SymbolKind::Function)
        }

        #[getter]
        fn top_level_global_variable_count(&self) -> usize {
            self.top_level_symbol_count_by_kind(SymbolKind::GlobalVariable)
        }

        fn class_ids(&self) -> Vec<u32> {
            self.symbol_ids_by_kind(SymbolKind::Class)
        }

        fn function_ids(&self) -> Vec<u32> {
            self.symbol_ids_by_kind(SymbolKind::Function)
        }

        fn global_variable_ids(&self) -> Vec<u32> {
            self.symbol_ids_by_kind(SymbolKind::GlobalVariable)
        }

        fn interface_ids(&self) -> Vec<u32> {
            self.symbol_ids_by_kind(SymbolKind::Interface)
        }

        fn type_ids(&self) -> Vec<u32> {
            self.symbol_ids_by_kind(SymbolKind::TypeAlias)
        }

        fn enum_ids(&self) -> Vec<u32> {
            self.symbol_ids_by_kind(SymbolKind::Enum)
        }

        fn namespace_ids(&self) -> Vec<u32> {
            self.symbol_ids_by_kind(SymbolKind::Namespace)
        }

        #[getter]
        fn interface_count(&self) -> usize {
            self.symbol_count_by_kind(SymbolKind::Interface)
        }

        #[getter]
        fn type_count(&self) -> usize {
            self.symbol_count_by_kind(SymbolKind::TypeAlias)
        }

        #[getter]
        fn enum_count(&self) -> usize {
            self.symbol_count_by_kind(SymbolKind::Enum)
        }

        #[getter]
        fn namespace_count(&self) -> usize {
            self.symbol_count_by_kind(SymbolKind::Namespace)
        }

        fn import_ids(&self) -> Vec<u32> {
            self.inner.imports.iter().map(|import| import.id).collect()
        }

        fn export_ids(&self) -> Vec<u32> {
            self.inner.exports.iter().map(|export| export.id).collect()
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
        fn external_reference_count(&self) -> usize {
            self.inner.external_references.len()
        }

        #[getter]
        fn function_call_count(&self) -> usize {
            self.inner.function_calls.len()
        }

        #[getter]
        fn promise_chain_count(&self) -> usize {
            self.inner.promise_chains.len()
        }

        #[getter]
        fn jsx_element_count(&self) -> usize {
            self.inner.jsx_elements.len()
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

    impl PyTypeScriptIndex {
        fn symbol_ids_by_kind(&self, kind: SymbolKind) -> Vec<u32> {
            self.inner
                .symbols
                .iter()
                .filter(|symbol| symbol.kind == kind)
                .map(|symbol| symbol.id)
                .collect()
        }

        fn symbol_count_by_kind(&self, kind: SymbolKind) -> usize {
            self.inner
                .symbols
                .iter()
                .filter(|symbol| symbol.kind == kind)
                .count()
        }

        fn top_level_symbol_count_by_kind(&self, kind: SymbolKind) -> usize {
            self.inner
                .symbols
                .iter()
                .filter(|symbol| symbol.is_top_level && symbol.kind == kind)
                .count()
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

    fn top_level_symbols_json(
        symbols: &[SymbolRecord],
        kind: Option<SymbolKind>,
    ) -> PyResult<String> {
        let records: Vec<_> = symbols
            .iter()
            .filter(|symbol| symbol.is_top_level && kind.map_or(true, |kind| symbol.kind == kind))
            .collect();
        serde_json::to_string(&records).map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    fn import_lookup_candidates(
        module: Option<&str>,
        name: Option<&str>,
        alias: Option<&str>,
        lookup: &str,
    ) -> bool {
        let lookup = lookup.trim();
        [alias, name, module]
            .into_iter()
            .flatten()
            .filter(|value| !value.is_empty())
            .any(|value| {
                let unquoted = value.trim_matches(['\'', '"', '`']);
                lookup == value
                    || lookup.contains(value)
                    || (!unquoted.is_empty() && (lookup == unquoted || lookup.contains(unquoted)))
            })
    }

    fn ranges_overlap(
        record_start: usize,
        record_end: usize,
        query_start: usize,
        query_end: usize,
    ) -> bool {
        if query_start == query_end {
            record_start <= query_start && query_start < record_end
        } else {
            record_start < query_end && query_start < record_end
        }
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
            assert!(index
                .file_by_path_ignore_case_json("PKG/MOD.PY")
                .unwrap()
                .contains("\"pkg/mod.py\""));
            assert_eq!(
                index
                    .file_by_path_ignore_case_json("PKG/MISSING.PY")
                    .unwrap(),
                "null"
            );
            assert!(index
                .symbols_for_file_by_byte_range_json(0, 0, 1_000)
                .unwrap()
                .contains("\"Service\""));
            assert!(index
                .imports_for_file_by_byte_range_json(0, 0, 9)
                .unwrap()
                .contains("\"os\""));
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
            assert_eq!(index.file_ids(), vec![0, 1, 2]);
            assert_eq!(index.symbol_ids(), vec![0, 1, 2]);
            assert_eq!(index.top_level_symbol_ids(), vec![0, 1, 2]);
            assert_eq!(index.class_ids(), vec![1, 2]);
            assert_eq!(index.function_ids(), Vec::<u32>::new());
            assert_eq!(index.global_variable_ids(), vec![0]);
            assert_eq!(index.import_ids(), vec![0, 1]);
            assert!(index.files_json().unwrap().contains("\"pkg/base.py\""));
            assert!(index
                .files_json()
                .unwrap()
                .contains("\"language\":\"python\""));
            assert!(index.files_json().unwrap().contains("\"content_hash\""));
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
            let debug_graph: serde_json::Value =
                serde_json::from_str(&index.debug_graph_json().unwrap()).unwrap();
            let nodes = debug_graph["nodes"].as_array().unwrap();
            let edges = debug_graph["edges"].as_array().unwrap();
            assert!(nodes.iter().any(|node| {
                node.get("id").and_then(serde_json::Value::as_str) == Some("symbol:2")
                    && node.get("node_type").and_then(serde_json::Value::as_str) == Some("symbol")
            }));
            assert!(edges.iter().any(|edge| {
                edge.get("edge_type").and_then(serde_json::Value::as_str)
                    == Some("import_resolution")
                    && edge.get("source").and_then(serde_json::Value::as_str) == Some("import:0")
                    && edge.get("target").and_then(serde_json::Value::as_str) == Some("symbol:1")
            }));
            assert!(edges.iter().any(|edge| {
                edge.get("edge_type").and_then(serde_json::Value::as_str) == Some("dependency")
                    && edge.get("reference_ids") == Some(&serde_json::json!([0]))
                    && edge.get("reference_count") == Some(&serde_json::json!(1))
            }));
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
            assert_eq!(index.function_call_count(), 1);
            assert_eq!(index.promise_chain_count(), 0);
            assert_eq!(index.file_ids(), vec![0, 1]);
            assert_eq!(index.symbol_ids(), vec![0, 1]);
            assert_eq!(index.top_level_symbol_ids(), vec![0, 1]);
            assert_eq!(index.class_ids(), Vec::<u32>::new());
            assert_eq!(index.function_ids(), vec![0, 1]);
            assert_eq!(index.global_variable_ids(), Vec::<u32>::new());
            assert_eq!(index.interface_ids(), Vec::<u32>::new());
            assert_eq!(index.type_ids(), Vec::<u32>::new());
            assert_eq!(index.enum_ids(), Vec::<u32>::new());
            assert_eq!(index.namespace_ids(), Vec::<u32>::new());
            assert_eq!(index.import_ids(), vec![0, 1]);
            assert_eq!(index.export_ids(), vec![0, 1]);
            assert!(index
                .file_by_path_ignore_case_json("SRC/APP.TSX")
                .unwrap()
                .contains("\"src/app.tsx\""));
            assert_eq!(
                index
                    .file_by_path_ignore_case_json("SRC/MISSING.TSX")
                    .unwrap(),
                "null"
            );
            assert!(index.files_json().unwrap().contains("\"src/app.tsx\""));
            assert!(index.files_json().unwrap().contains("\"language\":\"tsx\""));
            assert!(index.files_json().unwrap().contains("\"content_hash\""));
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
            assert!(index
                .symbols_for_file_by_byte_range_json(0, 0, 1_000)
                .unwrap()
                .contains("\"Page\""));
            assert!(index
                .imports_for_file_by_byte_range_json(0, 0, 30)
                .unwrap()
                .contains("\"React\""));
            assert!(index
                .exports_for_file_by_byte_range_json(0, 0, 1_000)
                .unwrap()
                .contains("\"Page\""));
            assert_eq!(index.subclass_edges_json().unwrap(), "[]");
            assert!(index.to_json().unwrap().contains("\"import_resolutions\""));
            assert!(index.to_json().unwrap().contains("\"external_modules\""));
            assert!(index.to_json().unwrap().contains("\"exports\""));
            assert!(index.to_json().unwrap().contains("\"references\""));
            assert!(index.to_json().unwrap().contains("\"dependencies\""));
            assert!(index.to_json().unwrap().contains("\"subclass_edges\""));
            let debug_graph: serde_json::Value =
                serde_json::from_str(&index.debug_graph_json().unwrap()).unwrap();
            let nodes = debug_graph["nodes"].as_array().unwrap();
            let edges = debug_graph["edges"].as_array().unwrap();
            assert!(nodes.iter().any(|node| {
                node.get("id").and_then(serde_json::Value::as_str) == Some("export:0")
                    && node.get("node_type").and_then(serde_json::Value::as_str) == Some("export")
            }));
            assert!(edges.iter().any(|edge| {
                edge.get("edge_type").and_then(serde_json::Value::as_str) == Some("export_symbol")
                    && edge.get("source").and_then(serde_json::Value::as_str) == Some("export:0")
                    && edge.get("target").and_then(serde_json::Value::as_str) == Some("symbol:0")
            }));
            assert!(edges.iter().any(|edge| {
                edge.get("edge_type").and_then(serde_json::Value::as_str) == Some("reference")
                    && edge.get("name").and_then(serde_json::Value::as_str) == Some("helper")
            }));
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
