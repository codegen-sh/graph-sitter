from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(
    os.environ.get("GRAPH_SITTER_RUN_PINNED_CODEMODS") != "1",
    reason="set GRAPH_SITTER_RUN_PINNED_CODEMODS=1 to run the pinned large-repo Rust codemod proof",
)
def test_pinned_large_repo_rust_codemods() -> None:
    extra_args = shlex.split(os.environ.get("GRAPH_SITTER_PINNED_CODEMOD_ARGS", ""))
    command = [
        sys.executable,
        str(REPO_ROOT / "rust-rewrite/tools/check_pinned_codemods.py"),
        *extra_args,
    ]
    subprocess.run(command, cwd=REPO_ROOT, check=True)
