# Wake AI Flow Writing Assistant

<task>
Create a fully functional Wake AI workflow by implementing the required class structure, defining workflow steps with appropriate prompts and validators, and configuring CLI options according to Wake AI patterns and best practices.
</task>

<context>
Wake AI provides a structured framework for creating AI-powered smart contract analysis workflows. Workflows are Python classes that inherit from `AIWorkflow` and define a sequence of steps that Claude executes with specific tools and validation requirements. The framework handles session management, cost tracking, state persistence, and result formatting automatically.

You will be creating workflows that can range from simple single-step detectors to complex multi-phase analysis pipelines. Each workflow operates in an isolated working directory and can use various Claude tools to analyze code, generate reports, and produce structured outputs.
</context>

<working_dir>
The workflow will automatically create a working directory at `.wake/ai/<session-id>/` where:
- `{{working_dir}}` is available in all prompts as the absolute path
- All generated files should be saved here
- State is persisted for resume capability
- Results are parsed from this directory
</working_dir>

<steps>

## 1. **Determine Workflow Type and Inheritance**

Analyze the requirements to choose the appropriate base class:

a. **For Simple Detectors** (finding specific patterns/vulnerabilities):
   ```python
   from wake_ai import MarkdownDetector
   
   class MyDetector(MarkdownDetector):
       """Detects specific vulnerability patterns."""
       
       def get_detector_prompt(self) -> str:
           return """<task>...</task>..."""
   ```

b. **For Complex Workflows** (multi-step analysis, custom validation):
   ```python
   from wake_ai import AIWorkflow
   from wake_ai.results import AIResult
   
   class MyWorkflow(AIWorkflow):
       """Complex multi-step analysis workflow."""
       
       def __init__(self, scope: List[str], **kwargs):
           # Custom initialization
           super().__init__(name="my_workflow", **kwargs)
   ```

c. **For Workflows with Custom Results**:
   ```python
   from wake_ai import AIWorkflow
   from wake_ai.results import AIResult
   
   class MyCustomResult(AIResult):
       # Define custom result structure
       pass
   
   class MyWorkflow(AIWorkflow):
       def __init__(self, **kwargs):
           super().__init__(
               name="my_workflow",
               result_class=MyCustomResult,
               **kwargs
           )
   ```

## 2. **Initialize the Workflow**

Configure the workflow in `__init__`.

**Note on Default Tools**: As of recent updates, AIWorkflow provides secure default tools that include:
- Read-only tools: `Read`, `Grep`, `Glob`, `LS`, `Task`, `TodoWrite`
- Write tools (path-restricted): `Write({working_dir}/**)`, `Edit({working_dir}/**)`, `MultiEdit({working_dir}/**)`
- Essential bash commands: `Bash(wake:*)`, `Bash(cd:*)`, `Bash(pwd)`, and others

Use `allowed_tools=None` in your steps to inherit these secure defaults.

a. **Set Basic Properties**:
   ```python
   def __init__(self, scope: List[str], threshold: float = 0.8, **kwargs):
       # Call parent constructor with workflow name
       super().__init__(name="vulnerability_analyzer", **kwargs)
       
       # Store configuration
       self.scope = scope
       self.threshold = threshold
   ```

b. **Add Initial Context**:
   ```python
   # Add workflow-specific context variables
   self.add_context("scope", " ".join(self.scope))
   self.add_context("threshold", str(self.threshold))
   self.add_context("execution_dir", str(self.execution_dir))
   ```

c. **Load External Prompts** (for complex workflows):
   ```python
   # Load prompts before _setup_steps() is called
   self.prompts = {}
   prompt_dir = Path(__file__).parent / "prompts"
   
   for prompt_file in prompt_dir.glob("*.md"):
       key = prompt_file.stem.split("-", 1)[1]  # Remove number prefix
       self.prompts[key] = prompt_file.read_text()
   ```

## 3. **Define Workflow Steps**

Implement `_setup_steps()` with appropriate step configurations:

a. **Basic Step Pattern**:
   ```python
   def _setup_steps(self):
       # Step 1: Initial analysis
       self.add_step(
           name="analyze",
           prompt_template=self._get_analysis_prompt(),
           allowed_tools=None,  # Use secure defaults from parent class
           max_cost=5.0,
           validator=self._validate_analysis,
           max_retries=2
       )
   ```

