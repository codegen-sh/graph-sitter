import json
import sys
from types import ModuleType

import pytest

from codemods.codemod import Codemod
from graph_sitter.codebase.factory.get_session import get_codebase_session
from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode
from graph_sitter.core.dataclasses.usage import UsageKind, UsageType
from graph_sitter.enums import ImportType
from graph_sitter.shared.enums.programming_language import ProgrammingLanguage


def fake_range(start_byte: int, end_byte: int, start_row: int = 0, start_column: int = 0, end_row: int = 0, end_column: int = 0):
    return {
        "start_byte": start_byte,
        "end_byte": end_byte,
        "start_row": start_row,
        "start_column": start_column,
        "end_row": end_row,
        "end_column": end_column,
    }


class FakeSummary:
    def as_dict(self):
        return {
            "files": 1,
            "symbols": 3,
            "classes": 1,
            "functions": 2,
            "global_variables": 0,
            "imports": 2,
            "import_resolutions": 2,
            "references": 1,
            "dependencies": 1,
            "bytes": 127,
            "lines": 10,
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
                    "byte_len": 127,
                    "line_count": 10,
                    "has_error": False,
                    "root_range": {
                        "start_byte": 0,
                        "end_byte": 127,
                        "start_row": 0,
                        "start_column": 0,
                        "end_row": 9,
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
                    "parent_symbol_id": None,
                    "is_top_level": True,
                    "name": "Service",
                    "kind": "class",
                    "range": {
                        "start_byte": 30,
                        "end_byte": 91,
                        "start_row": 3,
                        "start_column": 0,
                        "end_row": 6,
                        "end_column": 0,
                    },
                    "name_range": {
                        "start_byte": 36,
                        "end_byte": 43,
                        "start_row": 3,
                        "start_column": 6,
                        "end_row": 3,
                        "end_column": 13,
                    },
                },
                {
                    "id": 1,
                    "file_id": 0,
                    "parent_symbol_id": 0,
                    "is_top_level": False,
                    "name": "run",
                    "kind": "function",
                    "range": {
                        "start_byte": 49,
                        "end_byte": 91,
                        "start_row": 4,
                        "start_column": 4,
                        "end_row": 6,
                        "end_column": 0,
                    },
                    "name_range": {
                        "start_byte": 53,
                        "end_byte": 56,
                        "start_row": 4,
                        "start_column": 8,
                        "end_row": 4,
                        "end_column": 11,
                    },
                },
                {
                    "id": 2,
                    "file_id": 0,
                    "parent_symbol_id": None,
                    "is_top_level": True,
                    "name": "helper",
                    "kind": "function",
                    "range": {
                        "start_byte": 92,
                        "end_byte": 127,
                        "start_row": 7,
                        "start_column": 0,
                        "end_row": 9,
                        "end_column": 0,
                    },
                    "name_range": {
                        "start_byte": 96,
                        "end_byte": 102,
                        "start_row": 7,
                        "start_column": 4,
                        "end_row": 7,
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
                },
                {
                    "id": 1,
                    "file_id": 0,
                    "kind": "import",
                    "module": None,
                    "name": "pkg.service",
                    "alias": None,
                    "range": {
                        "start_byte": 10,
                        "end_byte": 28,
                        "start_row": 1,
                        "start_column": 0,
                        "end_row": 1,
                        "end_column": 18,
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
                },
                {
                    "id": 1,
                    "import_id": 1,
                    "source_file_id": 0,
                    "target_file_id": 0,
                    "target_symbol_id": None,
                }
            ]
        )

    def references_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "source_file_id": 0,
                    "source_symbol_id": 2,
                    "target_symbol_id": 0,
                    "import_id": 0,
                    "name": "Service",
                    "range": {
                        "start_byte": 117,
                        "end_byte": 124,
                        "start_row": 8,
                        "start_column": 11,
                        "end_row": 8,
                        "end_column": 18,
                    },
                }
            ]
        )

    def dependencies_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "source_symbol_id": 2,
                    "target_symbol_id": 0,
                    "source_file_id": 0,
                    "target_file_id": 0,
                    "reference_ids": [0],
                    "reference_count": 1,
                }
            ]
        )


class FakeTypeScriptSummary(FakeSummary):
    def as_dict(self):
        data = super().as_dict()
        data.update(
            {
                "files": 2,
                "symbols": 4,
                "classes": 0,
                "functions": 2,
                "global_variables": 0,
                "imports": 1,
                "import_resolutions": 1,
                "references": 1,
                "dependencies": 1,
                "bytes": 198,
                "lines": 10,
            }
        )
        return data


