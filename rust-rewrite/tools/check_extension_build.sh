#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-$(uv run python -c 'import sys; print(sys.executable)')}"
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

EXTENSION_DIR="${GRAPH_SITTER_EXTENSION_CHECK_DIR:-${TMPDIR:-/tmp}/graph_sitter_py_extension_check}"
EXTENSION_DIR="$EXTENSION_DIR" "$PYTHON_BIN" - <<'PY'
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

extension_dir = Path(os.environ["EXTENSION_DIR"])
extension_dir.mkdir(parents=True, exist_ok=True)
target = extension_dir / f"graph_sitter_py{sysconfig.get_config_var('EXT_SUFFIX')}"
shutil.copy2(source, target)
PY

PYTHONPATH="$EXTENSION_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - <<'PY'
import tempfile
from pathlib import Path

import graph_sitter_py

with tempfile.TemporaryDirectory(prefix="graph-sitter-extension-smoke-") as tmpdir:
    repo = Path(tmpdir)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "pkg" / "service.py").write_text(
        "import os\n\nclass Service:\n    pass\n", encoding="utf-8"
    )
    index = graph_sitter_py.index_python_path(str(repo))
    summary = index.summary().as_dict()
    assert summary["files"] == 2, summary
    assert summary["classes"] == 1, summary
    assert summary["imports"] == 1, summary

print(f"graph_sitter_py {graph_sitter_py.engine_version()} extension smoke passed")
PY
