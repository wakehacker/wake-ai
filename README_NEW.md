# Wake AI

A deterministic framework for AI-powered smart contract security analysis.

## What is Wake AI?

Wake AI is a wrapper framework for terminal-based AI agents (currently Claude Code, with future support for other CLI tools) that transforms how we approach smart contract analysis. Instead of relying on single prompts and hoping for the best, Wake AI introduces a systematic, multi-step approach to AI execution while preserving the reasoning capabilities that make LLMs powerful.

### The Problem We're Solving

Traditional approaches to AI-powered code analysis suffer from unpredictability. You write a prompt, cross your fingers, and hope the AI completes all the work correctly in one go. When working with complex security audits or vulnerability detection, this approach is fundamentally flawed. AI agents are powerful but inherently non-deterministic – they might miss steps, produce inconsistent outputs, or fail partway through execution.

### Our Solution: Deterministic AI Workflows

Wake AI bridges the gap between AI's generalization capabilities and the need for reliable, reproducible results. By breaking complex tasks into discrete steps with validation between each one, we achieve:

- **Predictable Execution**: Each step has clear inputs, outputs, and success criteria
- **Progressive Validation**: Verify the AI completed necessary work before proceeding
- **Multi-Agent Collaboration**: Different steps can use specialized agents
- **Rapid Prototyping**: Test new ideas without building from scratch

## Installation

```bash
pip install wake-ai
```

## Quick Start

```bash
# Run a comprehensive security audit
wake-ai audit

# Detect Uniswap-specific vulnerabilities
wake-ai uniswap

# Resume an interrupted workflow
wake-ai --resume
```

## Why Wake AI?

### 1. **Beyond Static Analysis**

We're entering a new era of vulnerability detection. While traditional detectors rely on pattern matching and static analysis, Wake AI leverages LLMs to understand context, reason about code behavior, and find complex vulnerabilities that rule-based systems miss.

### 2. **Structured Yet Flexible**

The framework provides structure without sacrificing flexibility:
- Define workflows as a series of steps
- Each step can use different tools and prompts
- Validation ensures quality before proceeding
- Context flows seamlessly between steps

### 3. **Cost-Controlled Execution**

Real-world AI usage requires cost management:
- Set per-step cost limits
- Automatic retry with feedback on failures
- Efficient prompt optimization when approaching limits
- Track total workflow costs

### 4. **Built for Security Professionals**

Designed specifically for smart contract security:
- Pre-built audit workflows following industry best practices
- Standardized detection output format
- Integration with existing Wake tools
- Export to common security report formats

## Core Architecture

### Workflows and Steps

At its heart, Wake AI treats complex tasks as workflows composed of individual steps:

```python
from wake_ai import AIWorkflow

class MyAuditWorkflow(AIWorkflow):
    def _setup_steps(self):
        # Step 1: Understand the codebase
        self.add_step(
            name="analyze",
            prompt_template="Analyze the smart contract architecture...",
            tools=["Read", "Grep"],
            validator=self.validate_analysis,
            max_cost=5.0
        )

        # Step 2: Deep dive into findings
        self.add_step(
            name="investigate",
            prompt_template="Based on your analysis: {{analyze_output}}...",
            tools=["Read", "Write"],
            max_cost=10.0
        )
```

### Multi-Agent Execution

Each step can run in a fresh session, enabling specialized agents:

```python
# Auditor agent for initial analysis
self.add_step(name="audit", prompt_template="You are a security auditor...")

# Exploit developer agent for validation
self.add_step(name="exploit", prompt_template="You are an exploit developer...",
              continue_session=False)  # Fresh agent

# Report writer agent for documentation
self.add_step(name="report", prompt_template="You are a technical writer...")
```

### Validation and Quality Control

Ensure each step produces expected outputs:

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

## Creating Custom Detectors

Wake AI makes it trivial to prototype new vulnerability detectors:

```python
from wake_ai.templates import MarkdownDetector

class FlashLoanDetector(MarkdownDetector):
    name = "flashloan"

    def get_detector_prompt(self) -> str:
        return """
        Analyze this codebase for flash loan attack vectors.

        Focus on:
        1. Price manipulation opportunities
        2. Unprotected external calls in loan callbacks
        3. Missing reentrancy guards
        4. Incorrect balance assumptions

        For each issue, explain the attack scenario and impact.
        """
```

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

Skip expensive steps when not needed:

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
3. **Validation** - Verify findings aren't false positives
4. **Report Generation** - Professional audit documentation

Each step validates outputs, ensuring no critical checks are missed.

## The Future of Security Analysis

Wake AI represents a paradigm shift in how we approach smart contract security. By combining the pattern recognition of traditional tools with the reasoning capabilities of AI, we're able to:

- Find novel vulnerability classes
- Understand complex cross-contract interactions
- Generate proof-of-concept exploits
- Produce comprehensive audit reports

All while maintaining the reproducibility and reliability that security professionals demand.

## Documentation

See [docs/README.md](docs/README.md) for:
- Complete API reference
- Step-by-step tutorials
- Advanced workflow patterns
- Integration guides

## License

MIT