b. **Step with Tool Restrictions**:
   ```python
   # Step with specific Bash commands allowed
   self.add_step(
       name="test_contracts",
       prompt_template="Run Wake tests on the contracts",
       allowed_tools=[
           "Read", 
           "Bash(wake test:*)",  # Note: Use colon for command prefixes
           "Bash(cd:*)"
       ],
       max_cost=3.0
   )
   ```

c. **Step Continuing Previous Session**:
   ```python
   # Continue from previous step's context
   self.add_step(
       name="generate_report",
       prompt_template="Based on your analysis, generate a report...",
       allowed_tools=["Write"],
       continue_session=True,  # Keep context from previous step
       max_cost=2.0
   )
   ```

d. **Conditional Step**:
   ```python
   # Only run if certain condition is met
   self.add_step(
       name="deep_analysis",
       prompt_template="Perform deep analysis...",
       condition=lambda ctx: len(ctx.get("vulnerabilities", [])) > 0,
       allowed_tools=["Read", "Task"],
       max_cost=10.0
   )
   ```

## 4. **Add Advanced Features**

### a. **Extraction Steps** (for structured data):
```python
from pydantic import BaseModel

class VulnerabilityData(BaseModel):
    severity: str
    contract: str
    function: str
    line: int
    description: str

# Add after analysis step
self.add_extraction_step(
    after_step="analyze",
    output_schema=VulnerabilityData,
    max_cost=0.5,
    context_key="vulnerability_data"
)
```

### b. **Dynamic Step Generation**:
```python
def _generate_remediation_steps(self, response: ClaudeCodeResponse, context: Dict[str, Any]) -> List[WorkflowStep]:
    """Generate steps based on findings."""
    steps = []
    
    vulnerabilities = context.get("vulnerabilities", [])
    for i, vuln in enumerate(vulnerabilities):
        steps.append(WorkflowStep(
            name=f"fix_vulnerability_{i}",
            prompt_template=f"Fix the {vuln['type']} vulnerability in {vuln['contract']}",
            allowed_tools=["Read", "Edit", "Write"],
            max_cost=3.0
        ))
    
    return steps

# In _setup_steps():
self.add_dynamic_steps(
    name="remediation_generator",
    generator=self._generate_remediation_steps,
    after_step="analyze"
)
```

## 5. **Implement Validators with Prompt Alignment**

### Critical Rule: Validators Must Match Prompts Exactly

Create validation functions that return `(success: bool, errors: List[str])` and **exactly match what you asked for in the prompt**:

```python
def _validate_analysis(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
    """Validate analysis step output - MUST match prompt requirements exactly."""
    errors = []
    
    # Check for required output file (use exact filename from prompt)
    results_file = self.working_dir / "analysis_results.yaml"
    if not results_file.exists():
        errors.append(
            f"Required file 'analysis_results.yaml' not created at {results_file}. "
            "The prompt asks you to create this file with vulnerability findings."
        )
        return (False, errors)
    
    # Validate YAML structure (match exact structure from prompt)
    try:
        import yaml
        with open(results_file) as f:
            data = yaml.safe_load(f)
        
        # Check required fields match prompt example
        if not isinstance(data, dict):
            errors.append("Results must be a YAML dictionary as shown in the prompt example")
        
        if "vulnerabilities" not in data:
            errors.append(
                "Missing 'vulnerabilities' field. The YAML must have structure:\n"
                "vulnerabilities:\n  - contract: ...\n    function: ...\n    ..."
            )
        
        # Validate each vulnerability has required fields from prompt
        for i, vuln in enumerate(data.get("vulnerabilities", [])):
            required_fields = ["contract", "function", "line", "severity", "description"]
            missing = [f for f in required_fields if f not in vuln]
            if missing:
                errors.append(
                    f"Vulnerability {i} missing fields: {', '.join(missing)}. "
                    f"Each vulnerability must have: {', '.join(required_fields)}"
                )
            
            # Validate severity values match prompt specification
            if "severity" in vuln and vuln["severity"] not in ["high", "medium", "low"]:
                errors.append(
                    f"Vulnerability {i} has invalid severity '{vuln['severity']}'. "
                    "Must be one of: high, medium, low (as specified in prompt)"
                )
            
    except Exception as e:
        errors.append(f"Invalid YAML format: {str(e)}. Check the YAML example in the prompt.")
    
    return (len(errors) == 0, errors)
```

### Validation Best Practices

1. **ALWAYS Include File Path in Error Messages**:
   ```python
   # Bad: No file path - AI doesn't know where to fix
   errors.append("Missing required table")
   
   # Good: File path included - AI knows exactly where to fix
   errors.append(f"Missing required table in {file_path}")
   ```

