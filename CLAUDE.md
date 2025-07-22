# Wake AI Architecture

## Overview

Wake AI is now a standalone Python package that provides AI-powered smart contract analysis capabilities. It has been extracted from the Wake framework into an independent module that can be used separately or integrated with other tools.

## Module Structure

The project is organized into two main directories:

### 1. Core Framework (`wake_ai/`)
Contains the AI framework implementation:
- **core/** - Core Claude integration and workflow engine
  - `claude.py` - Claude Code CLI wrapper with session management
  - `flow.py` - Base workflow and step classes
  - `exceptions.py` - Custom exceptions
  - `utils.py` - Framework utilities
- **detections.py** - Detection data models and formatters
- **results.py** - Result types (AIResult, SimpleResult, AIDetectionResult)
- **runner.py** - Workflow execution helper
- **utils.py** - Shared utilities (YAML loading, validation)
- **cli.py** - Command-line interface

### 2. Workflows (`flows/`)
Contains pre-built workflow implementations:
- **audit/** - Comprehensive security audit workflow
- **example/** - Example workflow template
- **test/** - Testing workflow
- **validation_test/** - Validation testing workflow

## Key Features

### Standalone CLI
Wake AI provides its own CLI interface:
```bash
wake-ai --flow audit                    # Run audit workflow
wake-ai --flow audit -s contracts/*.sol # Audit specific files
wake-ai --resume                        # Resume previous session
wake-ai --export results.json           # Export results
```

### Session Management
- Each workflow creates its own `ClaudeCodeSession`
- Sessions can be resumed between runs
- Working directory isolation per session
- State persistence for interrupted workflows

### Cost Management
- `query_with_cost()` implements intelligent cost-limited execution
- Configurable cost limits per step
- Automatic prompt optimization when approaching limits
- Cost tracking and reporting

### Validation System
- Step-level validation with automatic retries
- Custom validators per workflow step
- Error correction prompts on validation failure

## Technical Implementation

### Core Classes

#### AIWorkflow (Base Class)
- Abstract base for all workflows
- Manages step execution and state
- Handles context passing between steps
- Provides resume capability

#### WorkflowStep
- Represents a single workflow step
- Contains prompt template, tools, and validation
- Configurable retry and cost limits

#### ClaudeCodeSession
- Wrapper around Claude Code CLI
- Manages session lifecycle
- Tracks costs and usage
- Handles working directory setup

### Execution Flow

1. **Initialization**
   - Workflow creates unique session ID
   - Working directory is created at `.wake/ai/<session-id>/`
   - Initial context is prepared

2. **Step Execution**
   - Each step gets its own ClaudeCodeSession
   - Prompt is rendered with current context
   - Claude executes with specified tools
   - Results are validated (if validator provided)
   - Context is updated with step output

3. **Error Handling**
   - Validation failures trigger retries
   - Cost limits are monitored
   - Sessions can be resumed on interruption

### Context Management
- Each step has access to:
  - `{working_dir}` - Session working directory
  - `{execution_dir}` - Where workflow was launched
  - Previous step outputs as `{step_name}_output`
  - Custom context from workflow initialization

## Working Directory Structure

Each workflow session creates an isolated working directory:

```
.wake/ai/<session-id>/
├── state/              # Workflow state for resume capability
│   ├── workflow.json   # Workflow metadata and progress
│   └── context.json    # Current context state
├── results/            # AI-generated output files
│   ├── detections.yaml # Security findings
│   ├── report.md       # Analysis reports
│   └── ...             # Other workflow outputs
└── temp/               # Temporary working files
```

### Session Management
- **Session ID Format**: `YYYYMMDD_HHMMSS_random` (e.g., `20250121_143022_abc123`)
- **Path Template**: `.wake/ai/<session-id>/`
- **Automatic Creation**: Directory created on workflow initialization
- **Context Access**: Available as `{working_dir}` in all prompts
- **Automatic Cleanup**: Working directories can be automatically cleaned up after successful completion
  - Base AIWorkflow default: `cleanup_working_dir = False` (preserves working directory)
  - Individual workflows can override this default (e.g., some workflows might set `cleanup_working_dir = True`)
  - Override via CLI: `--no-cleanup` to preserve, `--cleanup` to force cleanup
  - Override in code: pass `cleanup_working_dir` parameter to workflow constructor

### State Persistence
The workflow state is saved after each step:
- Progress tracking for resume capability
- Context preservation between steps
- Cost accumulation tracking
- Step outputs stored for reference

## Creating Custom Workflows

To create a new workflow, inherit from `AIWorkflow`:

```python
from wake_ai import AIWorkflow, WorkflowStep
from wake_ai.core.utils import validate_yaml_output

class MyWorkflow(AIWorkflow):
    """Custom workflow implementation."""

    def _setup_steps(self):
        """Define workflow steps."""
        # Step 1: Analysis
        self.add_step(
            name="analyze",
            prompt_template=self._load_prompt("analyze.md"),
            tools=["file_search", "file_read"],
            max_retries=2,
            max_cost_limit=5.0
        )

        # Step 2: Generate results
        self.add_step(
            name="generate",
            prompt_template=self._load_prompt("generate.md"),
            tools=["file_write"],
            validator=validate_yaml_output,
            max_retries=3
        )

    @classmethod
    def get_cli_options(cls):
        """Define CLI options for this workflow."""
        return {
            "target": {
                "param_decls": ["-t", "--target"],
                "type": click.Path(exists=True),
                "help": "Target file or directory"
            }
        }

    @classmethod
    def process_cli_args(cls, **kwargs):
        """Process CLI arguments into workflow initialization args."""
        return {
            "target": kwargs.get("target", ".")
        }
```

## Package Configuration

### Installation
```bash
# From PyPI
pip install wake-ai

# Development mode
git clone https://github.com/Ackee-Blockchain/wake-ai
cd wake-ai
pip install -e ".[dev]"
```

### Dependencies
- **Core**: click, rich, pyyaml
- **Development**: black, isort, pytest, mypy
- **Runtime**: Claude Code CLI must be installed

### Entry Points
- `wake-ai` - Main CLI command
- Python API: `import wake_ai`

## Migration from Wake

The AI module has been extracted from Wake with the following changes:

1. **Independent Package**: No Wake dependencies
2. **Standalone CLI**: `wake-ai` instead of `wake ai`
3. **Simplified Structure**: Focused solely on AI workflows
4. **No Detector Integration**: Pure workflow execution
5. **Portable Workflows**: Can be used in any project

### Import Changes
```python
# Old (within Wake)
from wake.ai import AIWorkflow
from wake_ai.audit import AuditWorkflow

# New (standalone)
from wake_ai import AIWorkflow
from flows.audit import AuditWorkflow
```

## Prompt Writing Guidelines

When creating Wake AI workflow prompts, follow the guidelines in `prompt-writing.mdc`. Key principles:

### Structure
- Use Task-First Architecture with `<task>`, `<context>`, `<steps>` structure
- Include explicit `<validation_requirements>` sections
- Provide complete `<output_format>` examples with YAML/code
- Follow the three-phase pattern: Discovery → Analysis → Documentation

### Best Practices
- Start with a concise one-sentence `<task>` declaration
- Use numbered steps with **bold headings**
- Include sub-steps (a, b, c) for complex operations
- Reference specific Wake tools and commands
- Provide real-world code examples in output formats