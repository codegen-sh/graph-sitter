# Project Context for Multi-Agent Development

## Project Overview
This project implements [project description] using modern C++ and Python with a focus on performance, maintainability, and cross-platform compatibility.

## Technical Standards
Read(`workflow/llm_guidance/coding_guidelines.md`)

### Python Guidelines  
- **Version**: Python 3.13+
- **Type Checking**: mypy in strict mode
- **Async**: asyncio for all I/O operations
- **Style**: PEP 8 with type hints mandatory
- **Documentation**: Google-style docstrings

## Multi-Agent Workflow

Agents can be monitored through 
- `./workflow/llm_guidance/agents/monitor-agents.py`
- `./workflow/llm_guidance/llm_coordination/`

### Agent Hierarchy
1. **architect-coordinator**: Main orchestrator, never implements
3. **python-implementation**: Python code implementation

### Coordination Protocol
- All agents communicate through JSON files in `./workflow/llm_guidance/llm_coordination/`
- Main orchestrator deploys agents using `/agents <name> <task>`
- Handoffs include context, specifications, and success criteria
- Validation gates ensure quality before task completion

## Agent Usage Examples

### Starting a new feature:
```
/agents architect-coordinator "Design and implement a thread-safe memory pool allocator for real-time systems"
```

## Workflow Best Practices

### Do's ✅
- Break complex tasks into 5-10 subtasks maximum
- Use parallel agents for independent components
- Implement validation gates between phases
- Maintain clear specifications in coordination files
- Use file-based handoffs for large outputs
- Deploy reviewer after every implementation
- Keep agent prompts focused and specific

### Don'ts ❌
- Don't let the orchestrator implement code
- Don't skip test creation phase
- Don't allow peer-to-peer agent communication
- Don't exceed 20 subtasks (causes coordination overhead)
- Don't deploy dependent agents in parallel
- Don't skip review validation gates
- Don't modify other agents' outputs directly