class FakeTypeScriptIndex:
    def summary(self):
        return FakeTypeScriptSummary()

    def to_json(self):
        return '{"files":[],"symbols":[],"imports":[]}'

    def files_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "path": "src/app.ts",
                    "module_name": None,
                    "byte_len": 141,
                    "line_count": 7,
                    "has_error": False,
                    "root_range": fake_range(0, 141, 0, 0, 7, 0),
                },
                {
                    "id": 1,
                    "path": "src/util.ts",
                    "module_name": None,
                    "byte_len": 57,
                    "line_count": 3,
                    "has_error": False,
                    "root_range": fake_range(0, 57, 0, 0, 3, 0),
                },
            ]
        )

    def symbols_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "file_id": 0,
                    "parent_symbol_id": None,
                    "is_top_level": True,
                    "name": "Props",
                    "kind": "interface",
                    "range": fake_range(35, 68, 2, 0, 2, 33),
                    "name_range": fake_range(45, 50, 2, 10, 2, 15),
                },
                {
                    "id": 1,
                    "file_id": 0,
                    "parent_symbol_id": None,
                    "is_top_level": True,
                    "name": "Mode",
                    "kind": "type_alias",
                    "range": fake_range(69, 86, 3, 0, 3, 17),
                    "name_range": fake_range(74, 78, 3, 5, 3, 9),
                },
                {
                    "id": 2,
                    "file_id": 0,
                    "parent_symbol_id": None,
                    "is_top_level": True,
                    "name": "run",
                    "kind": "function",
                    "range": fake_range(87, 141, 4, 0, 6, 1),
                    "name_range": fake_range(103, 106, 4, 16, 4, 19),
                },
                {
                    "id": 3,
                    "file_id": 1,
                    "parent_symbol_id": None,
                    "is_top_level": True,
                    "name": "helper",
                    "kind": "function",
                    "range": fake_range(0, 57, 0, 0, 2, 1),
                    "name_range": fake_range(16, 22, 0, 16, 0, 22),
                },
            ]
        )

    def imports_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "file_id": 0,
                    "kind": "named_import",
                    "module": "./util",
                    "name": "helper",
                    "alias": "helper",
                    "range": fake_range(9, 15, 0, 9, 0, 15),
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
                    "target_file_id": 1,
                    "target_symbol_id": 3,
                }
            ]
        )

    def exports_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "file_id": 0,
                    "kind": "named",
                    "name": "run",
                    "local_name": "run",
                    "source_module": None,
                    "symbol_id": 2,
                    "import_id": None,
                    "range": fake_range(87, 141, 4, 0, 6, 1),
                },
                {
                    "id": 1,
                    "file_id": 1,
                    "kind": "named",
                    "name": "helper",
                    "local_name": "helper",
                    "source_module": None,
                    "symbol_id": 3,
                    "import_id": None,
                    "range": fake_range(0, 57, 0, 0, 2, 1),
                },
            ]
        )

    def references_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "source_file_id": 0,
                    "source_symbol_id": 2,
                    "target_symbol_id": 3,
                    "import_id": 0,
                    "name": "helper",
                    "range": fake_range(119, 125, 5, 9, 5, 15),
                }
            ]
        )

    def dependencies_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "source_symbol_id": 2,
                    "target_symbol_id": 3,
                    "source_file_id": 0,
                    "target_file_id": 1,
                    "reference_ids": [0],
                    "reference_count": 1,
                }
            ]
        )


class FakeDecoratedIndex(FakeIndex):
    def summary(self):
        return FakeDecoratedSummary()

    def files_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "path": "pkg/service.py",
                    "module_name": "pkg.service",
                    "byte_len": 132,
                    "line_count": 10,
                    "has_error": False,
                    "root_range": {
                        "start_byte": 0,
                        "end_byte": 132,
                        "start_row": 0,
                        "start_column": 0,
                        "end_row": 10,
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
                    "parent_symbol_id": None,
                    "is_top_level": True,
                    "name": "Service",
                    "kind": "class",
                    "range": {
                        "start_byte": 30,
                        "end_byte": 96,
                        "start_row": 3,
                        "start_column": 0,
                        "end_row": 7,
                        "end_column": 0,
                    },
                    "name_range": {
                        "start_byte": 41,
                        "end_byte": 48,
                        "start_row": 4,
                        "start_column": 6,
                        "end_row": 4,
                        "end_column": 13,
                    },
                },
                {
                    "id": 1,
                    "file_id": 0,
                    "parent_symbol_id": 0,
                    "is_top_level": False,
                    "name": "run",
                    "kind": "function",
                    "range": {
                        "start_byte": 50,
                        "end_byte": 96,
                        "start_row": 5,
                        "start_column": 4,
                        "end_row": 7,
                        "end_column": 0,
                    },
                    "name_range": {
                        "start_byte": 58,
                        "end_byte": 61,
                        "start_row": 5,
                        "start_column": 8,
                        "end_row": 5,
                        "end_column": 11,
                    },
                },
                {
                    "id": 2,
                    "file_id": 0,
                    "parent_symbol_id": None,
                    "is_top_level": True,
                    "name": "helper",
                    "kind": "function",
                    "range": {
                        "start_byte": 97,
                        "end_byte": 132,
                        "start_row": 8,
                        "start_column": 0,
                        "end_row": 10,
                        "end_column": 0,
                    },
                    "name_range": {
                        "start_byte": 101,
                        "end_byte": 107,
                        "start_row": 8,
                        "start_column": 4,
                        "end_row": 8,
                        "end_column": 10,
                    },
                },
            ]
        )

    def references_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "source_file_id": 0,
                    "source_symbol_id": 2,
                    "target_symbol_id": 0,
                    "import_id": 0,
                    "name": "Service",
                    "range": {
                        "start_byte": 122,
                        "end_byte": 129,
                        "start_row": 9,
                        "start_column": 11,
                        "end_row": 9,
                        "end_column": 18,
                    },
                }
            ]
        )


