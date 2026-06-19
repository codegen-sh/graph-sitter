#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

CLI_FILES=(
  src/graph_sitter/cli/cli.py
  src/graph_sitter/cli/commands/parse/main.py
  src/graph_sitter/cli/commands/run/main.py
  src/graph_sitter/cli/commands/run/run_local.py
  src/graph_sitter/cli/commands/transform/main.py
  tests/unit/cli/commands/parse/test_parse.py
  tests/unit/cli/commands/run/test_run.py
  tests/unit/cli/commands/transform/test_transform.py
)

uv run ruff check "${CLI_FILES[@]}"
uv run python -m py_compile "${CLI_FILES[@]}"

uv run graph-sitter --help >/dev/null
uv run graph-sitter parse --help >/dev/null
uv run graph-sitter run --help >/dev/null
uv run graph-sitter transform --help >/dev/null

uv run pytest \
  tests/unit/cli/commands/parse/test_parse.py \
  tests/unit/cli/commands/run/test_run.py \
  tests/unit/cli/commands/transform/test_transform.py \
  -q
