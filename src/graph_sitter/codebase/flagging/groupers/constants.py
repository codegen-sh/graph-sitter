from graph_sitter.codebase.flagging.groupers.all_grouper import AllGrouper
from graph_sitter.codebase.flagging.groupers.app_grouper import AppGrouper
from graph_sitter.codebase.flagging.groupers.codeowner_grouper import CodeownerGrouper
from graph_sitter.codebase.flagging.groupers.file_chunk_grouper import FileChunkGrouper
from graph_sitter.codebase.flagging.groupers.file_grouper import FileGrouper
from graph_sitter.codebase.flagging.groupers.instance_grouper import InstanceGrouper

ALL_GROUPERS = [
    AllGrouper,
    AppGrouper,
    CodeownerGrouper,
    FileChunkGrouper,
    FileGrouper,
    InstanceGrouper,
]
