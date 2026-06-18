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

On macOS, local extension smoke tests currently need PyO3 pointed at the active Python interpreter and dynamic lookup linker flags:

```sh
PYO3_PYTHON="$(uv run python -c 'import sys; print(sys.executable)')" \
RUSTFLAGS="-C link-arg=-undefined -C link-arg=dynamic_lookup" \
cargo build --release -p graph-sitter-py --features extension-module
```

The current module exports `Engine`, `EngineInfo`, `PythonIndex`, `IndexSummary`, `engine_version`, `debug_info`, `index_python_path`, and `index_python_paths`. A successful smoke import on this repo returned 1127 files, 3117 symbols, and 6414 imports for the compact Python index at that commit. The Python shell integration now uses `index_python_paths` so Rust indexes the exact file list returned by `RepoOperator.iter_files(...)`.

## Integration Choice

This skeleton does not alter the Hatch/Cython Python packaging path. The current `hatch.toml` custom hook is disabled by default, so wiring Rust into wheels should be a separate packaging/CI task after the backend facade and import smoke test are defined.
