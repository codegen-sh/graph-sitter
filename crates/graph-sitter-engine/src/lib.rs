#![forbid(unsafe_code)]

const ENABLED_FEATURES: &[&str] = &["skeleton"];

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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn debug_info_reports_version_and_skeleton_feature() {
        let info = Engine::new().debug_info();

        assert_eq!(info.version(), env!("CARGO_PKG_VERSION"));
        assert_eq!(info.enabled_features(), ["skeleton"]);
    }
}
