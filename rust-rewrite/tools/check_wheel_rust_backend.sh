#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON_VERSION="${PYTHON_VERSION:-3.13}"

run_python() {
  if command -v python >/dev/null 2>&1; then
    python "$@"
  elif command -v python3 >/dev/null 2>&1; then
    python3 "$@"
  else
    uv run python "$@"
  fi
}

usage() {
  echo "usage: $0 [--wheel PATH]" >&2
}

WHEEL="${GRAPH_SITTER_WHEEL:-}"
if [[ "$#" -gt 0 ]]; then
  case "$1" in
    --wheel)
      if [[ "$#" -ne 2 ]]; then
        usage
        exit 2
      fi
      WHEEL="$2"
      ;;
    *)
      usage
      exit 2
      ;;
  esac
fi

if [[ -n "$WHEEL" ]]; then
  if [[ ! -f "$WHEEL" ]]; then
    echo "Wheel does not exist: $WHEEL" >&2
    exit 1
  fi
  WHEEL="$(run_python -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$WHEEL")"
else
  rm -f dist/graph_sitter-*.whl
  uv build --wheel
  WHEEL="$(ls -t dist/graph_sitter-*.whl | head -n 1)"
fi

if [[ -z "$WHEEL" ]]; then
  echo "No graph-sitter wheel was built" >&2
  exit 1
fi

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

UV_CACHE_DIR="$SCRATCH/uv-cache"
mkdir -p "$UV_CACHE_DIR"
export UV_CACHE_DIR

run_graph_sitter() {
  uvx --python "$PYTHON_VERSION" --from "$WHEEL" graph-sitter "$@"
}

run_python - "$WHEEL" <<'PY'
from pathlib import Path
import sys
import zipfile

wheel = sys.argv[1]
with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    if not any(name.startswith("graph_sitter_py") and name.endswith((".so", ".pyd")) for name in names):
        msg = f"wheel does not include graph_sitter_py extension: {wheel}"
        raise AssertionError(msg)
    if "codemods/codemod.py" not in names:
        msg = f"wheel does not include codemods package: {wheel}"
        raise AssertionError(msg)
    wheel_metadata_names = [name for name in names if name.endswith(".dist-info/WHEEL")]
    if len(wheel_metadata_names) != 1:
        msg = f"wheel does not include exactly one WHEEL metadata file: {wheel}"
        raise AssertionError(msg)
    wheel_metadata = archive.read(wheel_metadata_names[0]).decode()
    tags = [
        line.removeprefix("Tag: ").strip()
        for line in wheel_metadata.splitlines()
        if line.startswith("Tag: ")
    ]
    if "Root-Is-Purelib: false" not in wheel_metadata:
        msg = f"wheel metadata still marks the Rust-backed artifact pure: {wheel}"
        raise AssertionError(msg)
    if not tags or any(tag.endswith("-none-any") for tag in tags):
        msg = f"wheel metadata includes misleading pure-Python tags {tags}: {wheel}"
        raise AssertionError(msg)
    if Path(wheel).name.endswith("-none-any.whl"):
        msg = f"wheel filename includes a pure-Python tag despite graph_sitter_py: {wheel}"
        raise AssertionError(msg)
PY

REPO="$SCRATCH/repo"
git init "$REPO" >/dev/null
git -C "$REPO" config user.email test@example.com
git -C "$REPO" config user.name "Test User"
mkdir -p "$REPO/pkg"
printf '' > "$REPO/pkg/__init__.py"
cat > "$REPO/pkg/service.py" <<'PY'
import os


class Service:
    pass


def run():
    return os.getcwd()
PY
git -C "$REPO" add .
git -C "$REPO" commit -m initial >/dev/null

run_graph_sitter --help >/dev/null

PYTHON_OUTPUT="$(run_graph_sitter parse "$REPO" --language python --backend python --format json)"
run_python - "$PYTHON_OUTPUT" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
assert payload["backend"] == "python", payload
assert payload["backend_requested"] == "python", payload
assert payload["files"] == 2, payload
assert payload["classes"] == 1, payload
assert payload["functions"] == 1, payload
assert payload["imports"] == 1, payload
PY

OUTPUT="$(run_graph_sitter parse "$REPO" --language python --backend rust --fallback error --format json)"
run_python - "$OUTPUT" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
assert payload["backend"] == "rust", payload
assert payload["backend_requested"] == "rust", payload
assert payload["files"] == 2, payload
assert payload["classes"] == 1, payload
assert payload["functions"] == 1, payload
assert payload["imports"] == 1, payload
PY

TRANSFORM="$SCRATCH/rename_transform.py"
cat > "$TRANSFORM" <<'PY'
def rename(codebase):
    function = codebase.get_function("run")
    function.rename("renamed")
    codebase.commit()
PY