2. **Copy Exact Strings from Prompt**:
   ```python
   # If prompt says: "Create a table with header: | Type | Count | Description |"
   if "| Type | Count | Description |" not in content:
       errors.append(
           f"Missing required table in {file_path}. Must include exact header: "
           "| Type | Count | Description |"
       )
   ```

3. **Provide Actionable Error Messages**:
   ```python
   # Bad: Generic error, no file path
   errors.append("Invalid format")
   
   # Good: Specific with example and file path
   errors.append(
       f"Invalid severity value in {file_path}. Must be 'high', 'medium', or 'low' "
       "as specified in the prompt example."
   )
   ```

4. **Reference Prompt Requirements**:
   ```python
   errors.append(
       f"Missing required section '## {section_name}' in {file_path}. "
       f"The prompt requires this exact section header."
   )
   ```

## 6. **Write Effective Prompts**

### a. **Inline Prompt Structure**:
```python
def _get_analysis_prompt(self) -> str:
    return """<task>
Analyze smart contracts in {{scope}} for reentrancy vulnerabilities and generate a detailed vulnerability report.
</task>

<steps>
1. **Scan Contract Files**
   a. Use Glob to find all Solidity files in the scope
   b. Read each contract file
   c. Identify state-changing functions

2. **Analyze for Reentrancy**
   a. Look for external calls followed by state changes
   b. Check for missing reentrancy guards
   c. Assess severity based on funds at risk

3. **Generate Report**
   Create `analysis_results.yaml` with structure:
   ```yaml
   vulnerabilities:
     - contract: "Contract.sol"
       function: "withdraw"
       line: 42
       severity: "high"
       description: "External call before state update"
   summary:
     total_found: 3
     high_severity: 1
     medium_severity: 2
   ```
</steps>

<validation_requirements>
- Must create analysis_results.yaml in working directory
- Each vulnerability must have all required fields
- Severity must be: high, medium, or low
- Line numbers must be accurate
</validation_requirements>"""
```

### b. **External Prompt Files** (for complex workflows):
Save as `prompts/1-analyze.md`:
```markdown
<task>
Perform comprehensive security audit of smart contracts focusing on common vulnerability patterns.
</task>

<context>
You are analyzing contracts in: {{scope}}
Working directory: {{working_dir}}
Previous findings: {{initialize_output}}
</context>

<steps>
[Detailed step instructions...]
</steps>

<output_format>
[YAML structure example...]
</output_format>
```

## 7. **Ensure Prompt-Validator Alignment**

### The Most Critical Rule in Wake AI

**Your validators MUST check for EXACTLY what your prompts ask the AI to create.**

### Common Alignment Failures

1. **Format Mismatch**:
   ```python
   # WRONG: Prompt asks for one format, validator checks for another
   # Prompt: "Create table with columns: | Impact | Confidence | Location |"
   # Validator: if "| Severity | Count |" not in content:  # MISMATCH!
   
   # CORRECT: Validator matches prompt exactly
   # Prompt: "Create table with columns: | Impact | Confidence | Location |"
   # Validator: if "| Impact | Confidence | Location |" not in content:
   ```

2. **Vague Error Messages**:
   ```python
   # WRONG: Doesn't help AI fix the issue
   errors.append("Missing table")
   
   # CORRECT: Tells AI exactly what's needed
   errors.append(
       "Missing findings table. Must include table with exact header: "
       "| Impact | Confidence | Location | (as specified in the prompt)"
   )
   ```

3. **Structure Misalignment**:
   ```python
   # WRONG: Prompt shows one YAML structure, validator expects another
   # Prompt example:
   # findings:
   #   - type: "high"
   #     description: "..."
   
   # Validator checking for different fields:
   if "severity" not in finding:  # Should be "type"!
   ```

### Prompt-Validator Development Process

1. **Write Prompt with Exact Outputs**:
   ```markdown
   Create `{{working_dir}}/results.yaml` with structure:
   ```yaml
   findings:
     - title: "Finding title"
       impact: "high|medium|low"
       confidence: "high|medium|low"
       location:
         file: "path/to/file.sol"
         line: 123
   ```
   ```

2. **Extract Every Requirement**:
   - File: `results.yaml` in working_dir
   - Root key: `findings` (list)
   - Required fields: `title`, `impact`, `confidence`, `location`
   - Location subfields: `file`, `line`
   - Valid impact values: `high`, `medium`, `low`
   - Valid confidence values: `high`, `medium`, `low`

