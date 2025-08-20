# Wake AI

An LLM orchestration framework that wraps terminal-based AI agents (like Claude Code) to provide structured, multi-step workflows for smart contract security analysis and beyond, making agentic execution more predictable and reliable through validation and progressive task decomposition.

![Wake AI](./demo.gif)

## The Problem

Traditional approaches to AI-powered code analysis suffer from unpredictability. You write a prompt, cross your fingers, and hope the AI completes all the work correctly in one go. When working with complex security audits or vulnerability detection, this approach is fundamentally flawed. AI agents are powerful but inherently non-deterministic – they might miss steps, produce inconsistent outputs, or fail partway through execution.

## Our Solution

Wake AI bridges the gap between AI's generalization capabilities and the need for reliable, reproducible results. By breaking complex tasks into discrete steps with validation between each, we achieve:

-   **Predictable Execution**: Each step has clear inputs, outputs, and success criteria
-   **Progressive Validation**: Verify the AI completed necessary work before proceeding
-   **Multi-Agent Collaboration**: Different steps can use specialized agents
-   **Rapid Prototyping**: Test new ideas without building from scratch

## Installation

```bash
pip install wake-ai
```

## Quick Start

```bash
# Run a comprehensive security audit
wake-ai audit

# Detect reentrancy vulnerabilities
wake-ai reentrancy
```

## Why Wake AI?

### 1. **Beyond Static Analysis**

We're entering a new era of vulnerability detection. While traditional detectors rely on pattern matching and static analysis, Wake AI leverages LLMs to understand context, reason about code behavior, and find complex vulnerabilities that rule-based systems miss.

### 2. **Structured Yet Flexible**

The framework provides structure without sacrificing flexibility:

-   Define workflows as a series of steps
-   Each step can use different tools and prompts
-   Validation ensures quality before proceeding
-   Context flows seamlessly between steps

### 3. **Cost-Controlled Execution**

Real-world AI usage requires cost management:

-   Set per-step cost limits
-   Automatic retry with feedback on failures
-   Efficient prompt optimization when approaching limits
-   Track total workflow costs

### 4. **Progress Tracking**

Visual feedback for long-running workflows:

-   Rich progress bars with percentage completion
-   Status messages during retries and validation
-   External progress hooks for app integration

### 5. **Security Workflows Included**

-   Pre-built audit and detector workflows to get you started
-   Standardized detection output format with JSON export
-   Build any workflow you need - security, testing, analysis, or beyond
-   Easy to extend with your own custom workflows

## Core Concepts

### Working Directory

Multi-step AI workflows face a fundamental problem: context sharing. Whether you're using a single agent across all steps or multiple specialized agents, data needs to flow between operations. How does an exploit developer agent access vulnerabilities found by an auditor agent? How does step three know what step one discovered? Traditional approaches would require complex state management or forcing the AI to re-analyze everything.

Wake AI takes a straightforward approach: each workflow gets an isolated working directory where all agents and steps operate. This shared workspace becomes the workflow's persistent memory:

```
.wake/ai/<YYYYMMDD_HHMMSS_random>/
├── state/                 # Workflow state metadata
├── findings.yaml          # Discovered vulnerabilities
├── analysis.md            # Detailed investigation notes
└── report.json            # Final structured output
```

Communication happens through files. One agent writes findings, another reads and validates them. A security auditor documents vulnerabilities, an exploit developer tests them, a report writer consolidates everything. No state passing, no variable juggling - just a shared filesystem that persists across the entire workflow execution. Your project directory remains clean while each agent has full freedom to create, modify, and reference files in this sandbox.

#### Post-Workflow Cleanup

By default, workflows are configured to automatically clean up their working directories after successful completion. This behavior can be overridden either within the `Workflow` class for specific workflows, or on the command line:

```bash
wake-ai --working-dir .audit/ --no-cleanup audit  # Preserve working directory
```

Some workflows might not require structured outputs and instead provide results within the working directory. An example of this could be a specialized `audit` workflow, where the output is written to markdown files in the working directory, which a human auditor can then review after the workflow has finished.

### Validation

