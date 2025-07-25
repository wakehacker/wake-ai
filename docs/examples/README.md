# Wake AI Examples

This directory contains educational examples demonstrating various Wake AI features and best practices.

## Available Examples

### 1. Conditional Workflow (`conditional_workflow.py`)

Shows how to use conditional step execution based on runtime state:
- Skip expensive analysis steps when no issues are found
- Dynamic workflow paths based on context
- Efficient resource usage with conditional logic

**Key Concepts:**
- `condition` parameter in `add_step()`
- Lambda functions for runtime evaluation
- Context-based decision making

### 2. Dynamic Workflow (`dynamic_workflow.py`)

Demonstrates runtime step generation based on discoveries:
- Generate analysis steps for each discovered contract
- Dynamic workflow expansion
- Adaptive analysis depth

**Key Concepts:**
- `add_dynamic_steps()` method
- Generator functions that create steps at runtime
- Context-aware step generation

### 3. Extraction Workflow (`extraction_workflow.py`)

Shows structured data extraction from AI responses:
- Extract data into Pydantic models
- Type-safe parsing and validation
- Context storage of extracted data

**Key Concepts:**
- `add_extraction_step()` method
- Pydantic schema integration
- Automatic retry on validation failure

### 4. Hooks Workflow (`hooks_workflow.py`)

Demonstrates the workflow hook system for monitoring and customization:
- Pre-step hooks for setup and context modification
- Post-step hooks for metrics collection
- Performance tracking and telemetry

**Key Concepts:**
- Workflow-level `_pre_step_hook()` and `_post_step_hook()`
- Direct context modification via `self.state.context`
- Metrics collection and persistence

## Learning Path

For developers new to Wake AI, we recommend exploring the examples in this order:

1. **Start with hooks workflow** - Understanding the execution model
2. **Study conditional workflow** - Learn flow control
3. **Explore extraction workflow** - Structured data parsing
4. **Review dynamic workflow** - Advanced runtime adaptation

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

## Running the Examples

These examples are for educational purposes. To run them in a real project:

1. Copy the workflow class to your project
2. Adapt the prompts and steps to your specific needs
3. Register with Wake AI CLI or use programmatically:

```python
from docs.examples.conditional_workflow import ConditionalWorkflow

# Create and execute
workflow = ConditionalWorkflow(name="my_analysis")
results, formatted = workflow.execute()
```