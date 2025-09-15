#!/usr/bin/env python3
"""
Wrapper script to run the KuzuDB MCP server from project root.
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import and run the MCP server
try:
    from graph_sitter.extensions.kuzu_map.kuzu_map_mcp import main
    main()
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure all dependencies are installed and the project structure is correct.")
    sys.exit(1)
except Exception as e:
    print(f"Error running MCP server: {e}")
    sys.exit(1)