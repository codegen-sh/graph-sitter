"""Extensions for the codegen package."""

from graph_sitter.extensions.index.code_index import CodeIndex
from graph_sitter.extensions.index.file_index import FileIndex

try:
    from graph_sitter.extensions.kuzu_map.sync import KuzuSync
    from graph_sitter.extensions.kuzu_map.monitor import CodeMonitor, CodeGraphAnalyzer
    __all__ = ["CodeIndex", "FileIndex", "KuzuSync", "CodeMonitor", "CodeGraphAnalyzer"]
except ImportError:
    # KuzuDB not available
    __all__ = ["CodeIndex", "FileIndex"]
