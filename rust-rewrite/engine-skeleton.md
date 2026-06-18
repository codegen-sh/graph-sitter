# Rust Engine Skeleton Notes

## Layout

- `Cargo.toml` defines a standalone Cargo workspace. It is not referenced by `pyproject.toml`, `hatch.toml`, or the current Python package build.
- `crates/graph-sitter-engine` is the dependency-free core crate. It exposes a minimal `Engine` plus `debug_info()` metadata API.
- `crates/graph-sitter-py` is a PyO3 placeholder crate. Its default build is a Rust-testable stub that forwards the same metadata API without linking Python. Enabling `pyo3-bindings` exposes a future Python extension module named `graph_sitter_py`.

## Build Commands

```sh
cargo fmt --all
cargo test --workspace
```

The PyO3 crate intentionally does not enable PyO3 by default so normal `cargo test --workspace` does not depend on a local Python development library. Build tooling can enable the crate feature later when producing a Python extension:

```sh
cargo build -p graph-sitter-py --features extension-module
```

## Integration Choice

This skeleton does not alter the Hatch/Cython Python packaging path. The current `hatch.toml` custom hook is disabled by default, so wiring Rust into wheels should be a separate packaging/CI task after the backend facade and import smoke test are defined.
