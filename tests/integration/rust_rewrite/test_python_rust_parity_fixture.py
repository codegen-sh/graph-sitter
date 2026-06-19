from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(
    os.environ.get("GRAPH_SITTER_RUN_RUST_PARITY_FIXTURE") != "1",
    reason="set GRAPH_SITTER_RUN_RUST_PARITY_FIXTURE=1 to run the Python/Rust parity fixture check",
)
def test_python_rust_parity_fixture() -> None:
    extra_args = shlex.split(os.environ.get("GRAPH_SITTER_RUST_PARITY_FIXTURE_ARGS", ""))
    command = [
        sys.executable,
        str(REPO_ROOT / "rust-rewrite/tools/check_python_rust_parity_fixture.py"),
        *extra_args,
    ]
    subprocess.run(command, cwd=REPO_ROOT, check=True)
