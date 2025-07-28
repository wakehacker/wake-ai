# Wake AI Flow Validation Alignment Guide

## Core Principle: Prompt-Validator Alignment

The most critical aspect of creating reliable Wake AI workflows is ensuring perfect alignment between what you ask the AI to produce in prompts and what you validate in the validator functions.

## Common Pitfalls

### 1. **Format Mismatch**
**Problem**: Asking for one format in the prompt but checking for a different format in the validator.

**Example from Audit Workflow**:
- **Prompt asks for**: 
  ```markdown
  | Impact   | High Confidence | Medium Confidence | Low Confidence | Total |
  ```
- **Validator checks for**: 
  ```python
  if "| Severity | Count |" not in content:
  ```

**Solution**: Always copy the exact format from your prompt into your validator.

### 2. **Vague Error Messages**
**Problem**: Error messages that don't explain what the AI should fix.

**Bad Example**:
```python
errors.append("Missing severity findings table in executive-summary.md")
```

**Good Example**:
```python
errors.append("Missing findings table. The report must include a table with the following header: | Impact | High Confidence | Medium Confidence | Low Confidence | Total |")
```

### 3. **Missing Validation Context**
**Problem**: Not providing the AI with enough information to understand what went wrong.

**Solution**: Include specific examples in error messages:
```python
errors.append(f"Missing required section '## Summary of Findings'. The report must contain this exact section header followed by the impact/confidence table.")
```

## Best Practices

### 1. **Exact String Matching**
When your prompt specifies exact text (like headers or table formats), use those exact strings in validation:

```python
# If prompt says: "## Audit Overview"
if "## Audit Overview" not in content:  # Exact match
    errors.append("Missing required section '## Audit Overview' (exact match required)")
```

### 2. **Structural Validation**
For complex structures like YAML or tables, validate both presence and format:

```python
def validate_findings_table(content: str) -> List[str]:
    errors = []
    
    # Check for table presence
    if "| Impact" not in content:
        errors.append("Missing findings table. Expected table starting with: | Impact | High Confidence | ...")
        return errors
    
    # Validate table structure
    required_headers = ["Impact", "High Confidence", "Medium Confidence", "Low Confidence", "Total"]
    header_line = next((line for line in content.split('\n') if line.startswith("| Impact")), None)
    
    if header_line:
        for header in required_headers:
            if header not in header_line:
                errors.append(f"Table missing required column: {header}")
    
    return errors
```

### 3. **Actionable Error Messages**
Every error message should tell the AI exactly what to do:

```python
# Bad
errors.append("Invalid YAML structure")

# Good
errors.append("Invalid YAML in plan.yaml. Each contract must have 'name' and 'issues' fields. Example:\ncontracts:\n  - name: 'Contract.sol'\n    issues: []")
```

### 4. **Progressive Validation**
Check prerequisites before detailed validation:

```python
def validate_report(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
    errors = []
    
    # First check file exists
    report_file = self.working_dir / "report.md"
    if not report_file.exists():
        errors.append(f"Report file not created. Expected file at: {report_file}")
        return (False, errors)  # Stop here if file doesn't exist
    
    # Then check content
    content = report_file.read_text()
    if len(content) < 100:
        errors.append("Report too short. Minimum 100 characters required.")
        return (False, errors)
    
    # Finally check specific requirements
    # ...
```

### 5. **Prompt-Validator Synchronization**
Always update validators when changing prompts:

```python
class MyWorkflow(AIWorkflow):
    def _setup_steps(self):
        # When you define the prompt, immediately think about validation
        self.add_step(
            name="analyze",
            prompt_template="""
            Create analysis.yaml with structure:
            findings:
              - type: [high|medium|low]
                description: "..."
            """,
            validator=self._validate_analysis  # Must check for exact structure
        )
    
    def _validate_analysis(self, response):
        errors = []
        # Validator must check for EXACTLY what prompt asks for
        # - File named "analysis.yaml" 
        # - Key named "findings"
        # - Type field with values high|medium|low
        # - Description field
```

## Validation Error Message Templates

### Critical Rule: Always Specify Which File to Fix

Every error message about file content MUST include the file path where the fix should be made.

### For Missing Files
```python
errors.append(f"Required file '{filename}' not created at {expected_path}. The prompt asks you to create this file with {brief_description}")
```

### For Missing Sections
```python
errors.append(f"Missing required section '{section_name}' in {file_path}. The document must include this exact section header.")
```

### For Invalid Format
```python
errors.append(f"Invalid {format_type} format in {file_path}. Expected: {example}. Found: {actual[:50]}...")
```

### For Missing Fields
```python
errors.append(f"Missing required field '{field}' in {file_path} at {context}. Each {item_type} must have: {', '.join(required_fields)}")
```

### For Table Issues
```python
errors.append(f"Missing table in {file_path}. The file must include a table with header: | Column1 | Column2 | ...")
```

## Workflow Development Process

1. **Write the Prompt First**
   - Define exact output format
   - Include examples in the prompt
   - Specify file names and locations

2. **Extract Validation Requirements**
   - List every file that should be created
   - Note exact section headers
   - Identify required fields/structure
   - Copy exact strings from prompt

3. **Write Validator**
   - Check each requirement from step 2
   - Use exact strings from prompt
   - Provide helpful error messages
   - Include examples in errors

4. **Test and Iterate**
   - Run the workflow
   - When validation fails, check error clarity
   - Update error messages to be more helpful
   - Ensure prompt and validator stay in sync

## Example: Fixing the Audit Workflow

### Original Problem
- Prompt asks for impact/confidence table
- Validator checks for severity/count table
- Error message doesn't explain what's needed

### Solution
```python
def _validate_executive_summary(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
    errors = []
    
    summary_file = Path(self.working_dir) / "executive-summary.md"
    if not summary_file.exists():
        errors.append(f"Executive summary not created at {summary_file}")
    else:
        content = summary_file.read_text()
        
        # Check for the EXACT table format from the prompt
        if "| Impact" not in content or "| High Confidence" not in content:
            errors.append(
                f"Missing findings table in {summary_file}. The executive summary must include a table with header: "
                "| Impact | High Confidence | Medium Confidence | Low Confidence | Total |"
            )
        
        # Check for table separator
        if "| Impact" in content and "|----" not in content:
            errors.append(f"Findings table missing separator line in {summary_file} (|------|...)")
```

## Checklist for Validation Alignment

- [ ] Every output file in prompt has a validation check
- [ ] Every required section in prompt is validated
- [ ] Table headers in validator match prompt exactly  
- [ ] YAML/JSON structure in validator matches prompt examples
- [ ] Error messages reference the prompt requirements
- [ ] Error messages include correct examples
- [ ] Validator uses exact strings from prompt (no paraphrasing)
- [ ] File paths in errors match {{working_dir}} usage in prompt