import json
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
            "global_variables": 0,
            "imports": 1,
            "import_resolutions": 1,
            "bytes": 64,
            "lines": 8,
            "files_with_errors": 0,
        }


class FakeIndex:
    def summary(self):
        return FakeSummary()

    def to_json(self):
        return '{"files":[],"symbols":[],"imports":[]}'

    def files_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "path": "pkg/service.py",
                    "module_name": "pkg.service",
                    "byte_len": 64,
                    "line_count": 8,
                    "has_error": False,
                    "root_range": {
                        "start_byte": 0,
                        "end_byte": 64,
                        "start_row": 0,
                        "start_column": 0,
                        "end_row": 8,
                        "end_column": 0,
                    },
                }
            ]
        )

    def symbols_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "file_id": 0,
                    "name": "Service",
                    "kind": "class",
                    "range": {
                        "start_byte": 11,
                        "end_byte": 31,
                        "start_row": 2,
                        "start_column": 0,
                        "end_row": 3,
                        "end_column": 8,
                    },
                    "name_range": {
                        "start_byte": 17,
                        "end_byte": 24,
                        "start_row": 2,
                        "start_column": 6,
                        "end_row": 2,
                        "end_column": 13,
                    },
                },
                {
                    "id": 1,
                    "file_id": 0,
                    "name": "helper",
                    "kind": "function",
                    "range": {
                        "start_byte": 33,
                        "end_byte": 64,
                        "start_row": 5,
                        "start_column": 0,
                        "end_row": 8,
                        "end_column": 0,
                    },
                    "name_range": {
                        "start_byte": 37,
                        "end_byte": 43,
                        "start_row": 5,
                        "start_column": 4,
                        "end_row": 5,
                        "end_column": 10,
                    },
                },
            ]
        )

    def imports_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "file_id": 0,
                    "kind": "import",
                    "module": None,
                    "name": "os",
                    "alias": None,
                    "range": {
                        "start_byte": 0,
                        "end_byte": 9,
                        "start_row": 0,
                        "start_column": 0,
                        "end_row": 0,
                        "end_column": 9,
                    },
                }
            ]
        )

    def import_resolutions_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "import_id": 0,
                    "source_file_id": 0,
                    "target_file_id": 0,
                    "target_symbol_id": 0,
                }
            ]
        )


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
        verify_input=False,
        verify_output=False,
    ) as codebase:
        assert codebase.ctx.rust_compact_mode is True
        assert codebase.ctx.rust_index is not None
        assert codebase.ctx.rust_index.engine_version == "test-rust-engine"
        assert codebase.ctx.rust_index.summary.files == 1
        assert codebase.ctx.rust_index.summary.classes == 1
        assert codebase.ctx.rust_index.summary.functions == 1
        assert codebase.ctx.rust_index.summary.global_variables == 0
        assert codebase.ctx.rust_index.summary.imports == 1
        assert codebase.ctx.rust_index.summary.import_resolutions == 1
        assert codebase.ctx.rust_index.files[0].path == "pkg/service.py"
        assert codebase.ctx.rust_index.symbols[0].name == "Service"
        assert codebase.ctx.rust_index.imports[0].name == "os"
        assert codebase.ctx.rust_index.import_resolutions[0].target_symbol_id == 0
        assert codebase.rust_index_summary == codebase.ctx.rust_index.summary
        assert codebase.rust_files[0].path == "pkg/service.py"
        assert codebase.rust_classes[0].name == "Service"
        assert codebase.rust_functions[0].name == "helper"
        assert codebase.rust_imports[0].name == "os"
        assert codebase.rust_import_resolutions[0].target_symbol_id == 0
        assert indexed_paths == [str(tmp_path.resolve())]
        assert selected_paths == [["pkg/service.py"]]

        assert len(codebase.files) == 1
        assert codebase.files[0].filepath == "pkg/service.py"
        assert codebase.files[0].content.startswith("import os")
        assert codebase.get_file("pkg/service.py") == codebase.files[0]
        assert codebase.has_file("PKG/SERVICE.PY", ignore_case=True)
        assert [symbol.name for symbol in codebase.symbols] == ["Service", "helper"]
        assert [symbol.name for symbol in codebase.classes] == ["Service"]
        assert [symbol.name for symbol in codebase.functions] == ["helper"]
        assert codebase.get_symbol("Service").source.startswith("class Service")
        assert codebase.get_class("Service").file == codebase.files[0]
        assert codebase.get_function("helper").filepath == "pkg/service.py"
        assert codebase.files[0].classes[0].name == "Service"
        assert codebase.files[0].functions[0].name == "helper"
        assert codebase.imports[0].source == "import os"
        assert codebase.imports[0].is_module_import()
        assert codebase.imports[0].from_file == codebase.files[0]
        assert codebase.imports[0].imported_symbol == codebase.classes[0]
        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


def test_missing_rust_extension_falls_back_to_python_graph(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "graph_sitter_py", None)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST, rust_fallback=RustFallbackMode.PYTHON)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={"app.py": "def run():\n    return 1\n"},
        config=config,
        verify_output=False,
    ) as codebase:
        assert codebase.ctx.rust_compact_mode is False
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
