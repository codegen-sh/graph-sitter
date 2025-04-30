from graph_sitter.codebase.flagging.code_flag import CodeFlag
from graph_sitter.codebase.flagging.group import Group
from graph_sitter.codebase.flagging.groupers.base_grouper import BaseGrouper
from graph_sitter.codebase.flagging.groupers.enums import GroupBy
from graph_sitter.git.repo_operator.repo_operator import RepoOperator
from graph_sitter.shared.logging.get_logger import get_logger

logger = get_logger(__name__)


class AppGrouper(BaseGrouper):
    """Group flags by segment=app.
    Ex: apps/profile.
    """

    type: GroupBy = GroupBy.APP

    @staticmethod
    def create_all_groups(flags: list[CodeFlag], repo_operator: RepoOperator | None = None) -> list[Group]:
        unique_apps = list({"/".join(flag.filepath.split("/")[:3]) for flag in flags})
        groups = []
        for idx, app in enumerate(unique_apps):
            matches = [f for f in flags if f.filepath.startswith(app)]
            if len(matches) > 0:
                groups.append(Group(id=idx, group_by=GroupBy.APP, segment=app, flags=matches))
        return groups

    @staticmethod
    def create_single_group(flags: list[CodeFlag], segment: str, repo_operator: RepoOperator | None = None) -> Group:
        segment_flags = [f for f in flags if f.filepath.startswith(segment)]
        if len(segment_flags) == 0:
            logger.warning(f"🤷‍♀️ No flags found for APP segment: {segment}")
        return Group(group_by=GroupBy.APP, segment=segment, flags=segment_flags)
