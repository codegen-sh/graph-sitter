#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

uv run ruff check

bash -n rust-rewrite/tools/check_fast.sh
bash -n rust-rewrite/tools/check_extension_build.sh
bash -n rust-rewrite/tools/check_pinned_large_repos.sh

cargo fmt --all --check
cargo test --workspace --all-targets

PYTHON_BIN="$(uv run python -c 'import sys; print(sys.executable)')"
PYTHON_LIBDIR="$("$PYTHON_BIN" - <<'PY'
import sysconfig

print(sysconfig.get_config_var("LIBDIR") or "")
PY
)"
if [[ -n "$PYTHON_LIBDIR" && -d "$PYTHON_LIBDIR" ]]; then
  export LD_LIBRARY_PATH="$PYTHON_LIBDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
PYO3_PYTHON="$PYTHON_BIN" cargo check -p graph-sitter-py --features pyo3-bindings
PYO3_PYTHON="$PYTHON_BIN" cargo test -p graph-sitter-py --features pyo3-bindings
if [[ "$(uname)" == "Darwin" ]]; then
  export RUSTFLAGS="${RUSTFLAGS:-} -C link-arg=-undefined -C link-arg=dynamic_lookup"
fi
PYO3_PYTHON="$PYTHON_BIN" cargo build -p graph-sitter-py --features extension-module

FAST_EXTENSION_DIR="${TMPDIR:-/tmp}/graph_sitter_py_fast_checks"
FAST_EXTENSION_DIR="$FAST_EXTENSION_DIR" "$PYTHON_BIN" - <<'PY'
import os
import shutil
import sys
import sysconfig
from pathlib import Path

root = Path.cwd()
if sys.platform == "darwin":
    source = root / "target/debug/libgraph_sitter_py.dylib"
elif os.name == "nt":
    source = root / "target/debug/graph_sitter_py.dll"
else:
    source = root / "target/debug/libgraph_sitter_py.so"
if not source.exists():
    msg = f"built extension artifact not found: {source}"
    raise FileNotFoundError(msg)

extension_dir = Path(os.environ["FAST_EXTENSION_DIR"])
extension_dir.mkdir(parents=True, exist_ok=True)
target = extension_dir / f"graph_sitter_py{sysconfig.get_config_var('EXT_SUFFIX')}"
shutil.copy2(source, target)
PY

uv run python -m py_compile \
  src/graph_sitter/codebase/rust_backend.py \
  tests/unit/sdk/codebase/test_rust_backend.py \
  tests/unit/sdk/codebase/test_rust_rewrite_readiness.py \
  tests/integration/rust_rewrite/test_pinned_airflow_snapshot.py \
  tests/integration/rust_rewrite/test_pinned_codemods.py \
  tests/integration/rust_rewrite/test_pinned_nextjs_snapshot.py \
  tests/integration/rust_rewrite/test_pinned_semantic_parity.py \
  tests/integration/rust_rewrite/test_python_rust_parity_fixture.py \
  rust-rewrite/tools/check_pinned_codemods.py \
  rust-rewrite/tools/check_p0_parity_coverage.py \
  rust-rewrite/tools/check_pinned_python_codebase.py \
  rust-rewrite/tools/check_wheel_pinned_python_repo.py \
  rust-rewrite/tools/check_wheel_pinned_typescript_repo.py \
  rust-rewrite/tools/check_rollout_readiness.py \
  rust-rewrite/tools/check_supported_subset.py \
  rust-rewrite/tools/check_pinned_semantic_parity.py \
  rust-rewrite/tools/check_python_rust_parity_fixture.py \
  rust-rewrite/tools/check_pinned_typescript_codebase.py \
  rust-rewrite/tools/benchmark_pinned_typescript_repo.py \
  rust-rewrite/tools/benchmark_pinned_python_repo.py \
  rust-rewrite/tools/compare_rust_python_index.py \
  rust-rewrite/tools/measure_codebase_rust_backend.py \
  rust-rewrite/tools/measure_python_backend.py \
  rust-rewrite/tools/measure_rust_facade.py \
  rust-rewrite/tools/measure_typescript_rust_index.py \
  rust-rewrite/tools/snapshot_pinned_typescript_repo.py \
  rust-rewrite/tools/snapshot_pinned_python_repo.py

uv run python rust-rewrite/tools/check_python_rust_parity_fixture.py \
  --skip-build-extension \
  --extension-dir "$FAST_EXTENSION_DIR"

uv run python rust-rewrite/tools/check_supported_subset.py
uv run python rust-rewrite/tools/check_p0_parity_coverage.py

uv run pytest \
  tests/unit/sdk/codebase/test_rust_backend.py \
  tests/unit/sdk/codebase/test_rust_rewrite_readiness.py \
  tests/integration/rust_rewrite/test_pinned_airflow_snapshot.py \
  tests/integration/rust_rewrite/test_pinned_codemods.py \
  tests/integration/rust_rewrite/test_pinned_nextjs_snapshot.py \
  tests/integration/rust_rewrite/test_pinned_semantic_parity.py \
  tests/integration/rust_rewrite/test_python_rust_parity_fixture.py \
  -q
