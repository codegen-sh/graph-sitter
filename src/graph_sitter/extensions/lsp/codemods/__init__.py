from graph_sitter.extensions.lsp.codemods.base import CodeAction
from graph_sitter.extensions.lsp.codemods.split_tests import SplitTests

ACTIONS: list[CodeAction] = [SplitTests()]
