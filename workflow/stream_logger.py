#!/usr/bin/env python3
"""
Memory-efficient streaming logger that writes immediately to disk.
Includes deduplication and compression options.
"""

import json
import sys
import os
import hashlib
from datetime import datetime
from pathlib import Path

class StreamingLogger:
    def __init__(self, session_id):
        self.session_id = session_id
        self.log_dir = Path.home() / "claude_logs" / "streaming"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        self.log_file = self.log_dir / f"stream_{date_str}_{session_id[:8]}.md"
        self.seen_hashes = set()
        
        # Initialize log file
        if not self.log_file.exists():
            self._write_header()
    
    def _write_header(self):
        """Write log file header."""
        with open(self.log_file, 'w') as f:
            f.write(f"# Claude Code Streaming Log\n\n")
            f.write(f"**Session:** {self.session_id[:8]}\n")
            f.write(f"**Started:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Project:** `{os.getcwd()}`\n\n")
            f.write("---\n\n")
    
    def _content_hash(self, content):
        """Generate hash for deduplication."""
        return hashlib.md5(content.encode()).hexdigest()
    
    def log_event(self, event_type, content, metadata=None):
        """Log an event with deduplication."""
        # Check for duplicate content
        content_hash = self._content_hash(content)
        if content_hash in self.seen_hashes:
            return  # Skip duplicate
        
        self.seen_hashes.add(content_hash)
        
        # Format timestamp
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Write to log
        with open(self.log_file, 'a') as f:
            if event_type == 'prompt':
                f.write(f"## 👤 User [{timestamp}]\n\n")
                f.write(f"{content}\n\n")
                
            elif event_type == 'tool':
                tool_name = metadata.get('name', 'Unknown')
                f.write(f"### 🔧 {tool_name} [{timestamp}]\n\n")
                
                # Compact tool representation
                if tool_name in ['Write', 'Edit']:
                    file_path = metadata.get('file_path', '')
                    f.write(f"Modified: `{file_path}`\n\n")
                elif tool_name == 'Bash':
                    f.write(f"```bash\n{content[:200]}\n```\n\n")
                else:
                    f.write(f"Operation: {content[:100]}...\n\n")
                    
            elif event_type == 'response':
                f.write(f"## 🤖 Claude [{timestamp}]\n\n")
                # Only log first 500 chars of response for efficiency
                f.write(f"{content[:500]}{'...' if len(content) > 500 else ''}\n\n")
            
            f.flush()  # Ensure immediate write to disk

def main():
    try:
        hook_data = json.load(sys.stdin)
        session_id = hook_data.get('session_id', 'unknown')
        hook_event = hook_data.get('hook_event_name', '')
        
        logger = StreamingLogger(session_id)
        
        if hook_event == 'UserPromptSubmit':
            prompt = hook_data.get('prompt', '')
            logger.log_event('prompt', prompt)
            
        elif hook_event == 'PostToolUse':
            tool_name = hook_data.get('tool_name', '')
            tool_input = hook_data.get('tool_input', {})
            
            # Create compact representation
            if tool_name == 'Bash':
                content = tool_input.get('command', '')
            else:
                content = json.dumps(tool_input, separators=(',', ':'))[:200]
            
            metadata = {
                'name': tool_name,
                'file_path': tool_input.get('file_path', '')
            }
            
            logger.log_event('tool', content, metadata)
            
    except Exception as e:
        # Log errors
        error_log = Path.home() / "claude_logs" / "errors.log"
        error_log.parent.mkdir(exist_ok=True)
        with open(error_log, 'a') as f:
            f.write(f"{datetime.now()}: Stream logger error: {str(e)}\n")

if __name__ == "__main__":
    main()