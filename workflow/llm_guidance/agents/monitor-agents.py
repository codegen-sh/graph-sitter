#!/usr/bin/env python3
"""Monitor multi-agent task progress."""

import json
import time
from pathlib import Path
from datetime import datetime

def monitor_agents():
    """Monitor and display agent progress."""
    status_file = Path("./workflow/llm_guidance/llm_coordination/agent-status.json")
    task_file = Path("./workflow/llm_guidance/llm_coordination/task-queue.json")
    
    print("🔍 Monitoring Agent Activity...")
    print("-" * 50)
    
    while True:
        try:
            # Read status
            if status_file.exists():
                with open(status_file) as f:
                    status = json.load(f)
                
                print(f"\n📊 Status Update - {datetime.now().strftime('%H:%M:%S')}")
                print(f"   Active Agents: {len(status.get('active_agents', []))}")
                print(f"   Completed: {len(status.get('completed_tasks', []))}")
                print(f"   Blocked: {len(status.get('blocked_tasks', []))}")
                
                # Show active agents
                for agent in status.get('active_agents', []):
                    print(f"   🔄 {agent}")
                
                # Show blocked tasks
                for task in status.get('blocked_tasks', []):
                    print(f"   ⚠️  Blocked: {task.get('id', 'unknown')}")
            
            # Read task queue
            if task_file.exists():
                with open(task_file) as f:
                    tasks = json.load(f)
                
                for task in tasks.get('tasks', []):
                    total = len(task.get('subtasks', []))
                    complete = len([st for st in task.get('subtasks', []) 
                                  if st.get('status') == 'complete'])
                    
                    progress = (complete / total * 100) if total > 0 else 0
                    print(f"   📈 {task.get('title', 'Task')}: {progress:.0f}%")
            
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped.")
            break
        except Exception as e:
            print(f"   ❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    monitor_agents()
