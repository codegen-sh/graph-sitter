from pathlib import Path

import rich_click as click


def normalize_subdirectories(repo_path: Path, raw_subdirectories: tuple[str, ...]) -> list[str] | None:
    if not raw_subdirectories:
        return None

    repo_root = repo_path.resolve()
    subdirectories: list[str] = []
    for raw_subdirectory in raw_subdirectories:
        raw_path = Path(raw_subdirectory).expanduser()
        if raw_path.is_absolute():
            try:
                relative_path = raw_path.resolve().relative_to(repo_root)
            except ValueError as error:
                msg = f"--subdir must be inside the target repository: {raw_subdirectory}"
                raise click.ClickException(msg) from error
        else:
            relative_path = raw_path

        normalized = relative_path.as_posix().removeprefix("./").rstrip("/")
        if normalized in {"", "."}:
            continue

        full_path = repo_root / normalized
        if not full_path.exists():
            msg = f"--subdir path does not exist: {normalized}"
            raise click.ClickException(msg)
        if full_path.is_dir():
            normalized = f"{normalized}/"
        subdirectories.append(normalized)

    return subdirectories or None
