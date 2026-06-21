from pathlib import Path

DOCS_ROOT = Path("./docs")
SYSTEM_PROMPT_SECTIONS = (
    "introduction",
    "building-with-graph-sitter",
    "tutorials",
)
PAGE_PRIORITY = {
    "introduction": ("overview", "getting-started", "installation"),
    "building-with-graph-sitter": ("at-a-glance",),
    "tutorials": ("at-a-glance",),
}


def render_page(page_path: Path) -> str:
    return page_path.read_text(encoding="utf-8").strip()


def iter_section_pages(section: str) -> list[Path]:
    section_dir = DOCS_ROOT / section
    if not section_dir.exists():
        return []

    priorities = PAGE_PRIORITY.get(section, ())
    priority_by_stem = {stem: index for index, stem in enumerate(priorities)}

    def sort_key(page_path: Path) -> tuple[int, str]:
        priority = priority_by_stem.get(page_path.stem, len(priorities))
        return (priority, page_path.relative_to(section_dir).as_posix())

    return sorted(section_dir.rglob("*.mdx"), key=sort_key)


def render_section(section: str) -> str:
    return "\n\n".join(render_page(page) for page in iter_section_pages(section))


def get_system_prompt() -> str:
    """Generate a system prompt from the docs tree used by the custom site."""
    return "\n\n".join(section for section in (render_section(section) for section in SYSTEM_PROMPT_SECTIONS) if section)
