#![cfg_attr(not(feature = "pyo3-bindings"), forbid(unsafe_code))]

pub fn engine_version() -> &'static str {
    graph_sitter_engine::engine_version()
}

pub fn enabled_features() -> &'static [&'static str] {
    graph_sitter_engine::debug_info().enabled_features()
}

#[cfg(feature = "pyo3-bindings")]
mod bindings {
    use graph_sitter_engine::{self, Engine, EngineInfo};
    use pyo3::prelude::*;

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
    }

    #[pyfunction(name = "engine_version")]
    fn py_engine_version() -> &'static str {
        graph_sitter_engine::engine_version()
    }

    #[pyfunction(name = "debug_info")]
    fn py_debug_info() -> PyEngineInfo {
        graph_sitter_engine::debug_info().into()
    }

    #[pymodule]
    fn graph_sitter_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add_class::<PyEngine>()?;
        m.add_class::<PyEngineInfo>()?;
        m.add_function(wrap_pyfunction!(py_engine_version, m)?)?;
        m.add_function(wrap_pyfunction!(py_debug_info, m)?)?;
        Ok(())
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn debug_info_forwards_core_engine_metadata() {
            let info = py_debug_info();

            assert_eq!(info.version, graph_sitter_engine::engine_version());
            assert_eq!(
                info.enabled_features,
                vec!["skeleton".to_owned(), "python-index".to_owned()]
            );
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn forwards_core_engine_metadata_without_python_linking() {
        assert_eq!(engine_version(), graph_sitter_engine::engine_version());
        assert_eq!(enabled_features(), ["skeleton", "python-index"]);
    }
}
