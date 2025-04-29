from graph_sitter.codebase.span import Span
from pydantic import BaseModel
from pydantic.config import ConfigDict


class Placeholder(BaseModel):
    model_config = ConfigDict(frozen=True)
    preview: str
    span: Span
    kind_id: int
    name: str
