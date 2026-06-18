import sys
from types import ModuleType

import pytest

from graph_sitter.codebase.factory.get_session import get_codebase_session
from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode


class FakeSummary:
    def as_dict(self):
        return {
            "files": 1,
            "symbols": 2,
            "classes": 1,
            "functions": 1,
            "imports": 1,
            "bytes": 64,
            "lines": 8,
            "files_with_errors": 0,
        }


class FakeIndex:
    def summary(self):
        return FakeSummary()

    def to_json(self):
        return '{"files":[],"symbols":[],"imports":[]}'


def install_fake_rust_extension(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[list[str]]]:
    indexed_paths: list[str] = []
    selected_paths: list[list[str]] = []
    module = ModuleType("graph_sitter_py")
    module.engine_version = lambda: "test-rust-engine"

    def index_python_path(path: str):
        indexed_paths.append(path)
        return FakeIndex()

    def index_python_paths(path: str, file_paths: list[str]):
        indexed_paths.append(path)
        selected_paths.append(file_paths)
        return FakeIndex()

    module.index_python_path = index_python_path
    module.index_python_paths = index_python_paths
    monkeypatch.setitem(sys.modules, "graph_sitter_py", module)
    return indexed_paths, selected_paths


def test_codebase_context_builds_opt_in_rust_index(monkeypatch, tmp_path):
    indexed_paths, selected_paths = install_fake_rust_extension(monkeypatch)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={"pkg/service.py": "import os\n\nclass Service:\n    pass\n\ndef helper():\n    return os.getcwd()\n"},
        config=config,
        verify_output=False,
    ) as codebase:
        assert codebase.ctx.rust_index is not None
        assert codebase.ctx.rust_index.engine_version == "test-rust-engine"
        assert codebase.ctx.rust_index.summary.files == 1
        assert codebase.ctx.rust_index.summary.classes == 1
        assert codebase.ctx.rust_index.summary.functions == 1
        assert codebase.ctx.rust_index.summary.imports == 1
        assert codebase.rust_index_summary == codebase.ctx.rust_index.summary
        assert indexed_paths == [str(tmp_path.resolve())]
        assert selected_paths == [["pkg/service.py"]]


def test_missing_rust_extension_falls_back_to_python_graph(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "graph_sitter_py", None)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST, rust_fallback=RustFallbackMode.PYTHON)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={"app.py": "def run():\n    return 1\n"},
        config=config,
        verify_output=False,
    ) as codebase:
        assert codebase.ctx.rust_index is None
        assert codebase.rust_index_summary is None
        assert "graph_sitter_py" in codebase.ctx.rust_backend_error
        assert len(codebase.files) == 1
        assert len(codebase.functions) == 1


def test_missing_rust_extension_can_fail_strictly(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "graph_sitter_py", None)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST, rust_fallback=RustFallbackMode.ERROR)

    with pytest.raises(RuntimeError, match="graph_sitter_py"):
        with get_codebase_session(
            tmpdir=tmp_path,
            files={"app.py": "def run():\n    return 1\n"},
            config=config,
            verify_output=False,
        ):
            pass
