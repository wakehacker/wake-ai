# Reentrancy Detector Example

This example demonstrates how to create a comprehensive security detector that combines Wake's static analysis with AI-powered verification.

## Overview

The reentrancy detector showcases several advanced patterns:
- Integration with Wake's built-in detectors
- Multi-phase analysis workflow
- False positive elimination
- Structured output formatting

## How It Works

### 1. Static Analysis Integration

The detector first runs Wake's built-in reentrancy detection:
```bash
wake init
wake detect reentrancy
```

This provides a baseline of potential vulnerabilities using proven static analysis techniques.

### 2. AI-Powered Verification

For each finding from Wake, the AI performs:
- **Context Analysis**: Reviews the complete function implementation
- **Call Flow Tracing**: Maps external calls and state changes
- **Exploitability Assessment**: Determines if the issue is actually exploitable

### 3. Enhanced Detection

Beyond Wake's findings, the AI looks for:
- Cross-function reentrancy patterns
- Read-only reentrancy vulnerabilities
- ERC777/1155 callback vulnerabilities
- Complex multi-contract reentrancy

## Key Learning Points

### Structured Prompt Design

The detector uses a clear prompt structure:
```markdown
<task>
Define the high-level objective
</task>

<context>
Provide background and approach
</context>

<steps>
Detailed instructions for each phase
</steps>

<validation_requirements>
Quality criteria and false positive checks
</validation_requirements>

<output_format>
Exact YAML structure with examples
</output_format>
```

### Combining Tools

The example shows how to effectively combine:
- Command-line tools (Wake CLI)
- File analysis (Read, Grep)
- Result generation (Write)

### Output Quality

Each finding includes:
- Clear vulnerability description
- Severity assessment with justification
- Exact code location and snippet
- Concrete remediation steps

## Usage

```bash
# Run the detector
wake-ai reentrancy

# With specific target files
wake-ai reentrancy -t contracts/Vault.sol

# Export results
wake-ai reentrancy --export findings.json
```

## Extending This Example

You can adapt this pattern for other vulnerability types:
1. Replace Wake's detector command with relevant tools
2. Adjust the analysis steps for the vulnerability type
3. Update validation requirements
4. Modify the output format as needed

## Code Structure

The detector is implemented as a single file inheriting from `MarkdownDetector`:

```python
class ReentrancyDetector(MarkdownDetector):
    name = "reentrancy"
    
    def get_detector_prompt(self) -> str:
        return """..."""  # Full structured prompt
```

This simple structure makes it easy to create new detectors by focusing on the prompt content rather than boilerplate code.