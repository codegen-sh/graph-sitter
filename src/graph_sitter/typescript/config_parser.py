from pathlib import Path
from typing import TYPE_CHECKING, cast

from graph_sitter.codebase.config_parser import ConfigParser
from graph_sitter.core.file import File
from graph_sitter.enums import NodeType
from graph_sitter.typescript.ts_config import TSConfig

if TYPE_CHECKING:
    from graph_sitter.codebase.codebase_context import CodebaseContext
    from graph_sitter.typescript.file import TSFile

import os
from functools import cache


class TSConfigParser(ConfigParser):
    # Cache of path names to TSConfig objects
    config_files: dict[Path, TSConfig]
    ctx: "CodebaseContext"

    def __init__(self, codebase_context: "CodebaseContext", default_config_name: str = "tsconfig.json"):
        super().__init__()
        self.config_files = dict()
        self.ctx = codebase_context
        self.default_config_name = default_config_name

    def get_config(self, config_path: os.PathLike | str) -> TSConfig | None:
        path = self._normalize_config_path(self.ctx.to_absolute(config_path))
        if path is None:
            return None
        if path in self.config_files:
            return self.config_files[path]
        if path.exists():
            config_file = File.from_content(path, path.read_text(), self.ctx, sync=False)
            if config_file is None:
                return None
            self.config_files[path] = TSConfig(config_file, self)
            return self.config_files[path]
        return None

    def _normalize_config_path(self, path: Path) -> Path | None:
        if path.is_dir():
            path = path / self.default_config_name
        elif not path.exists() and path.suffix != ".json":
            json_path = path.with_suffix(".json")
            if json_path.exists():
                path = json_path

        if path.exists() and not path.is_file():
            return None
        return path

    def parse_configs(self, codebase_context: "CodebaseContext | None" = None) -> None:
        # This only yields a 0.05s speedup, but its funny writing dynamic programming code
        @cache
        def get_config_for_dir(dir_path: Path) -> TSConfig | None:
            # Check if the config file exists in the directory
            ts_config_path = dir_path / self.default_config_name
            # If it does, return the config
            if ts_config_path.exists():
                if ts_config := self.get_config(self.ctx.to_absolute(ts_config_path)):
                    self.config_files[ts_config_path] = ts_config
                    return ts_config
            # Otherwise, check the parent directory
            if dir_path.is_relative_to(self.ctx.repo_path):
                return get_config_for_dir(dir_path.parent)
            return None

        # Get all the files in the codebase
        for file in self.ctx.get_nodes(NodeType.FILE):
            ts_file = cast("TSFile", file)  # This should be safe because we only call this on TSFiles
            # Get the config for the directory the file is in
            config = get_config_for_dir(ts_file.path.parent)
            # Set the config for the file
            ts_file.ts_config = config

        # Loop through all the configs and precompute their import aliases
        for config in self.config_files.values():
            config._precompute_import_aliases()
