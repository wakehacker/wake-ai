# Conditional Steps in Wake AI Workflows

The conditional steps feature allows you to skip workflow steps based on runtime conditions. This is useful for creating dynamic workflows that adapt based on intermediate results.

## Basic Usage

Add a `condition` parameter to any step with a function that takes the context and returns a boolean:

```python
self.add_step(
    name="fix_criticals",
    prompt_template="Fix critical vulnerabilities",
    condition=lambda ctx: len(ctx.get("critical_issues", [])) > 0
)
```

The step will only execute if the condition returns `True`. If it returns `False`, the step is skipped and marked in the workflow state.

## Using Class Methods as Conditions

For more complex conditions or better code organization, you can use class methods:

```python
class MyWorkflow(AIWorkflow):
    def _setup_steps(self):
        # Using lambda for simple conditions
        self.add_step(
            name="simple_check",
            prompt_template="...",
            condition=lambda ctx: ctx.get("value") > 10
        )
        
        # Using class method for complex conditions
        self.add_step(
            name="complex_check", 
            prompt_template="...",
            condition=self._should_run_complex_check
        )
    
    def _should_run_complex_check(self, context: Dict[str, Any]) -> bool:
        """Complex condition with access to instance state."""
        # Can access self.state, self.threshold, etc.
        has_issues = len(context.get("issues", [])) > 0
        is_critical = context.get("severity") == "critical"
        has_budget = self.state.total_cost < self.max_budget
        
        return has_issues and is_critical and has_budget
```

### Benefits of Class Methods

1. **Better readability** - Named methods are self-documenting
2. **Access to instance state** - Can use `self.state`, instance variables
3. **Easier testing** - Methods can be unit tested independently
4. **Complex logic** - Multi-line conditions without cramming into lambdas
5. **Reusability** - Same condition can be used for multiple steps

## Example: Security Audit with Conditional Fixes

```python
class SecurityAuditWorkflow(AIWorkflow):
    def _setup_steps(self):
        # Step 1: Run security analysis
        self.add_step(
            name="analyze",
            prompt_template="Run security analysis and categorize issues by severity"
        )
        
        # Step 2: Only fix critical issues if found
        self.add_step(
            name="fix_critical",
            prompt_template="Generate fixes for critical security issues: {{critical_issues}}",
            condition=lambda ctx: len(ctx.get("critical_issues", [])) > 0
        )
        
        # Step 3: Only document medium severity issues if found
        self.add_step(
            name="document_medium",
            prompt_template="Document medium severity issues for manual review",
            condition=lambda ctx: len(ctx.get("medium_issues", [])) > 0
        )
```

## Complex Conditions

Conditions can check multiple context values:

```python
# Skip if no issues OR if auto-fix is disabled
condition=lambda ctx: (
    len(ctx.get("issues", [])) > 0 and 
    ctx.get("auto_fix_enabled", True)
)
```

## Accessing Step Status

The workflow tracks which steps were completed vs skipped:

```python
results, formatted = workflow.execute()
print(f"Completed: {results['completed_steps']}")
print(f"Skipped: {results['skipped_steps']}")
```

## Integration with Other Features

Conditional steps work seamlessly with:
- Dynamic steps
- Extraction steps  
- Step validation
- Cost limits
- Session continuation

## Implementation Notes

- Steps are evaluated in order
- Skipped steps don't consume Claude API calls
- Context from skipped steps is not available to later steps
- Workflow state persistence includes skipped step tracking
- The `condition` function should be fast and not perform heavy computation