class FakeDecoratedSummary(FakeSummary):
    def as_dict(self):
        data = super().as_dict()
        data.update({"bytes": 132, "lines": 10})
        return data


class FakeMoveUpdateIndex(FakeIndex):
    def summary(self):
        return FakeMoveUpdateSummary()

    def files_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "path": "pkg/service.py",
                    "module_name": "pkg.service",
                    "byte_len": 24,
                    "line_count": 2,
                    "has_error": False,
                    "root_range": {
                        "start_byte": 0,
                        "end_byte": 24,
                        "start_row": 0,
                        "start_column": 0,
                        "end_row": 2,
                        "end_column": 0,
                    },
                },
                {
                    "id": 1,
                    "path": "pkg/consumer.py",
                    "module_name": "pkg.consumer",
                    "byte_len": 65,
                    "line_count": 4,
                    "has_error": False,
                    "root_range": {
                        "start_byte": 0,
                        "end_byte": 65,
                        "start_row": 0,
                        "start_column": 0,
                        "end_row": 4,
                        "end_column": 0,
                    },
                },
            ]
        )

    def symbols_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "file_id": 0,
                    "parent_symbol_id": None,
                    "is_top_level": True,
                    "name": "Service",
                    "kind": "class",
                    "range": {
                        "start_byte": 0,
                        "end_byte": 24,
                        "start_row": 0,
                        "start_column": 0,
                        "end_row": 2,
                        "end_column": 0,
                    },
                    "name_range": {
                        "start_byte": 6,
                        "end_byte": 13,
                        "start_row": 0,
                        "start_column": 6,
                        "end_row": 0,
                        "end_column": 13,
                    },
                },
                {
                    "id": 1,
                    "file_id": 1,
                    "parent_symbol_id": None,
                    "is_top_level": True,
                    "name": "use",
                    "kind": "function",
                    "range": {
                        "start_byte": 33,
                        "end_byte": 65,
                        "start_row": 2,
                        "start_column": 0,
                        "end_row": 4,
                        "end_column": 0,
                    },
                    "name_range": {
                        "start_byte": 37,
                        "end_byte": 40,
                        "start_row": 2,
                        "start_column": 4,
                        "end_row": 2,
                        "end_column": 7,
                    },
                },
            ]
        )

    def imports_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "file_id": 1,
                    "kind": "from",
                    "module": "pkg.service",
                    "name": "Service",
                    "alias": None,
                    "range": {
                        "start_byte": 0,
                        "end_byte": 31,
                        "start_row": 0,
                        "start_column": 0,
                        "end_row": 0,
                        "end_column": 31,
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
                    "source_file_id": 1,
                    "target_file_id": 0,
                    "target_symbol_id": 0,
                }
            ]
        )

    def references_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "source_file_id": 1,
                    "source_symbol_id": 1,
                    "target_symbol_id": 0,
                    "import_id": 0,
                    "name": "Service",
                    "range": {
                        "start_byte": 55,
                        "end_byte": 62,
                        "start_row": 3,
                        "start_column": 11,
                        "end_row": 3,
                        "end_column": 18,
                    },
                }
            ]
        )

    def dependencies_json(self):
        return json.dumps(
            [
                {
                    "id": 0,
                    "source_symbol_id": 1,
                    "target_symbol_id": 0,
                    "source_file_id": 1,
                    "target_file_id": 0,
                    "reference_ids": [0],
                    "reference_count": 1,
                }
            ]
        )


class FakeMoveUpdateSummary(FakeSummary):
    def as_dict(self):
        data = super().as_dict()
        data.update(
            {
                "files": 2,
                "symbols": 2,
                "classes": 1,
                "functions": 1,
                "imports": 1,
                "import_resolutions": 1,
                "bytes": 89,
                "lines": 6,
            }
        )
        return data


