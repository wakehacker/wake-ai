# Hook Example Workflow

This workflow demonstrates how to use pre/post step hooks in Wake AI workflows.

## Features Demonstrated

### Workflow-Level Hooks

Wake AI provides two workflow-level hooks that are called for every step:

- `_pre_step_hook(step)`: Called before each step execution
- `_post_step_hook(step, response)`: Called after each step execution

These hooks can directly modify `self.state.context` and access all workflow state.

### Use Cases

#### 1. Logging and Monitoring
```python
def _pre_step_hook(self, step: WorkflowStep) -> None:
    logger.info(f"Starting step '{step.name}'")
    self.step_start_times[step.name] = datetime.now()
```

#### 2. Dynamic Context Modification
```python
def _pre_step_hook(self, step: WorkflowStep) -> None:
    # Add dynamic context based on step
    if step.name == "generate_report":
        self.state.context["timestamp"] = datetime.now().isoformat()
        self.state.context["total_cost"] = sum(self.step_costs.values())
```

#### 3. Metrics Collection
```python
def _post_step_hook(self, step: WorkflowStep, response: ClaudeCodeResponse) -> None:
    # Track metrics
    duration = (datetime.now() - self.step_start_times[step.name]).total_seconds()
    
    # Save to file
    metrics = {
        "step": step.name,
        "cost": response.cost,
        "duration_seconds": duration,
        "success": response.success
    }
    self._save_metrics(metrics)
```

## Running the Example

```bash
wake-ai hook-example
```

This will:
1. Analyze project structure
2. Count files by extension
3. Generate a report with dynamically added context (timestamp, costs, step counters)

The workflow demonstrates:
- Tracking step execution times
- Collecting cost metrics
- Dynamically adding context for specific steps
- Saving metrics to `metrics.json`

Check the working directory for:
- `structure.txt` - Project structure analysis
- `file_count.txt` - File extension statistics
- `report.md` - Final report with dynamic context
- `metrics.json` - Step execution metrics