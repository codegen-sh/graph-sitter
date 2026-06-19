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

uv run python - "$WHEEL" <<'PY'
import sys
import zipfile

wheel = sys.argv[1]
with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    if not any(name.startswith("graph_sitter_py") and name.endswith((".so", ".pyd")) for name in names):
        msg = f"wheel does not include graph_sitter_py extension: {wheel}"
        raise AssertionError(msg)
PY

REPO="$(mktemp -d)"
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

OUTPUT="$(
  uvx \
    --no-cache \
    --refresh \
    --python "$PYTHON_VERSION" \
    --from "$WHEEL" \
    graph-sitter parse "$REPO" --language python --backend rust --fallback error --format json
)"
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
print("wheel Rust backend smoke passed")
PY