def install_fake_rust_extension(monkeypatch: pytest.MonkeyPatch, index_cls=FakeIndex, typescript_index_cls=FakeTypeScriptIndex) -> tuple[list[str], list[list[str]]]:
    indexed_paths: list[str] = []
    selected_paths: list[list[str]] = []
    module = ModuleType("graph_sitter_py")
    module.engine_version = lambda: "test-rust-engine"

    def index_python_path(path: str):
        indexed_paths.append(path)
        return index_cls()

    def index_python_paths(path: str, file_paths: list[str]):
        indexed_paths.append(path)
        selected_paths.append(file_paths)
        return index_cls()

    def index_typescript_path(path: str):
        indexed_paths.append(path)
        return typescript_index_cls()

    def index_typescript_paths(path: str, file_paths: list[str]):
        indexed_paths.append(path)
        selected_paths.append(file_paths)
        return typescript_index_cls()

    module.index_python_path = index_python_path
    module.index_python_paths = index_python_paths
    module.index_typescript_path = index_typescript_path
    module.index_typescript_paths = index_typescript_paths
    monkeypatch.setitem(sys.modules, "graph_sitter_py", module)
    return indexed_paths, selected_paths


def test_codebase_context_builds_opt_in_rust_index(monkeypatch, tmp_path):
    indexed_paths, selected_paths = install_fake_rust_extension(monkeypatch)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={"pkg/service.py": "import os\nimport pkg.service\n\nclass Service:\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Service()\n"},
        config=config,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        assert codebase.ctx.rust_compact_mode is True
        assert codebase.ctx.rust_index is not None
        assert codebase.ctx.rust_index.engine_version == "test-rust-engine"
        assert codebase.ctx.rust_index.summary.files == 1
        assert codebase.ctx.rust_index.summary.classes == 1
        assert codebase.ctx.rust_index.summary.functions == 2
        assert codebase.ctx.rust_index.summary.global_variables == 0
        assert codebase.ctx.rust_index.summary.imports == 2
        assert codebase.ctx.rust_index.summary.import_resolutions == 2
        assert codebase.ctx.rust_index.summary.references == 1
        assert codebase.ctx.rust_index.summary.dependencies == 1
        assert codebase.ctx.rust_index.files[0].path == "pkg/service.py"
        assert codebase.ctx.rust_index.symbols[0].name == "Service"
        assert codebase.ctx.rust_index.imports[0].name == "os"
        assert codebase.ctx.rust_index.import_resolutions[0].target_symbol_id == 0
        assert codebase.ctx.rust_index.references[0].target_symbol_id == 0
        assert codebase.ctx.rust_index.dependencies[0].target_symbol_id == 0
        assert codebase.rust_index_summary == codebase.ctx.rust_index.summary
        assert codebase.rust_files[0].path == "pkg/service.py"
        assert codebase.rust_classes[0].name == "Service"
        assert [symbol.name for symbol in codebase.rust_functions] == ["run", "helper"]
        assert codebase.rust_imports[0].name == "os"
        assert codebase.rust_imports[1].name == "pkg.service"
        assert codebase.rust_import_resolutions[0].target_symbol_id == 0
        assert codebase.rust_import_resolutions[1].target_symbol_id is None
        assert codebase.rust_references[0].name == "Service"
        assert codebase.rust_dependencies[0].reference_ids == [0]
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
        assert [import_handle.name for import_handle in codebase.imports] == ["os", "pkg.service"]
        assert codebase.get_symbol("Service").source.startswith("class Service")
        assert codebase.get_class("Service").file == codebase.files[0]
        assert codebase.get_function("helper").filepath == "pkg/service.py"
        assert codebase.files[0].classes[0].name == "Service"
        assert codebase.files[0].functions[0].name == "helper"
        assert [symbol.name for symbol in codebase.files[0].symbols_sorted_topologically] == ["helper", "Service"]
        assert [symbol.name for symbol in codebase.files[0].symbols(nested=True)] == ["Service", "run", "helper"]
        assert codebase.files[0].import_statements == [codebase.imports[0], codebase.imports[1]]
        assert codebase.files[0].get_nodes() == [codebase.imports[0], codebase.imports[1], codebase.classes[0], codebase.files[0].symbols(nested=True)[1], codebase.functions[0]]
        assert codebase.files[0].descendant_symbols == codebase.files[0].get_nodes()
        assert codebase.files[0].find_by_byte_range(codebase.rust_imports[0].range) == [codebase.imports[0]]
        assert codebase.files[0].find_by_byte_range(codebase.rust_imports[1].range) == [codebase.imports[1]]
        assert codebase.files[0].find_by_byte_range(codebase.rust_symbols[0].range) == [codebase.classes[0], codebase.files[0].symbols(nested=True)[1]]
        assert codebase.files[0].find_by_byte_range(codebase.rust_references[0].range) == [codebase.functions[0]]
        assert codebase.files[0].find_by_byte_range({"start_byte": 28, "end_byte": 30}) == []
        assert codebase.files[0].valid_symbol_names["Service"] == codebase.classes[0]
        assert codebase.files[0].valid_symbol_names["os"] == codebase.imports[0]
        assert codebase.files[0].valid_symbol_names["pkg.service"] == codebase.imports[1]
        assert codebase.files[0].valid_import_names["Service"] == codebase.classes[0]
        assert codebase.files[0].resolve_attribute("Service") == codebase.classes[0]
        assert codebase.files[0].resolve_attribute("os") == codebase.imports[0]
        assert list(codebase.files[0].resolve_name("Service")) == [codebase.classes[0]]
        assert list(codebase.files[0].resolve_name("Service", start_byte=40)) == [codebase.classes[0]]
        assert list(codebase.files[0].resolve_name("helper", start_byte=40)) == []
        assert codebase.files[0].get_node_by_name("Service") == codebase.classes[0]
        assert codebase.files[0].get_node_by_name("os") == codebase.imports[0]
        assert codebase.files[0].import_module_name == "pkg.service"
        assert codebase.files[0].get_import_module_name_for_file("pkg/__init__.py", codebase.ctx) == "pkg"
        assert codebase.files[0].get_import_string() == "from pkg import service"
        assert codebase.files[0].get_import_string(alias="svc") == "from pkg import service as svc"
        assert codebase.files[0].get_import_string(import_type=ImportType.WILDCARD) == "from pkg import * as service"
        assert codebase.files[0].has_import("os")
        assert codebase.files[0].has_import("import os")
        assert codebase.files[0].get_import("os") == codebase.imports[0]
        assert codebase.files[0].get_import("import os") == codebase.imports[0]
        assert codebase.files[0].get_import("missing") is None
        assert codebase.imports[0].source == "import os"
        assert codebase.imports[1].source == "import pkg.service"
        assert codebase.imports[0].get_name().source == "os"
        assert codebase.imports[0].get_name()._source == "os"
        assert codebase.imports[1].get_name().source == "pkg.service"
        assert codebase.imports[0].is_module_import()
        assert codebase.imports[0].from_file == codebase.files[0]
        assert codebase.imports[0].imported_symbol == codebase.classes[0]
        assert codebase.files[0].inbound_imports == [codebase.imports[0], codebase.imports[1]]
        assert codebase.files[0].importers == [codebase.imports[1]]
        helper = codebase.get_function("helper")
        service = codebase.get_class("Service")
        run = codebase.files[0].symbols(nested=True)[1]
        import_handle = codebase.imports[0]
        module_import = codebase.imports[1]
        assert run.name == "run"
        assert run.full_name == "Service.run"
        assert run.is_exported
        assert service.full_name == "Service"
        assert service.is_exported
        assert run.parent_symbol == service
        assert service.parent_symbol == service
        assert [symbol.name for symbol in service.child_symbols] == ["run"]
        assert [symbol.name for symbol in service.descendant_symbols] == ["Service", "run"]
        assert helper.descendant_symbols == [helper]
        assert service.get_import_string() == "from pkg.service import Service"
        assert service.get_import_string(alias="Svc") == "from pkg.service import Service as Svc"
        assert service.get_import_string(import_type=ImportType.WILDCARD) == "from pkg.service import * as service"
        assert import_handle.get_import_string() == "from pkg.service import os"
        assert import_handle.get_import_string(alias="operating_system") == "from pkg.service import os as operating_system"
        assert import_handle.descendant_symbols == [import_handle]
        assert import_handle.imported_exports == [service]
        assert module_import.imported_symbol == codebase.files[0]
        assert module_import.imported_exports == [service, helper, import_handle, module_import]
        assert module_import.resolve_attribute("Service") == service
        assert module_import.resolve_attribute("helper") == helper
        assert module_import.resolve_attribute("os") == import_handle
        assert module_import.resolve_attribute("missing") is None
        assert service.get_name().source == "Service"
        assert service.get_name()._source == "Service"
        assert service.get_name().name == "Service"
        assert service.get_name().full_name == "Service"
        assert run.get_name().source == "run"
        assert helper.dependencies == [service]
        assert helper.dependencies(usage_types=UsageType.CHAINED) == []
        assert helper.dependencies(max_depth=2) == [service]
        assert helper.symbol_usages == []
        assert service.symbol_usages == [helper]
        assert service.symbol_usages(UsageType.DIRECT | UsageType.CHAINED) == [helper]
        assert len(service.usages) == 1
        assert service.usages[0].usage_symbol == helper
        assert service.usages[0].imported_by == codebase.imports[0]
        assert service.usages[0].usage_type == UsageType.DIRECT
        assert service.usages[0].kind == UsageKind.BODY
        assert service.usages[0].match.source == "Service"
        assert service.usages[0].match.file == codebase.files[0]
        assert service.usages[0].match.start_point == (8, 11)
        assert import_handle.symbol_usages == [helper]
        assert import_handle.symbol_usages(UsageType.CHAINED) == []
        assert len(import_handle.usages) == 1
        assert import_handle.usages[0].usage_symbol == helper
        assert import_handle.usages[0].imported_by == import_handle
        assert import_handle.usages[0].match.source == "Service"
        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


