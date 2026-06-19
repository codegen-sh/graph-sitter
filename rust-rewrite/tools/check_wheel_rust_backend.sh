#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON_VERSION="${PYTHON_VERSION:-3.13}"
rm -f dist/graph_sitter-*.whl
uv build --wheel

WHEEL="$(ls -t dist/graph_sitter-*.whl | head -n 1)"
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

uv run python - "$WHEEL" <<'PY'
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
uv run python - "$PYTHON_OUTPUT" <<'PY'
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
uv run python - "$OUTPUT" <<'PY'
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
CHECK_OUTPUT="$(run_graph_sitter transform "$TRANSFORM:rename" "$REPO" --language python --backend rust --fallback error --check 2>&1)"
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

WRITE_OUTPUT="$(run_graph_sitter transform "$TRANSFORM:rename" "$REPO" --language python --backend rust --fallback error --write)"
if [[ "$WRITE_OUTPUT" != *"Changes have been applied"* ]]; then
  echo "Expected transform --write output to mention applied changes" >&2
  echo "$WRITE_OUTPUT" >&2
  exit 1
fi
if ! grep -q "def renamed():" "$REPO/pkg/service.py"; then
  echo "transform --write did not update the target repository" >&2
  exit 1
fi

print_message="wheel Rust backend parse and transform smoke passed"
echo "$print_message"
