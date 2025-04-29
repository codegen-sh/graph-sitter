from graph_sitter.codebase.progress.progress import Progress
from graph_sitter.codebase.progress.stub_task import StubTask


class StubProgress(Progress[StubTask]):
    def begin(self, message: str, count: int | None = None) -> StubTask:
        return StubTask()
