from pathlib import Path

# Base directories
CONFIG_DIR = Path("~/.config/codegen-sh").expanduser()
CODEGEN_DIR = Path(".codegen")

# Subdirectories
DOCS_DIR = CODEGEN_DIR / "docs"
EXAMPLES_DIR = CODEGEN_DIR / "examples"

# Files
AUTH_FILE = CONFIG_DIR / "auth.json"
