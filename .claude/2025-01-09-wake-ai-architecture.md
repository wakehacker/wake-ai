# Wake AI Architecture Plan

## Overview
This document outlines the architecture and implementation plan for integrating Claude Code AI assistance into the Wake CLI framework.

## Goals
1. Create a clean Python abstraction layer around Claude Code CLI
2. Enable multi-step AI workflows with structured prompting
3. Integrate seamlessly with Wake's existing CLI structure
4. Keep the implementation lightweight and maintainable
5. Allow for future extensibility

## Architecture Components

### 1. Directory Structure
```
wake/
├── cli/
│   ├── __main__.py      # Add ai command registration
│   ├── ai.py            # New: Main CLI command handler
│   └── ...
└── ai/                  # New: AI abstraction layer
    ├── __init__.py
    ├── claude.py        # Claude Code CLI wrapper
    ├── flow.py          # Multi-step workflow orchestrator
    ├── templates.py     # Prompt templates and structures
    └── utils.py         # Utility functions
```

### 2. Component Design

#### claude.py - Claude Code CLI Wrapper
Purpose: Provide a clean Python interface to Claude Code CLI commands

Key Classes/Functions:
- `ClaudeCodeSession`: Main wrapper class
  - `__init__(model="sonnet", allowed_tools=None, disallowed_tools=None)`
  - `query(prompt, non_interactive=True, output_format="json")`
  - `start_interactive(initial_prompt=None)`
  - `resume_session(session_id)`
  
- `ClaudeCodeResponse`: Response parser
  - Handles different output formats
  - Extracts tool usage, code changes, and messages

Example usage:
```python
session = ClaudeCodeSession(model="sonnet")
response = session.query("Analyze the codebase structure", non_interactive=True)
```

#### flow.py - Workflow Orchestrator
Purpose: Coordinate multi-step AI interactions

Key Classes/Functions:
- `AIWorkflow`: Base workflow class
  - `add_step(prompt, tools=None, validator=None)`
  - `execute(context=None)`
  - `save_state()` / `load_state()`

- `WorkflowStep`: Individual step definition
  - `prompt_template`
  - `required_tools`
  - `success_criteria`
  - `next_step_logic`

Pre-built workflows:
- `CodeAnalysisWorkflow`: Analyze codebase structure
- `RefactoringWorkflow`: Multi-step refactoring
- `TestGenerationWorkflow`: Generate tests for code

#### templates.py - Prompt Templates
Purpose: Store reusable prompt structures

Key Templates:
- `CODEBASE_ANALYSIS`: Initial codebase understanding
- `FUNCTION_DOCUMENTATION`: Document functions
- `TEST_GENERATION`: Generate unit tests
- `REFACTORING_PLAN`: Plan refactoring steps
- `CODE_REVIEW`: Review code changes

Template format:
```python
CODEBASE_ANALYSIS = """
Analyze the codebase in {directory}:
1. Identify main components and their purposes
2. Document the dependency structure
3. List potential areas for improvement

Focus on: {focus_areas}
Output format: {output_format}
"""
```

#### ai.py - CLI Command Handler
Purpose: Bridge between Wake CLI and AI functionality

Implementation:
```python
@click.group(name="ai", cls=NewCommandAlias)
@click.pass_context
def run_ai(ctx: Context):
    """AI-assisted development workflows"""
    pass

@run_ai.command(name="analyze")
@click.option("--focus", help="Specific areas to focus on")
@click.pass_context
def ai_analyze(ctx: Context, focus: Optional[str]):
    """Analyze codebase structure and patterns"""
    workflow = CodeAnalysisWorkflow()
    workflow.execute(context={"directory": ".", "focus": focus})

@run_ai.command(name="refactor")
@click.option("--target", required=True, help="Target file or directory")
@click.option("--goal", required=True, help="Refactoring goal")
@click.pass_context
def ai_refactor(ctx: Context, target: str, goal: str):
    """AI-guided refactoring"""
    workflow = RefactoringWorkflow()
    workflow.execute(context={"target": target, "goal": goal})

@run_ai.command(name="custom")
@click.option("--workflow", type=click.Path(exists=True), help="Custom workflow file")
@click.pass_context
def ai_custom(ctx: Context, workflow: str):
    """Run custom AI workflow"""
    custom_workflow = load_workflow_from_file(workflow)
    custom_workflow.execute()
```

### 3. Key Design Decisions

#### Use of subprocess vs SDK
- Use `subprocess` for Claude Code CLI interaction
- Allows full control over CLI options
- Easier to handle streaming and interactive modes
- More flexible for future CLI updates

#### State Management
- Workflows can save/load state for resumability
- Session IDs tracked for continuing conversations
- Results saved in `.wake-ai/` directory

#### Error Handling
- Graceful fallbacks for Claude Code availability
- Clear error messages for missing dependencies
- Validation at each workflow step

#### Configuration
- Leverage Wake's existing config system
- AI-specific config in `wake.toml`:
  ```toml
  [ai]
  default_model = "sonnet"
  max_turns = 10
  allowed_tools = ["read", "write", "search"]
  ```

### 4. LangChain Evaluation

After analysis, LangChain would add unnecessary complexity for this use case:
- We need direct control over Claude Code CLI
- Multi-step workflows are simple enough to implement directly
- LangChain's abstractions don't match our specific needs
- Keeping it simple makes the code more maintainable

### 5. Implementation Phases

Phase 1: Core Infrastructure
1. Create `ai/` directory structure
2. Implement `claude.py` wrapper
3. Add basic `ai` command to CLI

Phase 2: Workflow System
1. Implement `flow.py` orchestrator
2. Create basic workflow templates
3. Add workflow execution commands

Phase 3: Advanced Features
1. Custom workflow support
2. State persistence
3. Integration with Wake's existing tools

### 6. Example Usage

```bash
# Analyze codebase
wake ai analyze --focus "security patterns"

# Guided refactoring
wake ai refactor --target src/contracts --goal "optimize gas usage"

# Run custom workflow
wake ai custom --workflow .wake-ai/workflows/audit.yaml

# Interactive mode
wake ai interactive
```

### 7. Future Extensions

- Integration with Wake's test framework
- Automated PR generation
- Code review workflows
- Security audit workflows
- Performance optimization workflows

## Summary

This architecture provides a clean, extensible foundation for AI-assisted development in Wake. It leverages Claude Code's capabilities while maintaining Wake's design principles of simplicity and clarity.