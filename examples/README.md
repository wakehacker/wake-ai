# Wake AI Examples

This directory contains educational examples demonstrating various Wake AI features and best practices.

## Available Examples

### 1. Reentrancy Detector (`reentrancy/`)

A comprehensive security detector that shows how to:
- Build on top of Wake's static analysis capabilities
- Structure prompts for complex analysis tasks
- Validate and verify findings to eliminate false positives
- Output results in Wake AI's standard detection format

**Key Concepts Demonstrated:**
- Integration with external tools (`wake detect`)
- Multi-phase analysis workflow
- Structured prompt design with validation requirements
- Result formatting and severity classification

**Usage:**
```bash
# Run the detector
wake-ai reentrancy

# Export findings
wake-ai reentrancy --export reentrancy-findings.json
```

### 2. Workflow Hooks (`hooks/`)

Demonstrates the workflow hook system for monitoring and customization:
- Pre-step hooks for setup and context modification
- Post-step hooks for metrics collection
- Dynamic context injection based on workflow state
- Performance tracking and telemetry

**Key Concepts Demonstrated:**
- Workflow-level `_pre_step_hook()` and `_post_step_hook()`
- Direct context modification via `self.state.context`
- Metrics collection and persistence
- Step execution tracking

**Usage:**
```bash
# Run the example
wake-ai hook-example
```

## Learning Path

For developers new to Wake AI, we recommend exploring the examples in this order:

1. **Start with hooks example** - Understanding the execution model
2. **Study the reentrancy detector** - Learn structured prompt design
3. **Review the audit workflow** - See a production-ready implementation

## Creating Your Own Detector

After studying these examples, you can create your own detector by:

1. Inheriting from `MarkdownDetector` for simple single-step detectors
2. Inheriting from `AIWorkflow` for complex multi-step workflows
3. Following the prompt structure patterns shown in the examples
4. Using appropriate validation to ensure output quality

## Best Practices Demonstrated

### Prompt Design
- Clear task definitions with `<task>` sections
- Structured steps with specific instructions
- Validation requirements for quality control
- Explicit output format specifications

### Workflow Architecture
- Proper use of working directories
- Context passing between steps
- Cost management with limits
- Tool selection for each step

### Integration Patterns
- Leveraging Wake's built-in tools
- Combining static and AI analysis
- Progressive refinement of findings
- False positive elimination

See individual example READMEs for detailed documentation.