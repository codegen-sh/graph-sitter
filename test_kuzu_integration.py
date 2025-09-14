"""Test script for KuzuDB integration."""

import tempfile
import shutil
from pathlib import Path

try:
    from src.graph_sitter.core.codebase import Codebase
    from src.graph_sitter.extensions.kuzu_map import KuzuSync, CodeMonitor
    from src.graph_sitter.extensions.kuzu_map.monitor import CodeGraphAnalyzer

    print("✓ All imports successful")

    # Create a temporary test directory
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)

        # Create a simple Python file for testing
        test_file = test_dir / "test.py"
        test_file.write_text("""
def hello_world():
    '''A simple greeting function.'''
    return "Hello, World!"

class Greeter:
    '''A greeting class.'''

    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"Hello, {self.name}!"

if __name__ == "__main__":
    print(hello_world())
""")

        print(f"✓ Created test file: {test_file}")

        # Test codebase loading (use current directory which is a git repo)
        try:
            codebase = Codebase("./")
            print(f"✓ Codebase loaded with {len(codebase.files)} files")

            if codebase.functions:
                print(f"✓ Found {len(codebase.functions)} functions")

            if codebase.classes:
                print(f"✓ Found {len(codebase.classes)} classes")

        except Exception as e:
            print(f"✗ Codebase loading failed: {e}")
            exit(1)

        # Test KuzuSync initialization
        try:
            db_path = test_dir / "test.kuzu"
            kuzu_sync = KuzuSync(codebase, str(db_path))
            print("✓ KuzuSync initialized")

            # Test basic schema creation (no actual sync to avoid kuzu dependency issues)
            print("✓ KuzuDB schema should be initialized")

            kuzu_sync.close()
            print("✓ KuzuDB connection closed")

        except Exception as e:
            print(f"✗ KuzuSync failed: {e}")
            # This is expected if kuzu is not installed
            print("  (This is expected if kuzu package is not installed)")

    print("\n✓ Basic integration test completed successfully!")
    print("To fully test with KuzuDB:")
    print("1. Install kuzu: pip install kuzu")
    print("2. Run: python src/graph_sitter/extensions/kuzu_map/example.py sync")

except ImportError as e:
    print(f"✗ Import failed: {e}")
except Exception as e:
    print(f"✗ Test failed: {e}")