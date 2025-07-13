# Dynamic Workflow Implementation Analysis

## Current Architecture Overview

The `AIWorkflow` class in `wake/ai/flow.py` implements a linear, sequential workflow execution model:

1. **Steps are predefined** in `_setup_steps()` method (line 193)
2. **Execution is sequential** using a while loop (line 233): `while self.state.current_step < len(self.steps)`
3. **Steps are stored** in a list: `self.steps: List[WorkflowStep]` (line 184)

## Key Observation: Dynamic Step Addition is Possible

The execution loop checks `len(self.steps)` on each iteration, which means if we add steps to the list during execution, they will be picked up automatically.

## Implementation Approaches for Dynamic Steps

### Approach 1: Using _custom_context_update Hook (Simplest)

The `_custom_context_update()` method (line 342) is called after each step completes. We can override it to:

```python
def _custom_context_update(self, step_name: str, response: ClaudeCodeResponse):
    if step_name == "generate_plan":
        # Parse JSON from response
        plan_items = json.loads(response.content)
        
        # Insert new steps after current position
        for i, item in enumerate(plan_items):
            step = WorkflowStep(
                name=f"process_item_{i}",
                prompt_template="Process item: {item_data}",
                max_cost=5.0
            )
            # Insert after current step
            self.steps.insert(self.state.current_step + 1 + i, step)
            # Add item data to context
            self.state.context[f"item_data_{i}"] = item
```

**Pros:**
- No changes to base class needed
- Works with existing architecture
- Simple to implement

**Cons:**
- Limited to inserting steps after current step
- All dynamic steps must be defined at once

### Approach 2: Override execute() Method

Create a subclass that overrides the execute method to handle dynamic step generation:

```python
class DynamicWorkflow(AIWorkflow):
    def execute(self, context=None, resume=False):
        # ... initialization code ...
        
        while self.state.current_step < len(self.steps):
            step = self.steps[self.state.current_step]
            
            # Execute step
            response = self._execute_step(step)
            
            # Check if this step generates dynamic steps
            if hasattr(self, f"_generate_steps_for_{step.name}"):
                generator = getattr(self, f"_generate_steps_for_{step.name}")
                new_steps = generator(response)
                # Insert new steps
                for i, new_step in enumerate(new_steps):
                    self.steps.insert(self.state.current_step + 1 + i, new_step)
            
            self.state.current_step += 1
```

**Pros:**
- More flexible control
- Can implement complex logic
- Clean separation of concerns

**Cons:**
- Requires overriding core execute logic
- More code duplication

### Approach 3: Step with Loop Logic

Instead of generating multiple steps, create a single step that internally loops:

```python
def _setup_steps(self):
    self.add_step(
        name="generate_plan",
        prompt_template="Generate a JSON plan for analysis"
    )
    
    self.add_step(
        name="process_all_items",
        prompt_template="Process all items from the plan",
        validator=self._validate_all_items_processed
    )

def _custom_context_update(self, step_name: str, response: ClaudeCodeResponse):
    if step_name == "generate_plan":
        self.state.context["plan_items"] = json.loads(response.content)
    elif step_name == "process_all_items":
        # The AI processes all items in one conversation
        pass
```

**Pros:**
- Simplest implementation
- No dynamic step generation needed
- Works with current architecture as-is

**Cons:**
- Less granular control
- Harder to track individual item progress
- May hit token limits with many items

## Recommended Implementation

For your use case, **Approach 1** using `_custom_context_update` is the best option because:

1. It requires no changes to the base `AIWorkflow` class
2. It's simple to implement and understand
3. It leverages existing hooks in the architecture
4. The execution loop already supports dynamic step addition
5. You can add context data for each generated step

## Example Implementation

```python
class PlanBasedWorkflow(AIWorkflow):
    def _setup_steps(self):
        # Step 1: Generate the plan
        self.add_step(
            name="create_plan",
            prompt_template="Analyze the codebase and create a JSON plan with entries for review",
            max_cost=10.0
        )
        
        # Step 2 will be dynamically generated for each plan entry
    
    def _custom_context_update(self, step_name: str, response: ClaudeCodeResponse):
        if step_name == "create_plan":
            try:
                # Parse the JSON plan
                plan = json.loads(response.content)
                
                # Generate a step for each entry
                for idx, entry in enumerate(plan):
                    step = WorkflowStep(
                        name=f"review_entry_{idx}",
                        prompt_template=(
                            "Review the following entry from the plan:\n"
                            "Entry: {entry_data}\n"
                            "Previous entries reviewed: {completed_entries}"
                        ),
                        max_cost=5.0
                    )
                    
                    # Insert the step after current position
                    insert_pos = self.state.current_step + 1 + idx
                    self.steps.insert(insert_pos, step)
                    
                    # Add entry data to context
                    self.state.context[f"entry_data_{idx}"] = json.dumps(entry)
                    
            except json.JSONDecodeError:
                logger.error("Failed to parse plan JSON")
                raise
```

## Key Insights

1. The workflow architecture is more flexible than it initially appears
2. The execution loop's use of `len(self.steps)` makes dynamic steps possible
3. The `_custom_context_update` hook provides a clean extension point
4. No extensive refactoring is needed - just override one method in a subclass