def test_codebase_context_builds_opt_in_typescript_rust_index(monkeypatch, tmp_path):
    indexed_paths, selected_paths = install_fake_rust_extension(monkeypatch)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)
    files = {
        "src/app.ts": "import { helper } from './util';\n\ninterface Props { value: number }\ntype Mode = 'a';\nexport function run(props: Props) {\n  return helper(props.value);\n}\n",
        "src/util.ts": "export function helper(value: number) {\n  return value;\n}\n",
    }

    with get_codebase_session(
        tmpdir=tmp_path,
        programming_language=ProgrammingLanguage.TYPESCRIPT,
        files=files,
        config=config,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        assert codebase.ctx.rust_compact_mode is True
        assert codebase.ctx.rust_index is not None
        assert codebase.ctx.rust_index.summary.files == 2
        assert codebase.ctx.rust_index.summary.functions == 2
        assert codebase.ctx.rust_index.summary.imports == 1
        assert codebase.ctx.rust_index.summary.import_resolutions == 1
        assert codebase.ctx.rust_index.summary.references == 1
        assert codebase.ctx.rust_index.summary.dependencies == 1
        assert [export.name for export in codebase.rust_exports] == ["run", "helper"]
        assert [file.path for file in codebase.rust_files] == ["src/app.ts", "src/util.ts"]
        assert [symbol.name for symbol in codebase.rust_symbols] == ["Props", "Mode", "run", "helper"]
        assert codebase.rust_imports[0].module == "./util"
        assert codebase.rust_import_resolutions[0].target_symbol_id == 3
        assert codebase.rust_references[0].name == "helper"
        assert codebase.rust_dependencies[0].target_symbol_id == 3

        assert [file.filepath for file in codebase.files] == ["src/app.ts", "src/util.ts"]
        assert [symbol.name for symbol in codebase.symbols] == ["Props", "Mode", "run", "helper"]
        assert [function.name for function in codebase.functions] == ["helper", "run"]
        assert [interface.name for interface in codebase.interfaces] == ["Props"]
        assert [type_alias.name for type_alias in codebase.types] == ["Mode"]
        assert codebase.imports[0].name == "helper"
        assert [export.name for export in codebase.exports] == ["run", "helper"]

        run = codebase.get_function("run")
        helper = codebase.get_function("helper")
        assert run is not None
        assert helper is not None
        assert run.dependencies == [helper]
        assert helper.usages[0].match.source == "helper"

        app_file = codebase.get_file("src/app.ts")
        util_file = codebase.get_file("src/util.ts")
        run_export = app_file.get_export("run")
        helper_export = util_file.get_export("helper")
        assert run_export is not None
        assert helper_export is not None
        assert app_file.exports == [run_export]
        assert util_file.exports == [helper_export]
        assert app_file.named_exports == [run_export]
        assert app_file.default_exports == []
        assert app_file.export_statements == [run_export]
        assert run_export.exported_symbol == run
        assert run_export.resolved_symbol == run
        assert run_export.declared_symbol == run
        assert run_export.exported_name == "run"
        assert run_export.local_name == "run"
        assert run_export.is_named_export()
        assert not run_export.is_default_export()
        assert not run_export.is_reexport()
        assert not run_export.is_wildcard_export()
        assert not run_export.is_module_export()
        assert not run_export.is_external_export
        assert run_export.get_name().source == "run"
        assert list(run_export.names) == [("run", run_export)]
        assert run_export.descendant_symbols == [run_export, run]
        assert run_export.get_import_string() == "import { run } from 'src/app';"
        assert run_export.get_import_string(alias="execute") == "import { run as execute } from 'src/app';"
        assert helper_export.exported_symbol == helper
        assert helper_export.resolved_symbol == helper

        assert indexed_paths == [str(tmp_path.resolve())]
        assert selected_paths == [["src/app.ts", "src/util.ts"]]
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


def test_rust_compact_file_mutations_commit_without_python_graph(monkeypatch, tmp_path):
    install_fake_rust_extension(monkeypatch)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={"pkg/service.py": "import os\nimport pkg.service\n\nclass Service:\n    pass\n"},
        config=config,
        sync_graph=False,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        service_file = codebase.get_file("pkg/service.py")
        service_file.edit("VALUE = 1\n")
        codebase.commit(sync_graph=False)
        assert service_file.content == "VALUE = 1\n"
        assert (tmp_path / "pkg/service.py").read_text() == "VALUE = 1\n"

        assert service_file.replace("VALUE", "UPDATED") == 1
        codebase.commit(sync_graph=False)
        assert service_file.content == "UPDATED = 1\n"

        created_file = codebase.create_file("pkg/generated.py", "CREATED = True\n", sync=False)
        assert created_file.filepath == "pkg/generated.py"
        assert codebase.has_file("pkg/generated.py")
        assert codebase.get_file("pkg/generated.py") == created_file
        assert (tmp_path / "pkg/generated.py").read_text() == "CREATED = True\n"

        created_file.edit("CREATED = False\n")
        codebase.commit(sync_graph=False)
        assert (tmp_path / "pkg/generated.py").read_text() == "CREATED = False\n"

        created_file.remove()
        codebase.commit(sync_graph=False)
        assert not (tmp_path / "pkg/generated.py").exists()
        assert codebase.get_file("pkg/generated.py", optional=True) is None

        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


def test_rust_compact_symbol_rename_and_add_import_commit_without_python_graph(monkeypatch, tmp_path):
    install_fake_rust_extension(monkeypatch)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={
            "pkg/service.py": "import os\nimport pkg.service\n\nclass Service:\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Service()\n"
        },
        config=config,
        sync_graph=False,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        service_file = codebase.get_file("pkg/service.py")
        service = codebase.get_class("Service")

        assert service_file.add_import("from typing import Any") is None
        assert service_file.add_import("from typing import Any") is None
        service.rename("Worker")
        codebase.commit(sync_graph=False)

        expected = "from typing import Any\nimport os\nimport pkg.service\n\nclass Worker:\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Worker()\n"
        assert (tmp_path / "pkg/service.py").read_text() == expected
        assert service_file.content == expected
        assert service.name == "Worker"
        assert service.get_name().source == "Worker"

        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


def test_rust_compact_add_import_from_symbol_commit_without_python_graph(monkeypatch, tmp_path):
    install_fake_rust_extension(monkeypatch)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={"pkg/service.py": "import os\nimport pkg.service\n\nclass Service:\n    pass\n"},
        config=config,
        sync_graph=False,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        service = codebase.get_class("Service")
        consumer_file = codebase.create_file("pkg/consumer.py", "def use():\n    return Svc()\n", sync=False)

        assert consumer_file.add_import(service, alias="Svc") is None
        assert consumer_file.add_import(service, alias="Svc") is None
        codebase.commit(sync_graph=False)

        expected = "from pkg.service import Service as Svc\ndef use():\n    return Svc()\n"
        assert (tmp_path / "pkg/consumer.py").read_text() == expected
        assert consumer_file.content == expected

        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


def test_rust_compact_symbol_and_import_remove_commit_without_python_graph(monkeypatch, tmp_path):
    install_fake_rust_extension(monkeypatch)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={
            "pkg/service.py": "import os\nimport pkg.service\n\nclass Service:\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Service()\n"
        },
        config=config,
        sync_graph=False,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        service_file = codebase.get_file("pkg/service.py")
        codebase.imports[0].remove()
        codebase.get_function("helper").remove()
        codebase.commit(sync_graph=False)

        expected = "import pkg.service\n\nclass Service:\n    def run(self):\n        return os.getcwd()\n\n"
        assert (tmp_path / "pkg/service.py").read_text() == expected
        assert service_file.content == expected

        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


def test_rust_compact_add_decorator_commit_without_python_graph(monkeypatch, tmp_path):
    install_fake_rust_extension(monkeypatch)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={
            "pkg/service.py": "import os\nimport pkg.service\n\nclass Service:\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Service()\n"
        },
        config=config,
        sync_graph=False,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        service = codebase.get_class("Service")
        run = service.get_method("run")

        assert not service.is_decorated
        assert service.decorators == []
        assert service.add_decorator("@dataclass")
        assert not service.add_decorator("@dataclass", skip_if_exists=True)
        assert run.add_decorator("@classmethod")
        codebase.commit(sync_graph=False)

        expected = "import os\nimport pkg.service\n\n@dataclass\nclass Service:\n    @classmethod\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Service()\n"
        assert (tmp_path / "pkg/service.py").read_text() == expected
        assert service.file.content == expected

        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


def test_rust_compact_decorator_read_and_remove_commit_without_python_graph(monkeypatch, tmp_path):
    install_fake_rust_extension(monkeypatch, index_cls=FakeDecoratedIndex)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={
            "pkg/service.py": "import os\nimport pkg.service\n\n@old\nclass Service:\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Service()\n"
        },
        config=config,
        sync_graph=False,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        service = codebase.get_class("Service")

        assert service.is_decorated
        assert [decorator.source for decorator in service.decorators] == ["@old"]
        assert service.decorators[0].name == "old"
        assert service.decorators[0].full_name == "old"
        service.decorators[0].remove()
        codebase.commit(sync_graph=False)

        expected = "import os\nimport pkg.service\n\nclass Service:\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Service()\n"
        assert (tmp_path / "pkg/service.py").read_text() == expected
        assert service.file.content == expected

        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


def test_rust_compact_move_function_to_created_file_commit_without_python_graph(monkeypatch, tmp_path):
    install_fake_rust_extension(monkeypatch)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={
            "pkg/service.py": "import os\nimport pkg.service\n\nclass Service:\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Service()\n"
        },
        config=config,
        sync_graph=False,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        helper = codebase.get_function("helper")
        helpers_file = codebase.create_file("pkg/helpers.py", "", sync=False)

        helper.move_to_file(helpers_file, include_dependencies=False, strategy="add_back_edge")
        codebase.commit(sync_graph=False)

        expected_source = "import os\nimport pkg.service\n\nclass Service:\n    def run(self):\n        return os.getcwd()\n\n"
        expected_target = "from pkg.service import Service\ndef helper():\n    return Service()\n"
        assert (tmp_path / "pkg/service.py").read_text() == expected_source
        assert (tmp_path / "pkg/helpers.py").read_text() == expected_target

        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


def test_rust_compact_move_class_adds_back_edge_commit_without_python_graph(monkeypatch, tmp_path):
    install_fake_rust_extension(monkeypatch)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={
            "pkg/service.py": "import os\nimport pkg.service\n\nclass Service:\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Service()\n"
        },
        config=config,
        sync_graph=False,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        service = codebase.get_class("Service")
        models_file = codebase.create_file("pkg/models.py", "", sync=False)

        service.move_to_file(models_file, include_dependencies=False, strategy="add_back_edge")
        codebase.commit(sync_graph=False)

        expected_source = "from pkg.models import Service\nimport os\nimport pkg.service\n\n\ndef helper():\n    return Service()\n"
        expected_target = "class Service:\n    def run(self):\n        return os.getcwd()\n"
        assert (tmp_path / "pkg/service.py").read_text() == expected_source
        assert (tmp_path / "pkg/models.py").read_text() == expected_target

        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


def test_rust_compact_move_updates_imported_usages_commit_without_python_graph(monkeypatch, tmp_path):
    install_fake_rust_extension(monkeypatch, index_cls=FakeMoveUpdateIndex)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={
            "pkg/service.py": "class Service:\n    pass\n",
            "pkg/consumer.py": "from pkg.service import Service\n\ndef use():\n    return Service()\n",
        },
        config=config,
        sync_graph=False,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        service = codebase.get_class("Service")
        models_file = codebase.create_file("pkg/models.py", "", sync=False)

        service.move_to_file(models_file, include_dependencies=False, strategy="update_all_imports")
        codebase.commit(sync_graph=False)

        expected_consumer = "from pkg.models import Service\n\ndef use():\n    return Service()\n"
        assert (tmp_path / "pkg/service.py").read_text() == ""
        assert (tmp_path / "pkg/models.py").read_text() == "class Service:\n    pass\n"
        assert (tmp_path / "pkg/consumer.py").read_text() == expected_consumer

        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


def test_rust_compact_codemod_execute_symbol_import_edits_without_python_graph(monkeypatch, tmp_path):
    install_fake_rust_extension(monkeypatch)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    def execute(codebase):
        service_file = codebase.get_file("pkg/service.py")
        service_file.add_import("from typing import Any")
        codebase.imports[0].remove()
        codebase.get_class("Service").rename("Worker")

    codemod = Codemod(name="rust-symbol-import-smoke", execute=execute)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={
            "pkg/service.py": "import os\nimport pkg.service\n\nclass Service:\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Service()\n"
        },
        config=config,
        sync_graph=False,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        codemod.execute(codebase)
        codebase.commit(sync_graph=False)

        expected = "from typing import Any\nimport pkg.service\n\nclass Worker:\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Worker()\n"
        assert (tmp_path / "pkg/service.py").read_text() == expected
        assert codebase.get_file("pkg/service.py").content == expected

        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


def test_rust_compact_codemod_execute_move_updates_imports_without_python_graph(monkeypatch, tmp_path):
    install_fake_rust_extension(monkeypatch, index_cls=FakeMoveUpdateIndex)
    config = CodebaseConfig(graph_backend=GraphBackend.RUST)

    def execute(codebase):
        service = codebase.get_class("Service")
        models_file = codebase.create_file("pkg/models.py", "", sync=False)
        service.move_to_file(models_file, include_dependencies=False, strategy="update_all_imports")

    codemod = Codemod(name="rust-move-update-imports-smoke", execute=execute)

    with get_codebase_session(
        tmpdir=tmp_path,
        files={
            "pkg/service.py": "class Service:\n    pass\n",
            "pkg/consumer.py": "from pkg.service import Service\n\ndef use():\n    return Service()\n",
        },
        config=config,
        sync_graph=False,
        verify_input=False,
        verify_output=False,
    ) as codebase:
        codemod.execute(codebase)
        codebase.commit(sync_graph=False)

        expected_consumer = "from pkg.models import Service\n\ndef use():\n    return Service()\n"
        assert (tmp_path / "pkg/service.py").read_text() == ""
        assert (tmp_path / "pkg/models.py").read_text() == "class Service:\n    pass\n"
        assert (tmp_path / "pkg/consumer.py").read_text() == expected_consumer

        with pytest.raises(RuntimeError, match="Python graph is not built"):
            len(codebase.ctx.nodes)


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