3. **Write Validator That Checks Each Requirement**:
   ```python
   def _validate_results(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
       errors = []
       
       # Check exact filename from prompt
       results_file = self.working_dir / "results.yaml"
       if not results_file.exists():
           errors.append(
               f"File 'results.yaml' not created at {results_file}. "
               "The prompt asks you to create this exact file."
           )
           return (False, errors)
       
       try:
           with open(results_file) as f:
               data = yaml.safe_load(f)
           
           # Check exact structure from prompt
           if "findings" not in data:
               errors.append(
                   "Missing 'findings' key. File must have structure:\n"
                   "findings:\n  - title: ...\n    impact: ...\n    ..."
               )
               return (False, errors)
           
           # Validate each finding matches prompt example
           for i, finding in enumerate(data.get("findings", [])):
               # Check exact fields from prompt
               required = ["title", "impact", "confidence", "location"]
               missing = [f for f in required if f not in finding]
               if missing:
                   errors.append(
                       f"Finding {i} missing: {', '.join(missing)}. "
                       f"Each finding needs: {', '.join(required)}"
                   )
               
               # Check exact enum values from prompt
               if finding.get("impact") not in ["high", "medium", "low"]:
                   errors.append(
                       f"Finding {i}: invalid impact '{finding.get('impact')}'. "
                       "Must be: high, medium, or low (as shown in prompt)"
                   )
               
               # Check nested structure from prompt
               if "location" in finding:
                   loc = finding["location"]
                   if "file" not in loc or "line" not in loc:
                       errors.append(
                           f"Finding {i}: location must have 'file' and 'line' "
                           "(see prompt example)"
                       )
       
       except yaml.YAMLError as e:
           errors.append(f"Invalid YAML: {e}. Check prompt example for correct format.")
       
       return (len(errors) == 0, errors)
   ```

### Validation Alignment Checklist

Before finalizing any workflow step:

- [ ] List every file the prompt asks to create
- [ ] Note exact filenames and paths
- [ ] Copy exact section headers from prompt
- [ ] Copy exact table headers from prompt
- [ ] List all required YAML/JSON fields
- [ ] Note valid values for enums/choices
- [ ] Validator checks each item above
- [ ] Error messages reference prompt requirements
- [ ] Error messages include correct examples
- [ ] Test with intentionally wrong output

### Real Example: Audit Workflow Fix

The audit workflow had this misalignment:

**Prompt** (3-executive-summary.md):
```markdown
| Impact   | High Confidence | Medium Confidence | Low Confidence | Total |
```

**Validator** (workflow.py):
```python
if "| Severity | Count |" not in content:
    errors.append("Missing severity findings table in executive-summary.md")
```

**Fixed Validator**:
```python
# Check for the EXACT table format from the prompt
if "| Impact" not in content or not all(
    conf in content for conf in ["High Confidence", "Medium Confidence", "Low Confidence", "Total"]
):
    errors.append(
        "Missing findings summary table. The executive summary must include a table with "
        "this exact header: | Impact | High Confidence | Medium Confidence | Low Confidence | Total |"
    )
```

## 8. **Configure CLI Options**

Define command-line interface for the workflow:

```python
@classmethod
def get_cli_options(cls) -> Dict[str, Any]:
    """Define CLI options for this workflow."""
    return {
        "scope": {
            "param_decls": ["-s", "--scope"],
            "multiple": True,
            "type": click.Path(exists=True),
            "help": "Contract files or directories to analyze",
            "required": True
        },
        "threshold": {
            "param_decls": ["-t", "--threshold"],
            "type": click.FloatRange(0.0, 1.0),
            "default": 0.8,
            "help": "Confidence threshold for vulnerability detection"
        },
        "output_format": {
            "param_decls": ["-f", "--format"],
            "type": click.Choice(["yaml", "json", "markdown"]),
            "default": "yaml",
            "help": "Output format for results"
        }
    }

@classmethod
def process_cli_args(cls, **kwargs) -> Dict[str, Any]:
    """Process CLI arguments into workflow init parameters."""
    return {
        "scope": list(kwargs.get("scope", [])),
        "threshold": kwargs.get("threshold", 0.8),
        "output_format": kwargs.get("output_format", "yaml")
    }
```

## 8. **Implement Custom Result Classes** (if needed)

For workflows requiring special output formatting:

