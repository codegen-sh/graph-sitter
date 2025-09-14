#!/usr/bin/env python3
"""
Real-time markdown logger for Claude Code sessions.
Logs all messages and tool operations to a markdown file.
"""

import json
import sys
import os
import git
from datetime import datetime
from pathlib import Path

claude_root    = os.getenv("CLAUDE_PROJECT_DIR", "./")
relative_path  = "docs/llm_history"
current_branch = git.Repo(os.getcwd()).active_branch.name

log_dir        = ( Path( claude_root ) /   relative_path            ).resolve()
log_file       = ( log_dir             / ( current_branch + ".md" ) ).resolve()

def append_to_log(session_id, content):
    """Append content to session log file."""

    # Skip if content is None or empty
    if not content:
        return

    # Ensure content is a string
    if not isinstance(content, str):
        content = str(content)

    # Create file with header if it doesn't exist
    if not log_file.exists():
        with open(log_file, 'w') as f:
            f.write(f"# 🧠 remembers { current_branch }\n")
            f.write("---\n\n")

    # Append new content
    with open(log_file, 'a') as f:
        f.write(content)
        f.write("\n")

def get_latest_conversation_file():
    """Find the most recent conversation file for current session."""
    claude_dir = Path.home() / ".claude" / "projects"

    # Get project hash from current directory
    cwd = os.getcwd()
    project_hash = cwd.replace("/", "-")
    project_dir = claude_dir / project_hash
    
    if not project_dir.exists():
        return None
    
    # Find most recent JSONL file
    jsonl_files = list(project_dir.glob("*.jsonl"))
    if not jsonl_files:
        return None
    
    return max(jsonl_files, key=lambda f: f.stat().st_mtime)

def extract_claude_response(conversation_file):
    """Extract the latest Claude response from conversation file."""
    if not conversation_file or not conversation_file.exists():
        return None

    responses = []
    with open(conversation_file, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line)
                # Handle Claude Code conversation format
                if entry.get('type') == 'assistant' and 'message' in entry:
                    message = entry.get('message', {})
                    content = message.get('content', [])
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text_parts.append(item.get('text', ''))
                    if text_parts:
                        responses.append('\n'.join(text_parts))
            except json.JSONDecodeError:
                continue

    return responses[-1] if responses else None

def main():
    try:
        # Read hook input
        hook_data = json.load(sys.stdin)
        hook_event = hook_data.get('hook_event_name', 'Unknown')
        session_id = hook_data.get('session_id', 'unknown')
        # Handle different hook events
        if hook_event == 'UserPromptSubmit':
            prompt = hook_data.get('prompt', '')
            timestamp = datetime.now().strftime('%H:%M:%S')
            content = f"🧠 { prompt }\n"
            append_to_log(session_id, content)
            
        elif hook_event == 'PostToolUse':
            tool_name = hook_data.get('tool_name', '')
            tool_input = hook_data.get('tool_input', {})
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            content = f"{tool_name}(`"
            
            if tool_name in ['Write', 'Edit', 'MultiEdit']:
                file_path = tool_input.get('file_path', 'unknown')
                content += f"{file_path}"
                
            elif tool_name == 'Bash':
                command = tool_input.get('command', '')
                content += f"{command}"
                
            elif tool_name == 'Read':
                file_path = tool_input.get('file_path', 'unknown')
                content += f"{file_path}"
            else:
                content += f"{tool_input}"
            content += "`)"
            append_to_log(session_id, content)
            
        elif hook_event == 'Stop':
            # Try to get transcript path from hook data first
            transcript_path = hook_data.get('transcript_path')
            if transcript_path:
                conv_file = Path(transcript_path)
            else:
                # Fallback to the discovery method
                conv_file = get_latest_conversation_file()

            response = extract_claude_response(conv_file)
            if response:
                append_to_log(session_id, response + "\n")
            
        elif hook_event == 'SessionStart':
            # timestamp = datetime.now().strftime('%H:%M:%S')
            # content = f"### 📝 Session Started [{timestamp}]\n"
            # append_to_log(session_id, content)
            pass
            
        elif hook_event == 'SessionEnd':
            reason = hook_data.get('reason', 'unknown')
            timestamp = datetime.now().strftime('%H:%M:%S')
            content = f"\n---\n\n**Session ended:** {timestamp} (Reason: {reason})\n"
            append_to_log(session_id, content)
            
    except Exception as e:
        # Log errors silently to avoid disrupting Claude Code
        error_log = log_dir / "session_logger_errors.log"
        error_log.parent.mkdir(exist_ok=True)
        with open(error_log, 'a') as f:
            f.write(f"{datetime.now()}: {str(e)}\n")

if __name__ == "__main__":
    main()