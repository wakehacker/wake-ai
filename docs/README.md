# Wake AI Documentation

## Table of Contents

- [Introduction](#introduction)
- [Installation](#installation)
- [Getting Started](#getting-started)
- [Core Concepts](#core-concepts)
- [Creating Workflows](#creating-workflows)
- [Advanced Features](#advanced-features)
- [Examples](#examples)
- [API Reference](#api-reference)
- [Best Practices](#best-practices)

## Introduction

Wake AI is a framework for building AI-powered workflows to analyze smart contracts. It wraps Claude's capabilities in a structured workflow engine that provides cost control, validation, retry logic, and session management.

### Key Features

- **Workflow Engine**: Chain multiple AI steps with context passing
- **Cost Management**: Set per-step cost limits to control spending
- **Validation & Retry**: Automatic validation with configurable retries
- **Session Persistence**: Resume workflows from where they left off
- **Tool Control**: Fine-grained control over which tools Claude can use
- **Working Directory**: Isolated workspace for each workflow run

## Installation

### Requirements

- Python 3.8+
- Claude Code CLI installed and authenticated

### Install from PyPI

```bash
pip install wake-ai
```

### Install from Source

```bash
git clone https://github.com/Ackee-Blockchain/wake-ai
cd wake-ai
pip install -e .
```

### Claude Code Setup

Wake AI requires Claude Code CLI:

```bash
# Install Claude Code
pip install claude-code

# Authenticate
claude-code auth
```

## Getting Started

### Running Pre-built Workflows

Wake AI comes with ready-to-use workflows:

```bash
# Run comprehensive security audit
wake-ai audit

# Detect Uniswap-specific vulnerabilities
wake-ai uniswap

# Specify files to analyze
wake-ai audit -s contracts/Token.sol -s contracts/Vault.sol

# Export results
wake-ai audit --export results.json

# Resume interrupted workflow
wake-ai --resume
```

### Creating a Simple Detector

The easiest way to create a custom detector is using the `MarkdownDetector` template:

```python
from wake_ai.templates import MarkdownDetector

class AccessControlDetector(MarkdownDetector):
    """Detect access control vulnerabilities."""
    
    name = "access-control"
    
    def get_detector_prompt(self) -> str:
        return """
        Analyze this codebase for access control vulnerabilities.
        
        Check for:
        1. Missing access modifiers (onlyOwner, etc.)
        2. Incorrect permission checks
        3. Centralization risks
        4. Privilege escalation paths
        
        For each issue found, provide:
        - Clear explanation
        - Severity (critical/high/medium/low)
        - Recommended fix with code
        """
```

Register and run:

```bash
wake-ai access-control
```

## Core Concepts

### Workflows

A workflow is a sequence of AI-powered steps that execute in order. Each workflow:
- Has a unique working directory (`.wake/ai/<session-id>/`)
- Maintains context between steps
- Can be resumed if interrupted
- Tracks costs and validates outputs

### Steps

Each step in a workflow:
- Has a prompt template (using Jinja2)
- Can specify allowed/disallowed tools
- Has optional validation logic
- Can retry on failure
- Updates the workflow context

### Context

Context is how data flows between steps:
- Each step can access all previous outputs
- Special variables: `{{working_dir}}`, `{{execution_dir}}`
- Step outputs available as `{{step_name}_output}}`
- Custom context via `add_context()`

### Validation

Steps can have validators that ensure output quality:
- Return `(success: bool, errors: List[str])`
- Failed validation triggers retry with error feedback
- Maximum retry attempts configurable per step

## Creating Workflows

### AI-Assisted Workflow Generation

Wake AI includes a powerful prompt template that helps generate new workflows from your ideas. The prompt guides AI through creating complete workflow implementations following Wake AI patterns and best practices.

**Location**: `prompts/wake-ai-flow-generation.md`

This prompt helps you:
- Transform security analysis ideas into working detectors
- Create multi-step audit workflows with proper validation
- Generate CLI-ready workflows with all required components
- Follow Wake AI coding patterns and conventions

Example usage:
```bash
# Use the prompt with your favorite AI to generate a new workflow
# Then save the generated code to flows/my_detector/workflow.py
```

The prompt handles:
- Choosing between `MarkdownDetector` (simple) or `AIWorkflow` (complex)
- Setting up steps with appropriate tools and validators
- Creating CLI options and argument processing
- Implementing proper error handling and validation
- Following Wake AI's structured prompt patterns

### Multi-Step Workflow Example

```python
from wake_ai import AIWorkflow, WorkflowStep
from wake_ai.core.utils import validate_yaml_output

class TestGeneratorWorkflow(AIWorkflow):
    """Generate comprehensive test suites."""
    
    name = "test-gen"
    
    def _setup_steps(self):
        # Step 1: Analyze contract structure
        self.add_step(
            name="analyze",
            prompt_template="""Analyze the smart contract structure.
            
            Working directory: {{working_dir}}
            
            Tasks:
            1. Identify all functions and their purposes
            2. Find state variables and invariants
            3. Detect external dependencies
            
            Output a structured analysis.
            """,
            tools=["Read", "Grep", "Write"],
            max_cost=5.0
        )
        
        # Step 2: Generate test plan
        self.add_step(
            name="plan",
            prompt_template="""Based on your analysis:
            {{analyze_output}}
            
            Create a comprehensive test plan covering:
            - Unit tests for each function
            - Integration tests
            - Edge cases and attack vectors
            
            Output as YAML in plan.yaml
            """,
            tools=["Write"],
            validator=validate_yaml_output,
            max_cost=3.0
        )
        
        # Step 3: Implement tests
        self.add_step(
            name="implement",
            prompt_template="""Implement the test plan from plan.yaml.
            
            Generate test files using appropriate framework.
            Include detailed comments and assertions.
            """,
            tools=["Read", "Write", "MultiEdit"],
            max_cost=10.0,
            max_retries=2
        )
```

### Adding CLI Options

```python
@classmethod
def get_cli_options(cls):
    return {
        "framework": {
            "param_decls": ["-f", "--framework"],
            "type": click.Choice(["foundry", "hardhat"]),
            "default": "foundry",
            "help": "Test framework to use"
        }
    }

@classmethod
def process_cli_args(cls, **kwargs):
    return {
        "test_framework": kwargs.get("framework", "foundry")
    }
```

## Advanced Features

### Dynamic Step Generation

Generate steps at runtime based on analysis results:

```python
def _setup_steps(self):
    # Initial analysis step
    self.add_step(
        name="scan",
        prompt_template="Scan for all Solidity files...",
        tools=["Glob", "Read"]
    )
    
    # Generate steps based on findings
    def generate_review_steps(response, context):
        files = parse_file_list(response.content)
        steps = []
        
        for file in files:
            steps.append(WorkflowStep(
                name=f"review_{file.name}",
                prompt_template=f"Review {file.path} for vulnerabilities...",
                tools=["Read", "Write"],
                max_cost=2.0
            ))
        
        return steps
    
    self.add_dynamic_steps(
        name="file_reviews",
        generator=generate_review_steps,
        after_step="scan"
    )
```

### Conditional Step Execution

Skip steps based on runtime conditions:

```python
self.add_step(
    name="deep_analysis",
    prompt_template="Perform deep vulnerability analysis...",
    condition=lambda ctx: ctx.get("vulnerabilities_found", 0) > 0,
    max_cost=20.0
)
```

### Structured Data Extraction

Extract and validate structured data from AI responses:

```python
from pydantic import BaseModel

class VulnerabilityReport(BaseModel):
    title: str
    severity: str
    description: str
    recommendation: str

# Add extraction after analysis step
self.add_extraction_step(
    after_step="analyze",
    output_schema=VulnerabilityReport,
    context_key="vulnerability_data"
)

# Access in next step
self.add_step(
    name="report",
    prompt_template="""
    Generate report for: {{vulnerability_data.title}}
    Severity: {{vulnerability_data.severity}}
    """
)
```

### Cost Management

Control API costs with intelligent limits:

```python
# Step with cost limit
self.add_step(
    name="expensive_analysis",
    prompt_template="...",
    max_cost=10.0,        # Initial attempt limit
    max_retry_cost=2.0    # Retry attempt limit
)
```

The cost manager:
- Monitors costs in increments
- Prompts Claude to finish efficiently when approaching limit
- Supports different limits for initial vs retry attempts

### Tool Restrictions

Control which tools Claude can use:

```python
# Workflow-level defaults
class SecureWorkflow(AIWorkflow):
    allowed_tools = ["Read", "Write", "Grep"]
    disallowed_tools = ["Bash", "WebFetch"]

# Step-level overrides
self.add_step(
    name="verify",
    prompt_template="...",
    allowed_tools=["Read", "Bash(wake detect *)"],  # Only wake commands
    disallowed_tools=["Write"]  # No file modifications
)
```

### Session Management

Control session behavior:

```python
# Continue session from previous step
self.add_step(
    name="refine",
    prompt_template="Refine your previous analysis...",
    continue_session=True  # Reuse Claude session
)

# Working directory management
workflow = MyWorkflow(
    working_dir="/custom/path",  # Custom working directory
    cleanup_working_dir=False    # Preserve after completion
)
```

## Examples

The `examples/` directory contains working examples:

### Basic Examples

- **[reentrancy](examples/reentrancy/)** - Security detector with Wake integration
- **[reentrancy_test](examples/reentrancy_test/)** - Test generation workflow

### Advanced Examples

- **[hooks](examples/hooks/)** - Workflow customization with pre/post hooks
- **[conditional_test](examples/conditional_test/)** - Conditional step execution
- **[dynamic_steps](examples/dynamic_steps/)** - Runtime step generation
- **[extraction_step](examples/extraction_step/)** - Structured data extraction

Each example includes its own README with detailed explanations.

## API Reference

### Core Classes

#### `AIWorkflow`

Base class for all workflows.

```python
class AIWorkflow:
    def __init__(
        name: str,
        result_class: Type[AIResult] = None,
        working_dir: Union[str, Path] = None,
        allowed_tools: List[str] = None,
        cleanup_working_dir: bool = True
    )
    
    def add_step(
        name: str,
        prompt_template: str,
        tools: List[str] = None,
        validator: Callable = None,
        max_cost: float = None,
        condition: Callable = None
    )
    
    def execute(
        context: Dict[str, Any] = None,
        resume: bool = False
    ) -> Tuple[Dict, AIResult]
```

#### `WorkflowStep`

Individual workflow step configuration.

```python
@dataclass
class WorkflowStep:
    name: str
    prompt_template: str
    allowed_tools: List[str] = None
    validator: Callable = None
    max_cost: float = None
    max_retries: int = 3
    continue_session: bool = False
    condition: Callable = None
```

#### `MarkdownDetector`

Template for simple detectors.

```python
class MarkdownDetector(AIWorkflow):
    @abstractmethod
    def get_detector_prompt(self) -> str:
        """Return the detection prompt."""
        pass
```

### CLI Commands

```bash
# Run workflow
wake-ai <workflow-name> [OPTIONS]

# Common options
--model <opus|sonnet>     # Claude model to use
--resume                  # Resume from saved state
--export <path>          # Export results to JSON
--no-cleanup             # Keep working directory
--help                   # Show help

# Workflow-specific options vary
wake-ai audit --scope contracts/ --focus reentrancy
```

## Best Practices

### Prompt Design

1. **Be Specific**: Clear instructions produce better results
2. **Use Structure**: Break complex tasks into numbered steps
3. **Provide Examples**: Show expected output format
4. **Include Validation**: Specify what makes output valid

### Cost Optimization

1. **Set Reasonable Limits**: Start small, increase as needed
2. **Use Step Conditions**: Skip expensive steps when possible
3. **Validate Early**: Catch errors before expensive operations
4. **Reuse Sessions**: Use `continue_session` for related tasks

### Error Handling

1. **Add Validators**: Ensure output quality
2. **Set Retry Limits**: Balance quality vs cost
3. **Log Progress**: Use working directory for debugging
4. **Handle Interruptions**: Design for resumability

### Security

1. **Limit Tools**: Only allow necessary tools
2. **Validate Inputs**: Check user-provided paths
3. **Review Generated Code**: AI output needs verification
4. **Sandbox Execution**: Run in isolated environments

## Troubleshooting

### Common Issues

**"Claude Code not found"**
- Install: `pip install claude-code`
- Authenticate: `claude-code auth`

**"Validation failed after retries"**
- Check validator logic
- Increase `max_retries`
- Improve prompt clarity

**"Cost limit exceeded"**
- Increase `max_cost`
- Optimize prompts
- Use conditional steps

**"Cannot resume workflow"**
- Check working directory exists
- Verify state file present
- Use same workflow version

### Debug Mode

Run with verbose logging:

```bash
WAKE_AI_DEBUG=1 wake-ai audit
```

Check working directory for:
- Step outputs
- Validation errors
- Cost tracking
- Session state

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development setup and guidelines.

## License

MIT License - see [LICENSE](../LICENSE) for details.