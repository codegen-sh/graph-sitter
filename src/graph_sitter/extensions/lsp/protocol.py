import os
from pathlib import Path
from typing import TYPE_CHECKING

from lsprotocol.types import INITIALIZE, InitializeParams, InitializeResult
from pygls.protocol import LanguageServerProtocol, lsp_method

from graph_sitter.configs.models.codebase import CodebaseConfig
from graph_sitter.core.codebase import Codebase
from graph_sitter.extensions.lsp.io import LSPIO
from graph_sitter.extensions.lsp.progress import LSPProgress
from graph_sitter.extensions.lsp.utils import get_path

if TYPE_CHECKING:
    from graph_sitter.extensions.lsp.server import GraphSitterLanguageServer


class GraphSitterLanguageServerProtocol(LanguageServerProtocol):
    _server: "GraphSitterLanguageServer"

    def _init_codebase(self, params: InitializeParams) -> None:
        progress = LSPProgress(self._server, params.work_done_token)
        if params.root_path:
            root = Path(params.root_path)
        elif params.root_uri:
            root = get_path(params.root_uri)
        else:
            root = os.getcwd()
        config = CodebaseConfig().model_copy(update={"full_range_index": True})
        io = LSPIO(self.workspace)
        self._server.codebase = Codebase(repo_path=str(root), config=config, io=io, progress=progress)
        self._server.progress_manager = progress
        self._server.io = io
        progress.finish_initialization()

    @lsp_method(INITIALIZE)
    def lsp_initialize(self, params: InitializeParams) -> InitializeResult:
        ret = super().lsp_initialize(params)
        self._init_codebase(params)
        return ret
