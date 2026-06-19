#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

OUTPUT_DIR="${GRAPH_SITTER_PINNED_OUTPUT_DIR:-$ROOT/rust-rewrite/reports}"
CACHE_DIR="${GRAPH_SITTER_PINNED_CACHE_DIR:-/tmp/graph-sitter-pinned-repos}"
EXTENSION_DIR="${GRAPH_SITTER_PINNED_EXTENSION_DIR:-/tmp/graph_sitter_py_large_repo_checks}"
TIMEOUT="${GRAPH_SITTER_PINNED_TIMEOUT:-900}"

COMMON_ARGS=(
  --cache-dir "$CACHE_DIR"
  --extension-dir "$EXTENSION_DIR"
  --timeout "$TIMEOUT"
)
if [[ "${GRAPH_SITTER_PINNED_SKIP_FETCH:-0}" == "1" ]]; then
  COMMON_ARGS+=(--skip-fetch)
fi

AIRFLOW_SNAPSHOT_ARGS=("${COMMON_ARGS[@]}")
if [[ "${GRAPH_SITTER_PINNED_SKIP_BUILD_EXTENSION:-0}" == "1" ]]; then
  AIRFLOW_SNAPSHOT_ARGS+=(--skip-build-extension)
fi

mkdir -p "$OUTPUT_DIR"

echo "Checking pinned Airflow compact snapshot"
uv run python rust-rewrite/tools/snapshot_pinned_python_repo.py \
  "${AIRFLOW_SNAPSHOT_ARGS[@]}" \
  --output "$OUTPUT_DIR/airflow-rust-compact-snapshot.json"

echo "Checking pinned Airflow Rust Codebase proof"
uv run python rust-rewrite/tools/check_pinned_python_codebase.py \
  "${COMMON_ARGS[@]}" \
  --skip-build-extension \
  --output "$OUTPUT_DIR/airflow-rust-codebase.json"

echo "Checking pinned Next.js compact snapshot"
uv run python rust-rewrite/tools/snapshot_pinned_typescript_repo.py \
  "${COMMON_ARGS[@]}" \
  --skip-build-extension \
  --output "$OUTPUT_DIR/nextjs-rust-compact-snapshot.json"

echo "Checking pinned Next.js Rust Codebase proof"
uv run python rust-rewrite/tools/check_pinned_typescript_codebase.py \
  "${COMMON_ARGS[@]}" \
  --skip-build-extension \
  --output "$OUTPUT_DIR/nextjs-rust-codebase.json"

echo "Checking pinned large-repo Rust codemod proof"
uv run python rust-rewrite/tools/check_pinned_codemods.py \
  "${COMMON_ARGS[@]}" \
  --skip-build-extension \
  --output "$OUTPUT_DIR/pinned-rust-codemods.json"

echo "Pinned large-repo checks wrote reports to $OUTPUT_DIR"
