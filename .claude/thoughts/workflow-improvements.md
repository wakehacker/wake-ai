# Wake AI Workflow Enhancements: Consolidated Design Document

This document consolidates all proposed enhancements for Wake AI workflows, combining ideas from dynamic steps, extraction steps, and practical improvements.

## Table of Contents
1. [Overview](#overview)
2. [Dynamic Steps Design](#dynamic-steps-design)
3. [Extraction Steps Design](#extraction-steps-design)
4. [Step Helpers Design](#step-helpers-design)
5. [Unified Technical Specification](#unified-technical-specification)
6. [Practical Workflow Improvements](#practical-workflow-improvements)
7. [Implementation Roadmap](#implementation-roadmap)

## Overview

The Wake AI framework needs enhancements in three key areas:
1. **Dynamic Steps** - Gefnerate workflow steps at runtime based on previous results
2. **Extraction Steps** - Separate AI task execution from structured data extraction
3. **Workflow Improvements** - Common patterns, debugging, and execution limits

All proposals follow these principles:
- No breaking changes to existing workflows
- Minimal new concepts
- Build on existing patterns
- Type safety with Pydantic
- Clean, intuitive APIs

## Dynamic Steps Design

### Problem Statement
Currently, workflow steps in Wake AI are static - they're defined in `_setup_steps()` and executed sequentially. While we can technically modify `self.steps` during execution, we need a cleaner, more intuitive design pattern for dynamic step injection.

**Use Case Example**:
1. First step analyzes codebase for issues
2. Based on results, create one step per issue found
3. Final step summarizes all findings

### Current Architecture
- Steps stored in `self.steps: List[WorkflowStep]`
- Sequential execution with `self.state.current_step` tracking
- Hooks available: `_pre_step_hook()` and `_post_step_hook()`

### Design Options Considered

#### Option 1: Enhanced Post-Step Hook (Simplest)
Modify steps list directly in `_post_step_hook`:

```python
def _post_step_hook(self, step: WorkflowStep, response: ClaudeCodeResponse):
    if step.name == "analyze_issues":
        issues = self._parse_issues(response.content)
        insert_idx = next(i for i, s in enumerate(self.steps) if s.name == "summarize")

        for i, issue in enumerate(issues):
            issue_step = WorkflowStep(
                name=f"investigate_issue_{i}",
                prompt_template=f"Investigate issue: {issue}",
                # ... other params
            )
            self.steps.insert(insert_idx + i, issue_step)
```

**Pros**: Minimal changes, uses existing infrastructure
**Cons**: Modifies steps list during execution (though this works fine)

#### Option 2: Step Factory Method (Recommended) ⭐
Add a method for registering dynamic step generators:

```python
class AIWorkflow(ABC):
    def add_dynamic_steps(self, after_step: str, step_generator: Callable):
        """Add a dynamic step generator that runs after a specific step."""
        self._dynamic_generators = getattr(self, '_dynamic_generators', {})
        self._dynamic_generators[after_step] = step_generator

    def _post_step_hook(self, step: WorkflowStep, response: ClaudeCodeResponse):
        if hasattr(self, '_dynamic_generators') and step.name in self._dynamic_generators:
            new_steps = self._dynamic_generators[step.name](response, self.state.context)
            insert_idx = self.state.current_step + 1
            for i, new_step in enumerate(new_steps):
                self.steps.insert(insert_idx + i, new_step)
```

**Usage**:
```python
def _setup_steps(self):
    self.add_step("analyze", ...)
    self.add_dynamic_steps("analyze", self._generate_issue_steps)
    self.add_step("summarize", ...)

def _generate_issue_steps(self, response, context):
    issues = parse_issues(response.content)
    return [WorkflowStep(name=f"issue_{i}", ...) for i, issue in enumerate(issues)]
```

**Pros**: Clean API, explicit intent, minimal new infrastructure
**Cons**: Requires new method and attribute

#### Option 3: Step Templates (Most Flexible)
Define reusable step templates:

```python
class StepTemplate:
    def __init__(self, name_pattern: str, prompt_template: str, **kwargs):
        self.name_pattern = name_pattern
        self.prompt_template = prompt_template
        self.kwargs = kwargs

    def instantiate(self, **context) -> WorkflowStep:
        return WorkflowStep(
            name=self.name_pattern.format(**context),
            prompt_template=self.prompt_template.format(**context),
            **self.kwargs
        )
```

**Pros**: Very flexible, reusable templates
**Cons**: More complex, introduces new concept

### Recommendation
**Option 2 (Step Factory Method)** provides the best balance of simplicity and functionality:
- Minimal changes to existing code
- Clear, explicit API
- Easy to understand and use
- Maintains backward compatibility
- Follows existing patterns (similar to `add_step()`)

### Implementation Notes
- Dynamic steps maintain all features (validation, retries, cost limits)
- State saving/loading works automatically
- No changes needed to execution logic
- Could also support conditional steps with similar pattern

## Extraction Steps Design

### Problem Statement
We want to:
1. Let AI focus on the task without output format concerns
2. Extract structured data AFTER task completion
3. Automate the extraction process without manual prompting
4. Keep the workflow clean and intuitive

### Recommended Approach: Automatic Extraction Steps

#### API Design
```python
def add_extraction_after(
    self,
    step_name: str,
    output_schema: Type[BaseModel],
    extract_prompt: Optional[str] = None,  # Custom prompt if needed
    name_suffix: str = "_extract"
):
    """Add an automatic extraction step after a given step."""
```

#### Usage Example
```python
def _setup_steps(self):
    # Main work step - no format concerns
    self.add_step(
        name="analyze",
        prompt_template="Analyze the codebase for security vulnerabilities",
        max_cost=5.0
    )

    # Automatic extraction step (inserted after 'analyze')
    self.add_extraction_after(
        step_name="analyze",
        output_schema=IssuesList
    )

    # Register dynamic steps that use the extracted data
    self.add_dynamic_steps("analyze_extract", self._create_issue_steps)

    # Summary
    self.add_step("summarize", ...)
```

#### Implementation
```python
def add_extraction_after(
    self,
    step_name: str,
    output_schema: Type[BaseModel],
    extract_prompt: Optional[str] = None,
    name_suffix: str = "_extract"
):
    """Add automatic extraction step after specified step."""

    # Default extraction prompt if none provided
    if extract_prompt is None:
        extract_prompt = """Based on your previous analysis, output the findings as JSON.

Schema:
{{schema_description}}

Example:
{{schema_example}}

Output only valid JSON, no additional text."""

    # Create extraction step
    extraction_step = WorkflowStep(
        name=f"{step_name}{name_suffix}",
        prompt_template=extract_prompt,
        continue_session=True,  # Always continue from previous
        validator=self._create_schema_validator(output_schema),
        max_retries=3,
        max_cost=0.5  # Extraction should be cheap
    )

    # Find position to insert (right after the target step)
    insert_pos = None
    for i, step in enumerate(self.steps):
        if step.name == step_name:
            insert_pos = i + 1
            break

    if insert_pos is None:
        raise ValueError(f"Step '{step_name}' not found")

    # Insert extraction step
    self.steps.insert(insert_pos, extraction_step)

    # Store schema for automatic parsing
    self._extraction_schemas[f"{step_name}{name_suffix}"] = output_schema

def _create_schema_validator(self, schema: Type[BaseModel]):
    """Create a validator function for the schema."""
    def validator(response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        try:
            # Extract JSON from response
            json_str = self._extract_json(response.content)
            # Parse and validate
            schema.parse_raw(json_str)
            return (True, [])
        except Exception as e:
            return (False, [f"Schema validation failed: {str(e)}"])
    return validator

def _post_step_hook(self, step: WorkflowStep, response: ClaudeCodeResponse):
    """Extended to handle automatic parsing of extraction steps."""
    # ... existing code ...

    # If this is an extraction step, parse and store the data
    if hasattr(self, '_extraction_schemas') and step.name in self._extraction_schemas:
        schema = self._extraction_schemas[step.name]
        json_str = self._extract_json(response.content)
        parsed_data = schema.parse_raw(json_str)

        # Store parsed data with original step name
        base_name = step.name.replace("_extract", "")
        self.state.context[f"{base_name}_data"] = parsed_data
```

### Benefits

1. **Clean Separation**: Task execution is separate from formatting
2. **Automatic**: No manual extraction prompting needed
3. **Flexible**: Can provide custom extraction prompts
4. **Type Safe**: Pydantic validation built-in
5. **Intuitive**: Clear what's happening in workflow setup

### Alternative: Inline Helper Method

If you prefer a more compact approach:

```python
def extract_schema(self, schema: Type[BaseModel]) -> Any:
    """Extract schema from current session state."""
    prompt = f"Output your findings as JSON matching:\n{schema.schema_json(indent=2)}"
    response = self.session.query(prompt, continue_session=True, max_cost=0.5)

    # Parse and validate
    json_str = self._extract_json(response.content)
    return schema.parse_raw(json_str)

# Usage in post-step hook or dynamic step generator:
def _post_step_hook(self, step, response):
    if step.name == "analyze":
        issues = self.extract_schema(IssuesList)
        self.state.context["analyze_data"] = issues
```

### Recommendation

Use the **automatic extraction step** approach because:
- It's explicit in the workflow definition
- Maintains step isolation and testability
- Works seamlessly with resume/state management
- Integrates perfectly with dynamic steps
- Extraction attempts are visible in workflow progress

## Step Helpers Design

### Problem Statement
Currently, extracting structured data between steps requires manual prompting, parsing, and validation. We need a built-in way to:
- Continue from previous AI session
- Request specific JSON schema output
- Automatically parse and validate
- Handle schema validation errors with retries
- Make parsed data easily accessible for subsequent steps

### Design Approaches Considered

#### Approach 1: Separate Method Approach
```python
data = self.request_output(schema=IssuesSchema)
```
**Pros**: Explicit, can be called anywhere
**Cons**: Breaks step flow, unclear when/where to call, hard to track in state

#### Approach 2: Extended add_step (Recommended) ⭐
Extend existing `add_step` with optional schema parameter:
```python
self.add_step(
    name="extract_issues",
    prompt_template="Output the issues found as JSON matching this schema:\n{{schema_description}}",
    output_schema=IssuesSchema,  # New optional parameter
    continue_session=True,       # Reuse existing parameter
    max_retries=3               # Reuse for schema validation
)
```

#### Approach 3: Specialized Step Type
```python
self.add_extraction_step(
    name="extract_issues",
    schema=IssuesSchema,
    prompt="Extract the issues in JSON format"
)
```
**Pros**: Very explicit intent
**Cons**: Another API to learn, potentially overengineered

### Recommended Implementation: Extended add_step

#### API Design
```python
def add_step(
    self,
    name: str,
    prompt_template: str,
    output_schema: Optional[Type[BaseModel]] = None,  # NEW
    # ... existing parameters
):
```

#### Execution Flow
1. **Pre-execution**: If `output_schema` is provided:
   - Generate schema description/example
   - Inject into prompt context as `{{schema_description}}`
   - Set `continue_session=True` by default

2. **Post-execution**: If `output_schema` is provided:
   - Extract JSON from response (handle code blocks, messages)
   - Parse JSON and validate against schema
   - On validation failure:
     - Use existing retry mechanism
     - Inject validation errors into retry prompt
   - On success:
     - Store parsed object in context as `{step_name}_data`
     - Also keep raw output as `{step_name}_output`

### Integration with Dynamic Steps

This design works seamlessly with the dynamic steps feature:

```python
def _setup_steps(self):
    # Step 1: Analyze and extract structured data
    self.add_step(
        name="analyze",
        prompt_template="Analyze the codebase and output issues as JSON:\n{{schema_description}}",
        output_schema=IssuesListSchema,
        max_retries=3
    )

    # Register dynamic step generator that uses the parsed data
    self.add_dynamic_steps("analyze", self._generate_issue_steps)

    # Final summary step
    self.add_step("summarize", ...)

def _generate_issue_steps(self, response, context):
    # Access parsed data directly - no manual parsing needed!
    issues = context["analyze_data"]  # This is the parsed IssuesListSchema object

    return [
        WorkflowStep(
            name=f"investigate_issue_{i}",
            prompt_template=f"Investigate: {issue.description}",
            # ...
        )
        for i, issue in enumerate(issues.issues)
    ]
```

### Implementation Details

1. **Schema Description Generation**:
   ```python
   def _generate_schema_description(schema: Type[BaseModel]) -> str:
       # Use Pydantic's schema_json() or custom formatter
       return schema.schema_json(indent=2)
   ```

2. **JSON Extraction**:
   ```python
   def _extract_json(content: str) -> str:
       # Handle various formats:
       # - Raw JSON
       # - JSON in markdown code blocks
       # - JSON with surrounding text
       # Use regex or simple heuristics
   ```

3. **Validation Integration**:
   - Reuse existing `validator` parameter
   - If `output_schema` provided, create automatic validator
   - Chain with any custom validator if both provided

### Usage Example

```python
from pydantic import BaseModel
from typing import List

class Issue(BaseModel):
    type: str
    severity: str
    description: str
    file: str
    line: int

class IssuesList(BaseModel):
    issues: List[Issue]

class SecurityAuditWorkflow(AIWorkflow):
    def _setup_steps(self):
        # Extract structured data
        self.add_step(
            name="find_issues",
            prompt_template="""
            Analyze the codebase for security issues.
            Output your findings as JSON matching this schema:
            {{schema_description}}
            """,
            output_schema=IssuesList,
            max_cost=5.0
        )

        # Use parsed data for dynamic steps
        self.add_dynamic_steps("find_issues", self._create_investigation_steps)

    def _create_investigation_steps(self, response, context):
        issues_data = context["find_issues_data"]  # Parsed IssuesList object

        return [
            WorkflowStep(
                name=f"investigate_{issue.type}_{i}",
                prompt_template=f"Deep dive into {issue.type} issue in {issue.file}:{issue.line}",
                max_cost=2.0
            )
            for i, issue in enumerate(issues_data.issues)
            if issue.severity == "high"
        ]
```

### Benefits

1. **Simplicity**: Single API, natural extension of existing `add_step`
2. **Type Safety**: Pydantic models provide validation and typing
3. **Automatic Retries**: Reuses existing retry mechanism for schema validation
4. **Clean Integration**: Works perfectly with dynamic steps
5. **No Manual Parsing**: Framework handles JSON extraction and parsing
6. **Flexible**: Can still use custom validators alongside schema validation

### Alternative Considerations

If we want even more flexibility, we could support multiple output formats:
```python
output_format="json"  # or "yaml", "xml"
output_parser=custom_parser_function  # for complex cases
```

But for now, focusing on JSON with Pydantic schemas keeps it simple and covers 90% of use cases.

## Unified Technical Specification

### Overview
Three new step types to enhance Wake AI workflows:
1. **Dynamic Steps** - Generate steps based on runtime data
2. **Extraction Steps** - Extract structured data from AI responses
3. **Regular Steps** - Existing functionality (unchanged)

### API Design

#### 1. Regular Steps (existing)
```python
def add_step(
    name: str,
    prompt_template: str,
    allowed_tools: Optional[List[str]] = None,
    disallowed_tools: Optional[List[str]] = None,
    validator: Optional[Callable] = None,
    max_cost: Optional[float] = None,
    max_retries: int = 3,
    continue_session: bool = False
)
```

#### 2. Extraction Steps (new)
```python
def add_extraction_step(
    after_step: str,
    output_schema: Type[BaseModel],
    name: Optional[str] = None,  # defaults to "{after_step}_extract"
    extract_prompt: Optional[str] = None,  # auto-generated if not provided
    max_cost: float = 0.5  # extractions should be cheap
)
```

#### 3. Dynamic Steps (new)
```python
def add_dynamic_steps(
    after_step: str,
    generator: Callable[[ClaudeCodeResponse, Dict[str, Any]], List[WorkflowStep]]
)
```

### Implementation Architecture

#### Core Changes to AIWorkflow

```python
class AIWorkflow(ABC):
    def __init__(self, ...):
        # ... existing init ...
        self._dynamic_generators: Dict[str, Callable] = {}
        self._extraction_schemas: Dict[str, Type[BaseModel]] = {}
        self._step_positions: Dict[str, int] = {}  # Track original positions
```

#### Execution Flow Modifications

1. **Step Position Tracking**
   - Store original step positions during `_setup_steps()`
   - Use for inserting extraction/dynamic steps at correct locations

2. **Post-Step Hook Enhancement**
   ```python
   def _post_step_hook(self, step: WorkflowStep, response: ClaudeCodeResponse):
       # Handle extraction step parsing
       if step.name in self._extraction_schemas:
           schema = self._extraction_schemas[step.name]
           json_data = self._extract_json(response.content)
           parsed = schema.parse_raw(json_data)

           # Store with original step name
           base_name = step.name.replace("_extract", "")
           self.state.context[f"{base_name}_data"] = parsed

       # Handle dynamic step generation
       if step.name in self._dynamic_generators:
           generator = self._dynamic_generators[step.name]
           new_steps = generator(response, self.state.context)

           # Insert after current position
           insert_idx = self.state.current_step + 1
           for i, new_step in enumerate(new_steps):
               self.steps.insert(insert_idx + i, new_step)
   ```

#### Extraction Step Implementation

```python
def add_extraction_step(self, after_step: str, output_schema: Type[BaseModel], ...):
    # Generate extraction prompt
    if extract_prompt is None:
        schema_json = output_schema.schema_json(indent=2)
        extract_prompt = f"""Output your analysis as JSON matching this schema:

```json
{schema_json}
```

Provide ONLY valid JSON, no additional text or markdown formatting."""

    # Create step with automatic validator
    step = WorkflowStep(
        name=name or f"{after_step}_extract",
        prompt_template=extract_prompt,
        continue_session=True,  # Always true for extractions
        validator=self._create_schema_validator(output_schema),
        max_cost=max_cost,
        max_retries=3
    )

    # Insert after target step
    self._insert_after_step(after_step, step)

    # Store schema for parsing
    self._extraction_schemas[step.name] = output_schema
```

#### JSON Extraction Utility

```python
def _extract_json(self, content: str) -> str:
    """Extract JSON from AI response, handling various formats."""
    # Try patterns in order:
    # 1. JSON in code blocks: ```json\n{...}\n```
    # 2. JSON in generic code blocks: ```\n{...}\n```
    # 3. Raw JSON: {...} or [...]

    # Code block pattern
    code_block_match = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', content)
    if code_block_match:
        return code_block_match.group(1).strip()

    # Raw JSON pattern
    json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', content)
    if json_match:
        return json_match.group(1).strip()

    # Fallback: entire content
    return content.strip()
```

### Usage Example

```python
from pydantic import BaseModel
from typing import List

class Issue(BaseModel):
    type: str
    severity: str
    file: str
    line: int
    description: str

class IssuesList(BaseModel):
    issues: List[Issue]

class SecurityAuditWorkflow(AIWorkflow):
    def _setup_steps(self):
        # 1. Analysis step - pure work
        self.add_step(
            name="analyze",
            prompt_template="Analyze codebase for security vulnerabilities",
            allowed_tools=["file_search", "file_read"],
            max_cost=5.0
        )

        # 2. Extract structured data
        self.add_extraction_step(
            after_step="analyze",
            output_schema=IssuesList
        )

        # 3. Generate dynamic investigation steps
        self.add_dynamic_steps(
            after_step="analyze_extract",
            generator=self._generate_investigation_steps
        )

        # 4. Summary
        self.add_step(
            name="summarize",
            prompt_template="Summarize all findings from previous steps"
        )

    def _generate_investigation_steps(self, response, context):
        issues = context["analyze_data"]  # Parsed IssuesList

        return [
            WorkflowStep(
                name=f"investigate_{issue.type}_{i}",
                prompt_template=f"Deep dive into {issue.type} issue in {issue.file}:{issue.line}",
                continue_session=False,  # Fresh session per investigation
                max_cost=2.0
            )
            for i, issue in enumerate(issues.issues)
            if issue.severity in ["high", "critical"]
        ]
```

### Implementation Considerations

#### 1. State Management
- Dynamic steps must be included in state saving/loading
- Consider step insertion history for resume capability
- Extraction step results should be stored in state

#### 2. Step Naming
- Enforce unique step names
- Default extraction step names: `{source_step}_extract`
- Dynamic step names must be unique (generator responsibility)

#### 3. Error Handling
- Extraction validation errors should use existing retry mechanism
- Failed dynamic generation should not break workflow
- Clear error messages for missing steps in `after_step`

#### 4. Performance
- JSON extraction regex should be compiled once
- Schema validation should cache schema JSON
- Consider limiting dynamic steps to prevent explosion

#### 5. Resume Capability
- Dynamic steps added must be deterministic on resume
- Store generator state if needed
- Extraction results must be in saved state

### Migration Path

1. These are additive changes - no breaking changes
2. Existing workflows continue to work unchanged
3. New methods are optional enhancements

### Testing Considerations

1. Test extraction with various JSON formats
2. Test dynamic step insertion at boundaries
3. Test resume with dynamic steps
4. Test extraction validation retry logic
5. Test step name collision handling

### Future Enhancements

1. Support YAML/XML extraction formats
2. Allow conditional dynamic steps
3. Support parallel step execution
4. Add step dependencies beyond simple ordering

## Practical Workflow Improvements

### Problem Areas
1. Result parsing from working_dir is boilerplate-heavy
2. Common patterns (detectors, security checks) require repetitive setup
3. No easy way to limit step execution (time/turns)
4. Debugging workflows is difficult

### Proposed Solutions

#### 1. Auto-Extraction for Results (Simplify Detection Pattern)

Combine extraction steps with result classes:

```python
class DetectorWorkflow(AIWorkflow):
    """Base class for detection workflows with auto-extraction."""

    def __init__(self, **kwargs):
        kwargs['result_class'] = DetectionResult
        super().__init__(**kwargs)

    def _setup_steps(self):
        # Main detection logic
        self.add_step(
            name="detect",
            prompt_template=self.get_detector_prompt()
        )

        # Auto-extract to Pydantic model
        self.add_extraction_step(
            after_step="detect",
            output_schema=DetectionsList  # Pydantic: List[Detection]
        )

    def format_results(self, results):
        # No manual parsing needed!
        detections = self.state.context.get("detect_data", [])
        return DetectionResult(detections.detections, self.working_dir)
```

**Benefits**:
- No manual YAML parsing
- Type-safe with Pydantic
- Integrates with our extraction steps

#### 2. Workflow Mixins (Common Patterns)

```python
class WakeAnalysisMixin:
    """Integrate Wake's static analysis."""

    def add_wake_detect_step(self, detectors: List[str] = None):
        cmd = "wake detect" + (f" {' '.join(detectors)}" if detectors else "")
        self.add_step(
            name="wake_analysis",
            prompt_template=f"Run `{cmd}` and analyze results",
            allowed_tools=["Bash(wake *)"],
            max_cost=1.0
        )

class SecurityAuditMixin:
    """Common security audit patterns."""

    def add_slither_step(self):
        self.add_step(
            name="slither_analysis",
            prompt_template="Run Slither and categorize findings",
            allowed_tools=["Bash(slither *)"],
            max_cost=2.0
        )
```

**Usage**:
```python
class MyDetector(DetectorWorkflow, WakeAnalysisMixin):
    def _setup_steps(self):
        self.add_wake_detect_step(["reentrancy"])
        self.add_step("manual_verify", ...)
        self.add_extraction_step(...)
```

#### 3. Step Execution Limits

```python
self.add_step(
    name="expensive_analysis",
    prompt_template="...",
    max_cost=5.0,
    max_turns=10,      # NEW: Limit Claude interactions
    timeout=300        # NEW: 5 minute timeout
)
```

**Implementation notes**:
- `max_turns`: Pass to ClaudeCodeSession
- `timeout`: Wrap session.query() with timeout
- Both help control costs and prevent runaway steps

#### 4. Conditional Steps (Simple)

```python
self.add_step(
    name="fix_criticals",
    prompt_template="Fix critical vulnerabilities",
    condition=lambda ctx: len(ctx.get("critical_issues", [])) > 0
)
```

**Implementation**:
- Check condition in execute() before running step
- Skip if False, mark as "skipped" in state
- Simpler than dynamic steps for basic if/then logic

#### 5. Debug Mode

CLI flag: `--debug`

Effects:
- Force `cleanup_working_dir=False`
- Save each step's prompt/response to `.wake/ai/{session}/debug/{step_name}.md`
- Enhanced logging with timing info
- Pretty-print context at each step

#### 6. Result Decorators (Future Enhancement)

```python
@result_from_file("detections.yaml", schema=DetectionsList)
class MyDetectionResult(AIResult):
    # Auto-implements from_working_dir() using file + schema
    pass
```

### Integration with Previous Features

These improvements work seamlessly with our dynamic steps and extraction steps:

```python
class AdvancedDetector(DetectorWorkflow, WakeAnalysisMixin):
    def _setup_steps(self):
        # 1. Run Wake analysis
        self.add_wake_detect_step()

        # 2. Extract Wake findings
        self.add_extraction_step(
            after_step="wake_analysis",
            output_schema=WakeFindings
        )

        # 3. Dynamic verification steps
        self.add_dynamic_steps(
            after_step="wake_analysis_extract",
            generator=self._create_verification_steps
        )

        # 4. Conditional fix step
        self.add_step(
            name="generate_fixes",
            prompt_template="Generate fixes for confirmed issues",
            condition=lambda ctx: len(ctx.get("confirmed_issues", [])) > 0
        )

        # 5. Final extraction
        self.add_extraction_step(
            after_step="generate_fixes",
            output_schema=DetectionsList
        )
```

### Priority Order

1. **Step limits** (timeout, max_turns) - Easy win for cost control
2. **Debug mode** - Essential for development
3. **Detector base class** - Simplifies most common use case
4. **Mixins** - Promotes reuse without complexity
5. **Conditional steps** - Nice to have, but dynamic steps can handle most cases

### Implementation Complexity

All proposals are simple additions:
- No breaking changes
- Minimal new concepts
- Build on existing patterns
- Each feature is independent

## Implementation Roadmap

### Phase 1: Core Enhancements (High Priority)
1. **Dynamic Steps** - Step Factory Method approach
2. **Extraction Steps** - Automatic extraction after steps
3. **Step Execution Limits** - max_turns and timeout

### Phase 2: Developer Experience (Medium Priority)
1. **Debug Mode** - Enhanced logging and state saving
2. **Detector Base Class** - Simplify common patterns
3. **Workflow Mixins** - Reusable components

### Phase 3: Advanced Features (Lower Priority)
1. **Conditional Steps** - Simple if/then logic
2. **Result Decorators** - Auto-parsing from files
3. **Extended output formats** - YAML, XML support

### Key Design Principles Maintained
- **No breaking changes** - All existing workflows continue to work
- **Minimal new concepts** - Build on familiar patterns
- **Type safety** - Leverage Pydantic throughout
- **Clean APIs** - Intuitive and discoverable
- **Composability** - Features work well together

### Integration Benefits
The three main enhancements (dynamic steps, extraction steps, and practical improvements) are designed to work seamlessly together, enabling powerful workflow patterns while maintaining simplicity and clarity.