```python
from wake_ai.results import AIResult
from pathlib import Path
from typing import Dict, Any

class SecurityAuditResult(AIResult):
    """Custom result for security audit workflow."""
    
    def __init__(self, vulnerabilities: List[Dict], summary: Dict):
        self.vulnerabilities = vulnerabilities
        self.summary = summary
    
    @classmethod
    def from_working_dir(cls, working_dir: Path, raw_results: Dict[str, Any]) -> "SecurityAuditResult":
        """Parse results from working directory."""
        import yaml
        
        # Load main results file
        results_file = working_dir / "analysis_results.yaml"
        if results_file.exists():
            with open(results_file) as f:
                data = yaml.safe_load(f)
                return cls(
                    vulnerabilities=data.get("vulnerabilities", []),
                    summary=data.get("summary", {})
                )
        
        return cls(vulnerabilities=[], summary={})
    
    def pretty_print(self) -> None:
        """Display results in console."""
        from rich.console import Console
        from rich.table import Table
        
        console = Console()
        
        if not self.vulnerabilities:
            console.print("[green]No vulnerabilities found![/green]")
            return
        
        # Create summary table
        table = Table(title="Security Audit Results")
        table.add_column("Contract", style="cyan")
        table.add_column("Function", style="yellow")
        table.add_column("Severity", style="red")
        table.add_column("Description")
        
        for vuln in self.vulnerabilities:
            table.add_row(
                vuln["contract"],
                vuln["function"],
                vuln["severity"].upper(),
                vuln["description"]
            )
        
        console.print(table)
        console.print(f"\nTotal: {self.summary.get('total_found', 0)} vulnerabilities")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "vulnerabilities": self.vulnerabilities,
            "summary": self.summary
        }
```

## 9. **Complete Workflow Example**

Here's a complete example combining all concepts:

