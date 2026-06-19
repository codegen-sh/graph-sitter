#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

uv run ruff check

cargo fmt --all --check
cargo test --workspace --all-targets

PYTHON_BIN="$(uv run python -c 'import sys; print(sys.executable)')"
PYO3_PYTHON="$PYTHON_BIN" cargo check -p graph-sitter-py --features pyo3-bindings
PYO3_PYTHON="$PYTHON_BIN" cargo test -p graph-sitter-py --features pyo3-bindings
if [[ "$(uname)" == "Darwin" ]]; then
  export RUSTFLAGS="${RUSTFLAGS:-} -C link-arg=-undefined -C link-arg=dynamic_lookup"
fi
PYO3_PYTHON="$PYTHON_BIN" cargo build -p graph-sitter-py --features extension-module

uv run python -m py_compile \
  src/graph_sitter/codebase/rust_backend.py \
  tests/unit/sdk/codebase/test_rust_backend.py \
  tests/integration/rust_rewrite/test_pinned_airflow_snapshot.py \
  rust-rewrite/tools/benchmark_pinned_typescript_repo.py \
  rust-rewrite/tools/benchmark_pinned_python_repo.py \
  rust-rewrite/tools/compare_rust_python_index.py \
  rust-rewrite/tools/measure_codebase_rust_backend.py \
  rust-rewrite/tools/measure_python_backend.py \
  rust-rewrite/tools/measure_rust_facade.py \
  rust-rewrite/tools/measure_typescript_rust_index.py \
  rust-rewrite/tools/snapshot_pinned_python_repo.py

uv run pytest \
  tests/unit/sdk/codebase/test_rust_backend.py \
  tests/integration/rust_rewrite/test_pinned_airflow_snapshot.py \
  -q
