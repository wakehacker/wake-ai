# Dynamic Workflow Implementation Plan

## Summary
Dynamic step generation in AIWorkflow is easily implementable without extensive refactoring by leveraging the existing `_custom_context_update()` hook.

## Implementation Strategy: Use the _custom_context_update Hook

The simplest approach leverages the existing `_custom_context_update()` method that's called after each step completes. Since the execution loop checks `len(self.steps)` on each iteration, we can dynamically add steps during execution.

## Implementation Steps:

1. **Create a custom workflow subclass** that inherits from `AIWorkflow`

2. **Override `_custom_context_update()`** to:
   - Check if the completed step is the "plan generation" step
   - Parse the JSON response containing multiple entries
   - Dynamically create and insert new `WorkflowStep` objects for each entry
   - Add the entry data to the workflow context for each new step

3. **Use `self.steps.insert()`** to add the new steps at position `self.state.current_step + 1`

## Example Code Structure:
```python
class DynamicPlanWorkflow(AIWorkflow):
    def _setup_steps(self):
        # Only define the first step
        self.add_step(
            name="create_plan",
            prompt_template="Generate JSON plan with multiple entries"
        )
    
    def _custom_context_update(self, step_name: str, response: ClaudeCodeResponse):
        if step_name == "create_plan":
            plan_entries = json.loads(response.content)
            
            for idx, entry in enumerate(plan_entries):
                # Create a step for each entry
                step = WorkflowStep(
                    name=f"process_entry_{idx}",
                    prompt_template="Process entry: {entry_data}"
                )
                self.steps.insert(self.state.current_step + 1 + idx, step)
                self.state.context[f"entry_data_{idx}"] = entry
```

## Key Advantages:
- No changes to base `AIWorkflow` class needed
- Works within existing architecture
- Simple and clean implementation
- Maintains workflow state management and resumability