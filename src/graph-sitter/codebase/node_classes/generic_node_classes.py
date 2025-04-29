from graph_sitter.codebase.node_classes.node_classes import NodeClasses
from graph_sitter.core.class_definition import Class
from graph_sitter.core.detached_symbols.code_block import CodeBlock
from graph_sitter.core.detached_symbols.function_call import FunctionCall
from graph_sitter.core.detached_symbols.parameter import Parameter
from graph_sitter.core.file import File
from graph_sitter.core.function import Function
from graph_sitter.core.import_resolution import Import
from graph_sitter.core.statements.comment import Comment

GenericNodeClasses = NodeClasses(
    file_cls=File,
    class_cls=Class,
    function_cls=Function,
    import_cls=Import,
    parameter_cls=Parameter,
    comment_cls=Comment,
    code_block_cls=CodeBlock,
    function_call_cls=FunctionCall,
    bool_conversion={},
    dynamic_import_parent_types={},
)