```python
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import click
from pydantic import BaseModel

from wake_ai import AIWorkflow, WorkflowStep
from wake_ai.results import AIResult
from wake_ai.core.claude import ClaudeCodeResponse


class VulnerabilityInfo(BaseModel):
    contract: str
    function: str
    line: int
    severity: str
    type: str
    description: str


class ReentrancyResult(AIResult):
    """Result class for reentrancy detection."""
    
    def __init__(self, vulnerabilities: List[Dict]):
        self.vulnerabilities = vulnerabilities
    
    @classmethod
    def from_working_dir(cls, working_dir: Path, raw_results: Dict[str, Any]) -> "ReentrancyResult":
        import yaml
        results_file = working_dir / "reentrancy_report.yaml"
        
        if results_file.exists():
            with open(results_file) as f:
                data = yaml.safe_load(f)
                return cls(vulnerabilities=data.get("vulnerabilities", []))
        
        return cls(vulnerabilities=[])
    
    def pretty_print(self) -> None:
        from rich.console import Console
        from rich.panel import Panel
        
        console = Console()
        
        if not self.vulnerabilities:
            console.print(Panel("[green]✓ No reentrancy vulnerabilities found[/green]"))
            return
        
        console.print(Panel(f"[red]Found {len(self.vulnerabilities)} reentrancy vulnerabilities[/red]"))
        
        for vuln in self.vulnerabilities:
            console.print(f"\n[red]● {vuln['severity'].upper()}[/red] in {vuln['contract']}::{vuln['function']}")
            console.print(f"  Line {vuln['line']}: {vuln['description']}")
    
    def to_dict(self) -> Dict[str, Any]:
        return {"vulnerabilities": self.vulnerabilities}


class ReentrancyWorkflow(AIWorkflow):
    """Detects and analyzes reentrancy vulnerabilities in smart contracts."""
    
    # Default cleanup behavior for this workflow
    cleanup_working_dir = False  # Preserve results
    
    def __init__(self, contracts: List[str], deep_analysis: bool = False, **kwargs):
        """Initialize reentrancy detection workflow.
        
        Args:
            contracts: List of contract files to analyze
            deep_analysis: Whether to perform deep analysis with symbolic execution
        """
        super().__init__(
            name="reentrancy_detector",
            result_class=ReentrancyResult,
            **kwargs
        )
        
        self.contracts = contracts
        self.deep_analysis = deep_analysis
        
        # Add context
        self.add_context("contracts", " ".join(contracts))
        self.add_context("deep_analysis", deep_analysis)
    
    def _setup_steps(self):
        """Define workflow steps."""
        
        # Step 1: Initial scan for reentrancy patterns
        self.add_step(
            name="scan",
            prompt_template=self._get_scan_prompt(),
            allowed_tools=["Read", "Grep", "Glob"],
            max_cost=3.0,
            validator=self._validate_scan
        )
        
        # Step 2: Extract vulnerability data
        self.add_extraction_step(
            after_step="scan",
            output_schema=VulnerabilityInfo,
            context_key="vulnerabilities"
        )
        
        # Step 3: Deep analysis (conditional)
        self.add_step(
            name="deep_analysis",
            prompt_template=self._get_deep_analysis_prompt(),
            allowed_tools=["Read", "Bash(wake:*)", "Task"],
            condition=lambda ctx: self.deep_analysis and len(ctx.get("vulnerabilities", [])) > 0,
            continue_session=True,
            max_cost=10.0
        )
        
        # Step 4: Generate final report
        self.add_step(
            name="report",
            prompt_template=self._get_report_prompt(),
            allowed_tools=["Write"],
            continue_session=True,
            max_cost=1.0,
            validator=self._validate_report
        )
    
    def _get_scan_prompt(self) -> str:
        return """<task>
Scan smart contracts for reentrancy vulnerabilities by identifying external calls followed by state changes.
</task>

<context>
Analyzing contracts: {{contracts}}
Working directory: {{working_dir}}
</context>

<steps>
1. **Read Contract Files**
   - Read each specified contract file
   - Parse function definitions and modifiers

2. **Identify Reentrancy Patterns**
   - Look for external calls (call, delegatecall, transfer, send)
   - Check if state variables are modified after external calls
   - Note missing nonReentrant modifiers

3. **Classify Severity**
   - HIGH: Funds can be drained, no protection
   - MEDIUM: State corruption possible, limited protection
   - LOW: Minimal impact, some protection exists

4. **Document Findings**
   For each vulnerability found, record:
   - Contract name and path
   - Function name
   - Line number of the external call
   - Severity level
   - Specific vulnerability type
   - Clear description
</steps>

<output_format>
Create a mental note of all findings. You'll be asked to format them in the next step.
</output_format>"""
    
    def _get_deep_analysis_prompt(self) -> str:
        return """<task>
Perform deep analysis of identified reentrancy vulnerabilities using Wake's symbolic execution.
</task>

<steps>
1. **Run Wake Detectors**
   ```bash
   wake detect reentrancy {{contracts}}
   ```

2. **Analyze Call Graphs**
   - Trace execution paths to vulnerable functions
   - Identify all possible entry points

3. **Verify Exploitability**
   - Check if vulnerabilities are actually reachable
   - Assess real-world impact

4. **Update Findings**
   - Refine severity based on deep analysis
   - Add exploitation difficulty assessment
</steps>"""
    
    def _get_report_prompt(self) -> str:
        return """<task>
Generate a comprehensive reentrancy vulnerability report based on all analysis performed.
</task>

<output_format>
Create `reentrancy_report.yaml` with structure:
```yaml
vulnerabilities:
  - contract: "VulnerableBank.sol"
    function: "withdraw"
    line: 45
    severity: "high"
    type: "classic-reentrancy"
    description: "External call to msg.sender before balance update"
    exploitable: true
    recommendation: "Add nonReentrant modifier or use checks-effects-interactions pattern"
```
</output_format>

Include all vulnerabilities found, ordered by severity (high to low)."""
    
    def _validate_scan(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        """Validate initial scan completed successfully."""
        # Basic validation - just check response has content
        if not response.content:
            return (False, ["Scan produced no output"])
        return (True, [])
    
    def _validate_report(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        """Validate final report generation."""
        errors = []
        report_file = self.working_dir / "reentrancy_report.yaml"
        
        if not report_file.exists():
            errors.append("reentrancy_report.yaml not created")
            return (False, errors)
        
        try:
            import yaml
            with open(report_file) as f:
                data = yaml.safe_load(f)
            
            if "vulnerabilities" not in data:
                errors.append("Missing 'vulnerabilities' field in report")
            
        except Exception as e:
            errors.append(f"Invalid YAML in report: {str(e)}")
        
        return (len(errors) == 0, errors)
    
    @classmethod
    def get_cli_options(cls) -> Dict[str, Any]:
        """CLI options for reentrancy detector."""
        return {
            "contracts": {
                "param_decls": ["-c", "--contracts"],
                "multiple": True,
                "type": click.Path(exists=True),
                "required": True,
                "help": "Smart contract files to analyze"
            },
            "deep_analysis": {
                "param_decls": ["--deep-analysis"],
                "is_flag": True,
                "help": "Perform deep analysis with symbolic execution"
            }
        }
    
    @classmethod  
    def process_cli_args(cls, **kwargs) -> Dict[str, Any]:
        """Process CLI arguments."""
        return {
            "contracts": list(kwargs.get("contracts", [])),
            "deep_analysis": kwargs.get("deep_analysis", False)
        }
```