To ensure correct output from the entire workflow, each step must produce correct intermediate results. Without validation, AI responses might be unparseable, missing required fields, or contain errors that cascade through subsequent steps.

Each workflow step can include validators to ensure outputs are correct before proceeding. When validation fails, the step automatically retries with error correction prompts until outputs meet requirements.

Example validator:

```python
def validate_findings(self, response):
    # Check if required files were created
    if not (self.working_dir / "findings.yaml").exists():
        return False, ["No findings file created"]

    # Validate YAML structure
    findings = yaml.load(open(self.working_dir / "findings.yaml"))
    if not all(k in findings for k in ["vulnerabilities", "severity"]):
        return False, ["Invalid findings structure"]

    return True, []
```

_Benefits:_

-   **Self-correcting**: AI fixes validation errors automatically
-   **Quality control**: Outputs always meet specifications
-   **No cascading errors**: Invalid outputs won't propagate to subsequent steps
-   **Cost-effective**: Long-running workflows can be terminated early if validation fails
-   **Schema-based output**: Validators enforce specific output formats, enabling parsing of AI responses into structured data for export and integration with other tools

## Architecture

### Workflows and Steps

At its heart, Wake AI treats complex tasks as workflows composed of individual steps:

```python
from wake_ai import AIWorkflow

class MyAuditWorkflow(AIWorkflow):
    def _setup_steps(self):
        # Step 1: Map the codebase structure
        self.add_step(
            name="map_contracts",
            prompt_template="Find all Solidity contracts and identify their relationships...",
            validator=self.validate_mapping,
            max_cost=5.0
        )

        # Step 2: Focus on critical contracts (continues session)
        self.add_step(
            name="analyze_critical",
            prompt_template="Based on the contracts you just mapped, analyze the 3 most critical ones for vulnerabilities...",
            max_cost=10.0,
            continue_session=True  # Needs to remember which contracts were identified
        )
```

_Features:_

-   **Cost control**: If `max_cost` is set, once reaching the limit, the agent will be prompted to quickly finish the step, useful for managing cost-intensive steps.
-   **Session continuation**: `continue_session` controls whether the agent session is continued from the previous step or a new one is created, allowing you to choose between single or multi-agent workflows.
-   **Validator**: Each step can have a validator function which can be used to check if the step has been completed successfully.
-   **Conditional execution**: `condition` can be used to skip the step based on a boolean expression.

**Note**: Steps are executed sequentially. Wake AI does not currently support parallel step execution.

### Context Sharing

Wake AI's primary approach to context sharing is through the _working directory_. Additionally, workflows provide context management methods and the `add_extraction_step` helper function to extract structured data.

```python
from pydantic import BaseModel

class Vulnerability(BaseModel):
    name: str
    description: str
    severity: str
    file: str
    line: int

class VulnerabilitiesList(BaseModel):
    vulnerabilities: List[Vulnerability]

self.add_step(
    name="analyze_critical",
    prompt_template="Analyze the codebase for critical vulnerabilities...",
)

self.add_extraction_step(
    after_step="analyze_critical",
    output_schema=VulnerabilitiesList,
    context_key="vulnerabilities",
)
```

The extracted data will be stored in the `context` state under the key specified in `context_key` (defaults to `<step_name>_data`).

### Context Management

Wake AI workflows provide methods to manage context that flows between steps:

```python
# Add data to context
workflow.add_context("project_name", "MyDeFiProtocol")
workflow.add_context("audit_scope", ["Token.sol", "Vault.sol"])

# Retrieve context data
project = workflow.get_context("project_name")  # "MyDeFiProtocol"
scope = workflow.get_context("audit_scope")     # ["Token.sol", "Vault.sol"]

# Get all available context keys
keys = workflow.get_context_keys()  # ["project_name", "audit_scope", ...]
```

Context includes:

-   User-defined values via `add_context()`
-   Step outputs as `{{step_name}_output}}`
-   Extracted data from `add_extraction_step()` (defaults to `<step_name>_data`, but can be overridden with the `context_key` parameter)
-   Built-in values like `{{working_dir}}` and `{{execution_dir}}`

