# project ellaboration

## Scope:
Project implementation consists of:
Read @workflow/llm_guidance/project_01.md
Read @workflow/llm_guidance/project_02.md

Implementation reports:
Read @workflow/llm_memory/PROJECT_01_IMPLEMENTATION.md
Read @workflow/llm_memory/PROJECT_02_IMPLEMENTATION.md

## Task definition

**Create @workflow/llm_guidance/project_03.md**

This file must resemble the structure of @workflow/llm_guidance/project_XX.md
Must contain all important information to complete the project, using the workflow defined in @CLAUDE.md

The idea of the task is to create a very lean and simple MCP server as a python script: `./src/graph_sitter/extensions/kuzu_map/kuzu_map_mcp.py`

This MCP server must expose the same resources, tools and prompts as kuzu-mcp-server `https://github.com/kuzudb/kuzu-mcp-server/blob/main/index.js`

This MCP server must be implemented in a lean way, using FastMC. An example with hints follows in the markdown code block:

```python
from typing import Dict, List, Optional, Any
from mcp.server.fastmcp import FastMCP
import logging
import colorlog

mcp = FastMCP("{{servername}}")


@mcp.tool()
async def get_{{tool_name}}( {{args}} ) ) -> Dict[str, Any]:
    """
    Retrieve context from a codebase using code2prompt with the specified parameters.
    
    Args:
        {{args}}
    
    Returns:
        {{return}}
    """
    
    {{implemntation}}

    return {
        {{return}}
    }

if __name__ == "__main__":
    # Initialize FastMCP server
    handler = colorlog.StreamHandler()
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
        secondary_log_colors={},
        style="%",
    )
    handler.setFormatter(formatter)
    logger = colorlog.getLogger(__name__)
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    mcp.run(transport='stdio')
```

The MCP server MUST persist graph-sitter in memory, synchonizing it with kuzu db.

After wrting the plan, state the best way to invoke its execution making the use of `agents`

read @.claude/commands/🧠.md