</steps>

<recent_updates>
## Recent Framework Updates

The following changes have been made to the Wake AI framework that affect workflow creation:

1. **Default Tool Permissions**: AIWorkflow now provides secure default tools. Use `allowed_tools=None` to inherit defaults instead of specifying all tools manually.

2. **Tool Pattern Format**: When restricting Bash commands, use colon syntax: `Bash(wake:*)` instead of `Bash(wake *)`

3. **Detection Structure Changes**:
   - The `Detection` class now uses `description` field instead of `detection` field
   - Added optional `source` field to track which workflow/detector found the issue
   - Audit workflow uses `AuditDetection` with `impact` and `confidence` instead of `severity`

4. **MarkdownDetector Independence**: `MarkdownDetector` no longer depends on `AuditResult` and has its own `MarkdownDetectorResult` class

5. **Detection Type Validation**: Audit workflow validates detection types against a specific list:
   - Data validation, Code quality, Logic error, Standards violation
   - Gas optimization, Logging, Trust model, Arithmetics
   - Access control, Unused code, Storage clashes, Denial of service
   - Front-running, Replay attack, Reentrancy, Function visibility
   - Overflow/Underflow, Configuration, Reinitialization, Griefing, N/A
</recent_updates>

<validation_requirements>
- **CRITICAL**: Validators MUST check for EXACTLY what prompts ask the AI to create
- **CRITICAL**: Error messages MUST tell the AI specifically what to fix, with examples
- **ALWAYS** inherit from either `AIWorkflow` or `MarkdownDetector`
- **ALWAYS** implement `_setup_steps()` method
- **ALWAYS** call `super().__init__()` with workflow name
- **NEVER** access `self.steps` before `super().__init__()` is called
- **NEVER** forget to validate step outputs that create files
- **ALWAYS** use `{{working_dir}}` in prompts for file paths
- **ALWAYS** use proper tool restrictions for security-sensitive operations
- **ALWAYS** provide proper typing for all methods
- **NEVER** use generic Exception catching without proper error handling
- **ALWAYS** copy exact strings (headers, table formats, field names) from prompts to validators
- **NEVER** paraphrase or change formats between prompt and validator
</validation_requirements>

<output_format>
When asked to create a workflow, provide:

1. **Complete Python Code**:
   - Full workflow class implementation
   - All required imports
   - Proper docstrings
   - Type hints for all parameters

2. **Prompt Files** (if using external prompts):
   - Each prompt as a separate markdown file
   - Named with number prefix: `0-initialize.md`, `1-analyze.md`
   - Following Wake AI prompt structure

3. **Usage Example**:
   ```bash
   # CLI usage
   wake-ai --flow my_workflow -c contract.sol --deep-analysis
   
   # Python usage
   from flows.my_workflow import MyWorkflow
   workflow = MyWorkflow(contracts=["contract.sol"])
   results, formatted = workflow.execute()
   ```

4. **File Structure**:
   ```
   flows/
   └── my_workflow/
       ├── __init__.py
       ├── workflow.py
       └── prompts/
           ├── 0-initialize.md
           └── 1-analyze.md
   ```
</output_format>

<example_simple_detector>
```python
from wake_ai import MarkdownDetector

class UnusedImportDetector(MarkdownDetector):
    """Detects unused imports in Solidity contracts."""
    
    def get_detector_prompt(self) -> str:
        return """<task>
Identify all unused import statements in Solidity contracts by analyzing which imported symbols are never referenced in the code.
</task>

<context>
You are analyzing smart contracts to find import statements that bring in symbols (contracts, libraries, interfaces) that are never used in the importing file. This helps clean up code and reduce compilation overhead.
</context>

<steps>
1. **Scan for Import Statements**
   - Find all import statements in each Solidity file
   - Track what symbols each import brings into scope
   - Note the import style (specific, aliased, or wildcard)

2. **Analyze Symbol Usage**
   - For each imported symbol, search for its usage in the file
   - Check in: inheritance, function parameters, return types, variable declarations, function calls
   - Consider aliased imports

3. **Generate Findings**
   - List each unused import with its location
   - Specify which symbols are unused
   - Suggest whether to remove or make specific

Save findings to `{{working_dir}}/results.yaml` with this structure:
```yaml
findings:
  - file: "contracts/Token.sol"
    line: 3
    import_statement: 'import "./interfaces/IERC20.sol";'
    unused_symbols: ["IERC20"]
    severity: "low"
    recommendation: "Remove unused import"
