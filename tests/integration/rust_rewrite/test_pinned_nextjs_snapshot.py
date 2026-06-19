from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(
    os.environ.get("GRAPH_SITTER_RUN_PINNED_NEXTJS_SNAPSHOT") != "1",
    reason="set GRAPH_SITTER_RUN_PINNED_NEXTJS_SNAPSHOT=1 to run the pinned Next.js Rust compact TypeScript snapshot check",
)
def test_pinned_nextjs_rust_compact_typescript_snapshot() -> None:
    extra_args = shlex.split(os.environ.get("GRAPH_SITTER_PINNED_NEXTJS_SNAPSHOT_ARGS", ""))
    command = [
        sys.executable,
        str(REPO_ROOT / "rust-rewrite/tools/snapshot_pinned_typescript_repo.py"),
        *extra_args,
    ]
    subprocess.run(command, cwd=REPO_ROOT, check=True)
