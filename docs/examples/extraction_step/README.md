# Extraction Step Example

This example demonstrates how to use extraction steps in Wake AI workflows to automatically extract structured data from AI responses.

## Overview

The extraction step feature allows you to:
1. Let AI focus on the main task without worrying about output format
2. Extract structured data in a separate step using Pydantic schemas
3. Automatically parse and validate the extracted data
4. Use the parsed data in subsequent steps

## Example Workflow

The example workflow analyzes Python code for potential issues and extracts them as structured data:

1. **analyze** - Analyzes the code for issues (no format constraints)
2. **analyze_extract** - Extracts the issues as structured JSON
3. **summarize** - Uses the extracted data to create a summary

## Where Extracted Data is Stored

When you use `add_extraction_step()`, the parsed data is automatically stored in the workflow context:

```python
# Default behavior: data is stored with key "{step_name}_data"
self.add_extraction_step(
    after_step="analyze",
    output_schema=IssuesList
)
# Creates extraction step named "analyze_extract"
# Stores parsed data in context["analyze_data"]

# Custom context key: specify where to store the data
self.add_extraction_step(
    after_step="analyze",
    output_schema=IssuesList,
    context_key="my_issues"  # Custom key
)
# Stores parsed data in context["my_issues"]

# Custom step name and context key
self.add_extraction_step(
    after_step="analyze",
    output_schema=IssuesList,
    name="extract_issues",  # Custom step name
    context_key="found_issues"  # Custom context key
)
# Creates step named "extract_issues"
# Stores parsed data in context["found_issues"]
```

### Accessing Extracted Data

In subsequent steps, you can access the parsed Pydantic objects:

```python
# In prompt templates using Jinja2
prompt_template="""
Found {{analyze_data.issues|length}} issues.
First issue: {{analyze_data.issues[0].description}}
"""

# In dynamic step generators or post-step hooks
def _generate_fix_steps(self, response, context):
    issues = context["analyze_data"]  # This is the parsed IssuesList object
    for issue in issues.issues:
        # Work with strongly-typed Pydantic objects
        print(f"Issue: {issue.type} at {issue.file}:{issue.line}")
```

## Running the Example

```bash
# Run the extraction example workflow
wake-ai --flow examples.extraction_step.extraction_workflow

# With a specific file
wake-ai --flow examples.extraction_step.extraction_workflow -f example_code.py
```

## Key Features Demonstrated

- Using `add_extraction_step()` to add automatic extraction
- Defining Pydantic models for structured data
- Default vs custom context keys for storing extracted data
- Accessing parsed data in subsequent steps
- Automatic validation and retry on schema errors