from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(
    os.environ.get("GRAPH_SITTER_RUN_PINNED_AIRFLOW_SNAPSHOT") != "1",
    reason="set GRAPH_SITTER_RUN_PINNED_AIRFLOW_SNAPSHOT=1 to run the pinned Airflow Rust compact snapshot check",
)
def test_pinned_airflow_rust_compact_snapshot() -> None:
    extra_args = shlex.split(os.environ.get("GRAPH_SITTER_PINNED_AIRFLOW_SNAPSHOT_ARGS", ""))
    command = [
        sys.executable,
        str(REPO_ROOT / "rust-rewrite/tools/snapshot_pinned_python_repo.py"),
        *extra_args,
    ]
    subprocess.run(command, cwd=REPO_ROOT, check=True)


@pytest.mark.skipif(
    os.environ.get("GRAPH_SITTER_RUN_PINNED_AIRFLOW_CODEBASE") != "1",
    reason="set GRAPH_SITTER_RUN_PINNED_AIRFLOW_CODEBASE=1 to run the pinned Airflow Rust Codebase compatibility/performance check",
)
def test_pinned_airflow_rust_codebase_python_handles() -> None:
    extra_args = shlex.split(os.environ.get("GRAPH_SITTER_PINNED_AIRFLOW_CODEBASE_ARGS", ""))
    command = [
        sys.executable,
        str(REPO_ROOT / "rust-rewrite/tools/check_pinned_python_codebase.py"),
        *extra_args,
    ]
    subprocess.run(command, cwd=REPO_ROOT, check=True)