set +e
CHECK_OUTPUT="$(run_graph_sitter transform "${TRANSFORM}:rename" "$REPO" --language python --backend rust --fallback error --check 2>&1)"
CHECK_STATUS=$?
set -e
if [[ "$CHECK_STATUS" -ne 1 ]]; then
  echo "Expected transform --check to exit 1 when changes would be produced; got $CHECK_STATUS" >&2
  echo "$CHECK_OUTPUT" >&2
  exit 1
fi
if [[ "$CHECK_OUTPUT" != *"Codemod would produce changes"* ]]; then
  echo "Expected transform --check output to mention produced changes" >&2
  echo "$CHECK_OUTPUT" >&2
  exit 1
fi
if ! grep -q "def run():" "$REPO/pkg/service.py"; then
  echo "transform --check mutated the target repository" >&2
  exit 1
fi

WRITE_OUTPUT="$(run_graph_sitter transform "${TRANSFORM}:rename" "$REPO" --language python --backend rust --fallback error --write)"
if [[ "$WRITE_OUTPUT" != *"Changes have been applied"* ]]; then
  echo "Expected transform --write output to mention applied changes" >&2
  echo "$WRITE_OUTPUT" >&2
  exit 1
fi
if ! grep -q "def renamed():" "$REPO/pkg/service.py"; then
  echo "transform --write did not update the target repository" >&2
  exit 1
fi

REGISTERED_REPO="$SCRATCH/registered-repo"
git init "$REGISTERED_REPO" >/dev/null
git -C "$REGISTERED_REPO" config user.email test@example.com
git -C "$REGISTERED_REPO" config user.name "Test User"
mkdir -p "$REGISTERED_REPO/pkg" "$REGISTERED_REPO/.codegen/codemods/rename"
printf '' > "$REGISTERED_REPO/pkg/__init__.py"
cat > "$REGISTERED_REPO/pkg/app.py" <<'PY'
def target():
    return 1
PY
cat > "$REGISTERED_REPO/.codegen/codemods/rename/rename.py" <<'PY'
import graph_sitter


@graph_sitter.function("rename-target")
def run(codebase):
    function = codebase.get_function("target")
    function.rename("renamed_target")
    codebase.commit()
PY
git -C "$REGISTERED_REPO" add .
git -C "$REGISTERED_REPO" commit -m initial >/dev/null

set +e
RUN_CHECK_OUTPUT="$(run_graph_sitter run rename-target "$REGISTERED_REPO" --language python --backend rust --fallback error --check 2>&1)"
RUN_CHECK_STATUS=$?
set -e
if [[ "$RUN_CHECK_STATUS" -ne 1 ]]; then
  echo "Expected registered run --check to exit 1 when changes would be produced; got $RUN_CHECK_STATUS" >&2
  echo "$RUN_CHECK_OUTPUT" >&2
  exit 1
fi
if [[ "$RUN_CHECK_OUTPUT" != *"Codemod would produce changes"* ]]; then
  echo "Expected registered run --check output to mention produced changes" >&2
  echo "$RUN_CHECK_OUTPUT" >&2
  exit 1
fi
if ! grep -q "def target():" "$REGISTERED_REPO/pkg/app.py"; then
  echo "registered run --check mutated the target repository" >&2
  exit 1
fi

RUN_WRITE_OUTPUT="$(run_graph_sitter run rename-target "$REGISTERED_REPO" --language python --backend rust --fallback error --write)"
if [[ "$RUN_WRITE_OUTPUT" != *"Changes have been applied"* ]]; then
  echo "Expected registered run --write output to mention applied changes" >&2
  echo "$RUN_WRITE_OUTPUT" >&2
  exit 1
fi
if ! grep -q "def renamed_target():" "$REGISTERED_REPO/pkg/app.py"; then
  echo "registered run --write did not update the target repository" >&2
  exit 1
fi

REGISTERED_SUBDIR_REPO="$SCRATCH/registered-subdir-repo"
git init "$REGISTERED_SUBDIR_REPO" >/dev/null
git -C "$REGISTERED_SUBDIR_REPO" config user.email test@example.com
git -C "$REGISTERED_SUBDIR_REPO" config user.name "Test User"
mkdir -p "$REGISTERED_SUBDIR_REPO/src" "$REGISTERED_SUBDIR_REPO/tests" "$REGISTERED_SUBDIR_REPO/.codegen/codemods/scoped"
cat > "$REGISTERED_SUBDIR_REPO/src/app.py" <<'PY'
def target():
    return 1
PY
cat > "$REGISTERED_SUBDIR_REPO/tests/test_app.py" <<'PY'
def target():
    return 2
PY
cat > "$REGISTERED_SUBDIR_REPO/.codegen/codemods/scoped/scoped.py" <<'PY'
import graph_sitter


@graph_sitter.function("assert-scoped")
def run(codebase):
    filepaths = [file.filepath for file in codebase.files]
    if any(filepath.endswith("tests/test_app.py") for filepath in filepaths):
        raise AssertionError(f"unscoped parse: {filepaths}")
    function = codebase.get_function("target")
    function.rename("renamed_target")
    codebase.commit()
