# Dynamic Steps Example

This example demonstrates Wake AI's dynamic step generation capability, which allows workflows to create new steps at runtime based on the results of previous steps.

## Overview

The `DynamicAnalysisWorkflow` shows how to:
1. Run an initial analysis step
2. Generate new steps based on the analysis results
3. Execute the dynamically generated steps
4. Summarize findings from all steps

## How It Works

### 1. Initial Setup
```python
def _setup_steps(self):
    # Regular step
    self.add_step(name="find_classes", ...)
    
    # Register dynamic generator
    self.add_dynamic_steps(
        name="investigate_classes",
        generator=self._generate_class_investigation_steps,
        after_step="find_classes"
    )
    
    # Final step runs after all dynamic steps
    self.add_step(name="summarize", ...)
```

### 2. Dynamic Step Generation
The generator function receives the previous step's response and current context:
```python
def _generate_class_investigation_steps(self, response, context):
    # Parse response to determine what steps to create
    classes = parse_classes(response.content)
    
    # Return list of WorkflowStep objects
    return [
        WorkflowStep(name=f"investigate_{cls}", ...)
        for cls in classes
    ]
```

### 3. Execution Flow
- Step 1/3: find_classes
- (Dynamic steps are generated)
- Step 2/7: investigate_class_0_foo
- Step 3/7: investigate_class_1_bar
- Step 4/7: investigate_class_2_baz
- ...
- Step 7/7: summarize

## Running the Example

```bash
# From wake-ai root directory
python examples/dynamic_steps/dynamic_workflow.py

# Or use with CLI (when integrated)
wake-ai --flow examples.dynamic_steps.dynamic_workflow
```

## Key Features

1. **Flexible Step Generation**: Create 0 to N steps based on runtime data
2. **Independent Sessions**: Each dynamic step can have its own Claude session
3. **Context Sharing**: All steps share the workflow context
4. **Error Handling**: Failed dynamic generation won't crash the workflow

## Important Notes

- **Step Count Changes**: The total step count will change after dynamic steps are added
- **Resume Behavior**: When resuming, dynamically generated steps are preserved
- **Generator Errors**: If the generator fails, execution continues without the dynamic steps

## Use Cases

Dynamic steps are useful for:
- Analyzing multiple files/components discovered at runtime
- Creating per-issue investigation steps
- Generating test cases for each function found
- Building hierarchical analysis workflows
- Processing variable-length lists of items

## Customization

You can customize dynamic steps by:
- Setting different tools per step
- Using `continue_session=True` to maintain context
- Adding validators for each dynamic step
- Setting individual cost limits
- Adding conditions to skip certain dynamic steps