### Dynamic Prompt Templates

To create dynamic prompt templates, Wake AI utilizes Jinja2 templates, which allow you to pass in context variables in the `{{ context_key }}` format. Workflow classes keep track of their `context` state, where you can store any data you want to pass to the prompt template.

```python
from pydantic import BaseModel

class ContractList(BaseModel):
    contracts: str

class AuditWorkflow(AIWorkflow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Add files to context for use in prompts
        self.add_context("files", list(self.working_dir.glob("**/*.sol")))

    def _setup_steps(self):
        self.add_step(
            name="map_contracts",
            prompt_template="Find all Solidity contracts and identify their relationships. Here are the files in the codebase: {{files}}",
        )

        self.add_step(
            name="determine_focus",
            prompt_template="Determine the top 3 core contracts to focus on for analysis.",
            continue_session=True  # Needs to remember which contracts were identified
        )

        self.add_extraction_step(
            after_step="determine_focus",
            output_schema=ContractList,
            context_key="files_to_focus",
        )

        self.add_step(
            name="analyze_focus",
            prompt_template="Conduct a thorough analysis of the following contracts: {{files_to_focus}}",
            max_cost=10.0,
        )

```

## Creating Custom Detectors

Wake AI makes it trivial to prototype new vulnerability detectors with the `SimpleDetector` helper class:

```python
import rich_click as click
from wake_ai import workflow
from wake_ai.templates import SimpleDetector

@workflow.command("flashloan")
@click.option("--focus-area", "-f", help="Specific area to focus analysis")
def factory(focus_area):
    """Detect flash loan attack vectors."""
    detector = FlashLoanDetector()
    detector.focus_area = focus_area
    return detector

class FlashLoanDetector(SimpleDetector):
    """Flash loan vulnerability detector."""

    focus_area: str = None

    def get_detector_prompt(self) -> str:
        focus_context = f"Focus specifically on: {self.focus_area}" if self.focus_area else ""

        return f"""
        Analyze this codebase for flash loan attack vectors.
        {focus_context}

        Focus on:
        1. Price manipulation opportunities
        2. Unprotected external calls in loan callbacks
        3. Missing reentrancy guards
        4. Incorrect balance assumptions

        For each issue, explain the attack scenario and impact.
        """
```

The helper class automatically parses detector output into a standardized format for CLI display or JSON export.

## Advanced Features

### Dynamic Step Generation

Generate steps based on runtime discoveries:

```python
def generate_file_reviews(response, context):
    # Parse discovered contracts
    contracts = parse_contracts(response.content)

    # Create a review step for each contract
    return [
        WorkflowStep(
            name=f"review_{contract.name}",
            prompt_template=f"Audit {contract.path} for vulnerabilities...",
            max_cost=3.0
        )
        for contract in contracts
    ]

self.add_dynamic_steps("reviews", generate_file_reviews, after_step="scan")
```

### Conditional Execution

Skip expensive steps based on runtime conditions:

```python
self.add_step(
    name="deep_analysis",
    prompt_template="Perform computational analysis...",
    condition=lambda ctx: len(ctx.get("critical_findings", [])) > 0,
    max_cost=20.0
)
```

### Tool Restrictions

Fine-grained control over AI capabilities:

```python
# Only allow specific Wake commands
allowed_tools = ["Read", "Write", "Bash(wake detect *)", "Bash(wake init)"]

# Prevent any modifications
self.add_step(
    name="review_only",
    prompt_template="Review the code...",
    disallowed_tools=["Write", "Edit", "Bash"]
)
```

## Real-World Example: Security Audit Workflow

Our production audit workflow demonstrates the framework's power:

1. **Initial Analysis** - Map attack surface and identify focus areas
2. **Vulnerability Hunting** - Deep dive with specialized prompts
3. **Report Generation** - Professional audit documentation

Each step validates outputs, ensuring no critical checks are missed.

## Documentation

See [docs/README.md](docs/README.md) for:

-   Complete API reference
-   Step-by-step tutorials
-   Advanced workflow patterns
-   Integration guides

## License

ISC
