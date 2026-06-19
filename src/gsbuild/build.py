import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

RUST_EXTENSION_SKIP_ENV = "GRAPH_SITTER_SKIP_RUST_EXTENSION_BUILD"
RUST_EXTENSION_PROFILE_ENV = "GRAPH_SITTER_RUST_EXTENSION_PROFILE"


def update_init_file(file: Path) -> None:
    path = Path(__file__).parent.parent
    sys.path.append(str(path))
    from graph_sitter.gscli.generate.runner_imports import generate_exported_modules, get_runner_imports

    content = file.read_text(encoding="utf-8")
    generated_imports = get_runner_imports(include_codegen=False).strip()
    generated_exports = generate_exported_modules().strip()
    for generated_block in (generated_imports, generated_exports):
        content = content.replace(generated_block, "").strip()
    content = f"{generated_imports}\n\n{content}\n\n{generated_exports}\n"
    file.write_text(content, encoding="utf-8")


def _truthy(value: str | None) -> bool:
    return value is not None and value.lower() not in {"", "0", "false", "no", "off"}


def _extension_source(root: Path, profile: str) -> Path:
    if sys.platform == "darwin":
        filename = "libgraph_sitter_py.dylib"
    elif os.name == "nt":
        filename = "graph_sitter_py.dll"
    else:
        filename = "libgraph_sitter_py.so"
    return root / "target" / profile / filename


def _build_rust_extension(root: Path, profile: str) -> Path:
    env = os.environ.copy()
    env["PYO3_PYTHON"] = sys.executable
    if sys.platform == "darwin":
        dynamic_lookup_flags = "-C link-arg=-undefined -C link-arg=dynamic_lookup"
        env["RUSTFLAGS"] = f"{env.get('RUSTFLAGS', '')} {dynamic_lookup_flags}".strip()

    command = ["cargo", "build", "-p", "graph-sitter-py", "--features", "extension-module"]
    if profile == "release":
        command.append("--release")
    subprocess.run(command, cwd=root, env=env, check=True)

    source = _extension_source(root, profile)
    if not source.exists():
        msg = f"built Rust extension artifact not found: {source}"
        raise FileNotFoundError(msg)
    return source


def _copy_extension_for_wheel(root: Path, source: Path, profile: str) -> Path:
    extension_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if not extension_suffix:
        msg = "Python extension suffix is unavailable"
        raise RuntimeError(msg)

    target = root / "target" / "wheel-rust-extension" / profile / f"graph_sitter_py{extension_suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def _rust_profile(config: dict[str, Any]) -> str:
    profile = os.environ.get(RUST_EXTENSION_PROFILE_ENV, config.get("rust-profile", "release"))
    if profile not in {"debug", "release"}:
        msg = f"Unsupported Rust extension profile: {profile!r}"
        raise ValueError(msg)
    return profile


class SpecialBuildHook(BuildHookInterface):
    PLUGIN_NAME = "codegen_build"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        build_data.setdefault("artifacts", [])
        build_data.setdefault("force_include", {})

        file = Path(self.root) / "src" / "graph_sitter" / "__init__.py"
        update_init_file(file)
        build_data["artifacts"].append(f"/{file}")

        if not self.config.get("rust-extension", True) or _truthy(os.environ.get(RUST_EXTENSION_SKIP_ENV)):
            return

        root = Path(self.root)
        profile = _rust_profile(self.config)
        source = _build_rust_extension(root, profile)
        target = _copy_extension_for_wheel(root, source, profile)
        build_data["force_include"][str(target)] = target.name
        build_data["infer_tag"] = True
        build_data["pure_python"] = False
