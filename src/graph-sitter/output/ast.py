from typing import Self

from graph_sitter.codebase.span import Span
from openai import BaseModel
from pydantic.config import ConfigDict


class AST(BaseModel):
    model_config = ConfigDict(frozen=True)
    codegen_sdk_type: str
    span: Span
    tree_sitter_type: str
    children: list[tuple[str | None, Self]]