PY
git -C "$REGISTERED_SUBDIR_REPO" add .
git -C "$REGISTERED_SUBDIR_REPO" commit -m initial >/dev/null

set +e
RUN_SUBDIR_CHECK_OUTPUT="$(run_graph_sitter run assert-scoped "$REGISTERED_SUBDIR_REPO" --language python --backend rust --fallback error --subdir src --check 2>&1)"
RUN_SUBDIR_CHECK_STATUS=$?
set -e
if [[ "$RUN_SUBDIR_CHECK_STATUS" -ne 1 ]]; then
  echo "Expected registered run --subdir --check to exit 1 when changes would be produced; got $RUN_SUBDIR_CHECK_STATUS" >&2
  echo "$RUN_SUBDIR_CHECK_OUTPUT" >&2
  exit 1
fi
if [[ "$RUN_SUBDIR_CHECK_OUTPUT" != *"Codemod would produce changes"* ]]; then
  echo "Expected registered run --subdir --check output to mention produced changes" >&2
  echo "$RUN_SUBDIR_CHECK_OUTPUT" >&2
  exit 1
fi
if [[ "$RUN_SUBDIR_CHECK_OUTPUT" == *"unscoped parse"* ]]; then
  echo "registered run --subdir --check did not preserve scoped parsing in the sandbox" >&2
  echo "$RUN_SUBDIR_CHECK_OUTPUT" >&2
  exit 1
fi
if ! grep -q "def target():" "$REGISTERED_SUBDIR_REPO/src/app.py"; then
  echo "registered run --subdir --check mutated the selected target file" >&2
  exit 1
fi
if ! grep -q "def target():" "$REGISTERED_SUBDIR_REPO/tests/test_app.py"; then
  echo "registered run --subdir --check mutated the unselected target file" >&2
  exit 1
fi

TS_REPO="$SCRATCH/typescript-repo"
git init "$TS_REPO" >/dev/null
git -C "$TS_REPO" config user.email test@example.com
git -C "$TS_REPO" config user.name "Test User"
mkdir -p "$TS_REPO/src"
cat > "$TS_REPO/src/util.ts" <<'TS'
export function helper() {
  return 1;
}
TS
cat > "$TS_REPO/src/app.ts" <<'TS'
import { helper } from './util';

export function run() {
  return helper();
}
TS
git -C "$TS_REPO" add .
git -C "$TS_REPO" commit -m initial >/dev/null

TS_OUTPUT="$(run_graph_sitter parse "$TS_REPO" --language typescript --backend rust --fallback error --format json)"
run_python - "$TS_OUTPUT" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
assert payload["backend"] == "rust", payload
assert payload["backend_requested"] == "rust", payload
assert payload["language"] == "typescript", payload
assert payload["files"] == 2, payload
assert payload["symbols"] == 2, payload
assert payload["classes"] == 0, payload
assert payload["functions"] == 2, payload
assert payload["imports"] == 1, payload
assert payload["exports"] == 2, payload
assert payload["references"] == 1, payload
assert payload["dependencies"] == 1, payload
assert payload["files_with_errors"] == 0, payload
PY

TS_TRANSFORM="$SCRATCH/rename_ts_transform.py"
cat > "$TS_TRANSFORM" <<'PY'
def rename(codebase):
    function = codebase.get_function("run")
    function.rename("renamedRun")
    codebase.commit()
PY

set +e
TS_CHECK_OUTPUT="$(run_graph_sitter transform "${TS_TRANSFORM}:rename" "$TS_REPO" --language typescript --backend rust --fallback error --check 2>&1)"
TS_CHECK_STATUS=$?
set -e
if [[ "$TS_CHECK_STATUS" -ne 1 ]]; then
  echo "Expected TypeScript transform --check to exit 1 when changes would be produced; got $TS_CHECK_STATUS" >&2
  echo "$TS_CHECK_OUTPUT" >&2
  exit 1
fi
if [[ "$TS_CHECK_OUTPUT" != *"Codemod would produce changes"* ]]; then
  echo "Expected TypeScript transform --check output to mention produced changes" >&2
  echo "$TS_CHECK_OUTPUT" >&2
  exit 1
fi
if ! grep -q "export function run()" "$TS_REPO/src/app.ts"; then
  echo "TypeScript transform --check mutated the target repository" >&2
  exit 1
fi

TS_WRITE_OUTPUT="$(run_graph_sitter transform "${TS_TRANSFORM}:rename" "$TS_REPO" --language typescript --backend rust --fallback error --write)"
if [[ "$TS_WRITE_OUTPUT" != *"Changes have been applied"* ]]; then
  echo "Expected TypeScript transform --write output to mention applied changes" >&2
  echo "$TS_WRITE_OUTPUT" >&2
  exit 1
fi
if ! grep -q "export function renamedRun()" "$TS_REPO/src/app.ts"; then
  echo "TypeScript transform --write did not update the target repository" >&2
  exit 1
fi

print_message="wheel Rust backend Python/TypeScript parse, transform, and registered run smoke passed"
echo "$print_message"
