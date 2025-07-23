# Conditional Workflow Example

This example demonstrates how to create workflows with conditional steps that only execute when certain conditions are met.

## Features Demonstrated

1. **Lambda conditions** - Simple inline conditions for straightforward checks
2. **Class method conditions** - More complex conditions with access to instance state
3. **Context-based decisions** - Steps that adapt based on previous results
4. **State tracking** - Automatic tracking of which steps were completed vs skipped

## Usage

```python
from examples.conditional_test.conditional_workflow import ConditionalWorkflow

# Create workflow with threshold of 10 files
workflow = ConditionalWorkflow(threshold=10)

# Execute the workflow
results, formatted = workflow.execute()

# Check which steps ran
print(f"Completed: {results['completed_steps']}")
print(f"Skipped: {results['skipped_steps']}")
```

## How It Works

1. The workflow analyzes the codebase and counts Python files
2. If file count > threshold: runs large project analysis (skips small)
3. If file count <= threshold: runs small project analysis (skips large)
4. Always generates a summary showing what was executed

This pattern is useful for:
- Security workflows that only fix critical issues
- Build workflows that skip steps based on file changes
- Analysis workflows that adapt to project size/complexity
- Any workflow where steps depend on runtime conditions