```
</steps>"""
```
</example_simple_detector>

<example_complex_workflow>
```python
from pathlib import Path
from typing import Dict, Any, List, Tuple
import click

from wake_ai import AIWorkflow
from wake_ai.core.claude import ClaudeCodeResponse


class UpgradeabilityAudit(AIWorkflow):
    """Comprehensive audit for upgradeable smart contract systems."""
    
    # Preserve results by default
    cleanup_working_dir = False
    
    def __init__(self, proxy_address: str, implementation_address: str, **kwargs):
        super().__init__(name="upgradeability_audit", **kwargs)
        
        self.proxy = proxy_address
        self.implementation = implementation_address
        
        # Load external prompts
        prompt_dir = Path(__file__).parent / "prompts"
        self.prompts = {}
        for p in prompt_dir.glob("*.md"):
            self.prompts[p.stem.split("-", 1)[1]] = p.read_text()
        
        # Set context
        self.add_context("proxy_address", proxy_address)
        self.add_context("implementation_address", implementation_address)
    
    def _setup_steps(self):
        # Step 1: Analyze proxy pattern
        self.add_step(
            name="analyze_proxy",
            prompt_template=self.prompts["analyze_proxy"],
            allowed_tools=["Read", "Grep", "Task"],
            max_cost=5.0,
            validator=self._validate_proxy_analysis
        )
        
        # Step 2: Check storage layout
        self.add_step(
            name="storage_check", 
            prompt_template=self.prompts["storage_check"],
            allowed_tools=["Read", "Bash(wake print storage-layout:*)"],
            continue_session=True,
            max_cost=3.0
        )
        
        # Step 3: Security analysis
        self.add_step(
            name="security_audit",
            prompt_template=self.prompts["security_audit"],
            allowed_tools=["Read", "Write", "Task"],
            max_cost=10.0,
            validator=self._validate_security_audit
        )
        
        # Dynamic steps based on findings
        self.add_dynamic_steps(
            name="issue_remediation",
            generator=self._generate_fix_steps,
            after_step="security_audit"
        )
    
    def _validate_proxy_analysis(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        errors = []
        analysis_file = self.working_dir / "proxy_analysis.yaml"
        
        if not analysis_file.exists():
            errors.append("proxy_analysis.yaml not created")
        
        return (len(errors) == 0, errors)
    
    def _validate_security_audit(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        errors = []
        
        required_files = ["security_findings.yaml", "audit_report.md"]
        for file in required_files:
            if not (self.working_dir / file).exists():
                errors.append(f"Required file {file} not created")
        
        return (len(errors) == 0, errors)
    
    def _generate_fix_steps(self, response: ClaudeCodeResponse, context: Dict[str, Any]) -> List[WorkflowStep]:
        # Parse findings and generate remediation steps
        import yaml
        
        findings_file = self.working_dir / "security_findings.yaml"
        if not findings_file.exists():
            return []
        
        with open(findings_file) as f:
            findings = yaml.safe_load(f)
        
        steps = []
        critical_issues = [f for f in findings.get("issues", []) if f["severity"] == "critical"]
        
        for i, issue in enumerate(critical_issues[:3]):  # Limit to 3 critical fixes
            steps.append(WorkflowStep(
                name=f"fix_critical_{i}",
                prompt_template=f"""Fix the critical issue: {issue['title']}
                
Issue description: {issue['description']}
Location: {issue['location']}

Generate a patch file that addresses this issue.""",
                allowed_tools=["Read", "Write", "Edit"],
                max_cost=3.0
            ))
        
        return steps
    
    @classmethod
    def get_cli_options(cls) -> Dict[str, Any]:
        return {
            "proxy_address": {
                "param_decls": ["--proxy"],
                "type": str,
                "required": True,
                "help": "Proxy contract address"
            },
            "implementation_address": {
                "param_decls": ["--implementation"],
                "type": str,
                "required": True,
                "help": "Implementation contract address"
            }
        }
    
    @classmethod
    def process_cli_args(cls, **kwargs) -> Dict[str, Any]:
        return {
            "proxy_address": kwargs["proxy_address"],
            "implementation_address": kwargs["implementation_address"]
        }
```
</example_complex_workflow>