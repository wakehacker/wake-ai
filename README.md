# Wake AI Architecture

The core component of Wake AI are workflows which consist of a set of steps. Each step has a prompt (with available tools) and a step validator. Options such as `max_cost_limit` or `max_retries` can be set for each step.

## Folder Structure

```
wake/
├── wake/cli/ai.py              # `wake ai` command implementation
├── wake/ai/                    # Core AI module
│   ├── framework/              # Core framework components
│   │   ├── claude.py           # Claude Code wrapper
│   │   ├── flow.py             # Base workflow infrastructure
│   │   ├── exceptions.py       # Framework exceptions
│   │   └── utils.py            # Framework utility functions
│   ├── detections.py           # Detection-specific classes and utilities
│   ├── results.py              # Result system (AIResult, SimpleResult)
│   ├── tasks.py                # Task classes (AITask, DetectionTask)
│   ├── runner.py               # Workflow execution helper
│   └── utils.py                # Shared utility functions
│
└── wake_ai/                    # AI workflow implementations
    ├── audit/                  # Security audit workflow
    │   ├── workflow.py         # AuditWorkflow implementation
    │   └── prompts/            # Audit-specific prompts
    │       ├── 0-initialize.md
    │       ├── 1-analyze-and-plan.md
    │       ├── 2-manual-review.md
    │       └── 3-executive-summary.md
    └── ...                     # More workflows
```

## Execution Paths

Workflows can be implemented in 2 ways:

`wake ai --flow <name> <args>` - new CLI commands for running workflows

or

`wake detect <ai-detector-name> <args>` - standard detector wrapper for workflows

Both have their own advantages and disadvantages.

### 1. CLI Command: `wake ai`

```bash
wake ai --flow audit --scope contracts/Token.sol --model opus
```

This makes more (intuitive) sense, BUT:
- Wake is opensource and thus the prompts will be open-sourced too (at least at this point)

### 2. Detector Command: `wake detect`
AI workflow wrapped as a Wake detector.

```bash
wake detect ai-audit --scope contracts/Token.sol --model opus
```

Less intuitive for implementation, BUT:
- Can be created as a private detector, distributed within `wake-private`

## Workflow Core Concepts

### Cladue Session and Workflow Management

Wake AI contains inteligent wrappers for Claude Code API.
This wrapper allows us to:
- Continue `claude code` sessions inbetween steps
- Set cost limits for each step, where the wrapper automatically loops through `claude code` execution in configurable increments of `n` turns, monitoring accumulated costs after each increment and prompting Claude to efficiently finish the task when the specified `max_cost_limit` threshold is approached
- If a `validation` function is provided, the wrapper will automatically retry the step, prompting `claude code` to fix the errors returned by the `validation` function

### Working Directory

A key concept of Wake AI is the `working_dir` and `execution_dir`.
The `execution_dir` is the directory where the workflow is executed.
The `working_dir` is the directory where the `claude code` works in.

One of the main problems which needed to be resolved is how to pass context and results in between steps.
A straight forward solution is to simply use a working directory, serving as a shared scratchpad and results storage.
All steps within the workflow will have access to the working directory, and can read and write to it.
The working directory is also used to store the result of the workflow.

```
.wake/ai/<YYYYMMDD_HHMMSS_random>/
├── state/                 # Workflow state metadata
├── <ai-thoughts>.md       # Thoughts, or intermediate results can be stored in markdown files
└── <ai-results>.json      # Results can be stored in json files for easy parsing after the workflow is finished
```

### Workflow Execution Flow

This diagram shows how workflows execute with multiple steps, validation, and retry logic:

```mermaid
flowchart TD
    Start([Start Workflow]) --> Init[Initialize Workflow]
    Init --> NextStep

    NextStep[Get Next Step] --> CheckComplete{All Steps<br/>Complete?}
    CheckComplete -->|Yes| Complete([Workflow Complete])
    CheckComplete -->|No| StepBox

    subgraph StepBox["Claude Code Session"]
        ExecuteStep[Execute Step:<br/>• Set step tools<br/>• Format prompt with context<br/>• Create Claude session<br/>• Query Claude] --> QueryAI

        QueryAI[Claude Response] --> Validate{Has<br/>Validator?}
        Validate -->|No| Success
        Validate -->|Yes| RunValidator[Run Validation]

        RunValidator --> Valid{Valid?}
        Valid -->|Yes| Success
        Valid -->|No| CheckRetries{Retries<br/>Left?}

        CheckRetries -->|Yes| RetryPrompt[Add Error Correction<br/>to Prompt]
        CheckRetries -->|No| Fail[Mark Step Failed]

        RetryPrompt --> QueryAI
    end

    Success[Mark Step Complete] --> UpdateContext[Update Context]
    UpdateContext --> NextStep

    Fail --> Error([Workflow Error])

    style Start fill:#90EE90,color:#000
    style Complete fill:#90EE90,color:#000
    style Error fill:#FFB6C1,color:#000
    style Valid fill:#87CEEB,color:#000
    style CheckRetries fill:#FFE4B5,color:#000
    style StepBox fill:transparent,stroke:#333,stroke-width:2px
```

### Max Cost Handling Flow

This diagram shows how `query_with_cost()` executes Claude in turns with cost monitoring:

```mermaid
flowchart TD
    Start([query_with_cost<br/>max_cost = X]) --> Init[Initialize:<br/>accumulated_cost = 0]

    Init --> ExecuteTurn[Execute Claude Turn]
    ExecuteTurn --> Accumulate[accumulated_cost += turn_cost]
    Accumulate --> CheckComplete{Task<br/>Complete?}

    CheckComplete -->|Yes| Done([Return Response])
    CheckComplete -->|No| CheckCost{accumulated_cost<br/>> threshold?}

    CheckCost -->|No| NormalPath
    CheckCost -->|Yes| InitRetry[Initialize: retry_turn = 0]

    subgraph NormalPath["Normal Continuation"]
        ContinuePrompt[Add prompt:<br/>Continue with the task] --> ExecuteTurn
    end

    subgraph FinalizePath["Quick Finalization"]
        RetryTurn[retry_turn += 1] --> CheckRetryTurns{retry_turn < 3?}
        CheckRetryTurns -->|Yes| FinalizePrompt[Add prompt:<br/>Finish efficiently]
        CheckRetryTurns -->|No| Fail[Fail/Revert]
        FinalizePrompt --> FinalTurnLoop[Execute retry turns]
        FinalTurnLoop --> CheckComplete2{Task<br/>Complete?}
        CheckComplete2 -->|Yes| ForceDone[Return Response]
        CheckComplete2 -->|No| RetryTurn
    end

    InitRetry --> FinalizePrompt

    ForceDone --> Done
    Fail --> Error([Task Failed - Cost Exceeded])

    style Start fill:#90EE90,color:#000
    style Done fill:#90EE90,color:#000
    style Error fill:#FFB6C1,color:#000
    style CheckCost fill:#FFE4B5,color:#000
    style FinalizePath fill:transparent,stroke:#ff6b6b,stroke-width:2px
    style NormalPath fill:transparent,stroke:#339af0,stroke-width:2px
```

## Flow Example: AIAuditWorkflow

The audit workflow demonstrates the full capabilities of the Wake AI framework:

### Step Details

1. **Analyze & Plan** (`max_cost: $10.0`)
   - Tools: read, search, write, grep, bash
   - Creates: `tracking.yaml`, `overview.md`
   - Validates: YAML structure, required sections

2. **Manual Review** (`max_cost: $50.0`)
   - Tools: read, write, search, grep, edit
   - Reviews: Each vulnerability in tracking
   - Creates: Issue files for confirmed findings (i.e. `issues/m1-reentrancy.yaml`)
   - Updates: Status (confirmed/false-positive)

3. **Executive Summary** (`max_cost: $10.0`)
   - Tools: read, write
   - Creates: Professional audit report
   - Includes: Statistics, findings, recommendations


### Usage Example

```bash
# Run a new audit
wake ai --flow audit -s contracts/Token.sol -s contracts/Vault.sol --model opus

# Resume a previous audit if it was interrupted
wake ai --flow audit --resume

# With specific focus areas
wake ai --flow audit -f reentrancy -f "access control" --model sonnet
```

### Implementation Example

Here's a simplified example of how the audit workflow is implemented:

```python
from wake.ai.framework.flow import AIWorkflow, ClaudeCodeResponse
from typing import Tuple, List

class AuditWorkflow(AIWorkflow):
    """Security audit workflow following industry best practices."""

    name = "audit"
    allowed_tools = ["Read", "Grep", "Glob", "LS", "Task", "TodoWrite", "Write", "Edit", "MultiEdit"]

    def __init__(self, scope_files=None, context_docs=None, focus_areas=None, **kwargs):
        self.scope_files = scope_files or []
        self.context_docs = context_docs or []
        self.focus_areas = focus_areas or []

        # Load prompts from markdown files
        self._load_prompts()

        # Initialize parent class - this calls _setup_steps()
        super().__init__(name=self.name, **kwargs)

    def _setup_steps(self):
        """Define workflow steps with prompts, tools, and validators."""

        # Step 1: Analyze and Plan
        self.add_step(
            name="analyze_and_plan",
            prompt_template=self._build_prompt("analyze_and_plan"),
            tools=["Read", "Search", "Write", "Grep", "Bash"],
            max_cost=10.0,
            validator=self._validate_analyze_and_plan,
            max_retries=2
        )

        # Step 2: Manual Review
        self.add_step(
            name="manual_review",
            prompt_template=self._build_prompt("manual_review"),
            tools=["Read", "Write", "Search", "Grep", "Edit"],
            max_cost=10.0,
            validator=self._validate_manual_review,
            max_retries=2
        )


        # ... more steps ...

    def _validate_analyze_and_plan(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        """Validate that required files were created with correct structure."""
        errors = []
        audit_dir = Path(self.working_dir) / "audit"

        # Check for tracking.yaml
        tracking_file = audit_dir / "tracking.yaml"
        if not tracking_file.exists():
            errors.append(f"Tracking file not created at {tracking_file}")
        else:
            # Validate YAML structure
            with open(tracking_file, 'r') as f:
                data = yaml.safe_load(f)
                # Check required fields...

        return (len(errors) == 0, errors)

    # ... more validators ...


    @classmethod
    def get_cli_options(cls) -> Dict[str, Any]:
        """Return audit workflow CLI options."""
        import click
        return {
            "scope": {
                "param_decls": ["-s", "--scope"],
                "multiple": True,
                "type": click.Path(exists=True),
                "help": "Files/directories in audit scope (default: entire codebase)"
            },
            "context": {
                "param_decls": ["-c", "--context"],
                "multiple": True,
                "type": click.Path(exists=True),
                "help": "Additional context files (docs, specs, etc.)"
            },
            "focus": {
                "param_decls": ["-f", "--focus"],
                "multiple": True,
                "help": "Focus areas (e.g., 'reentrancy', 'ERC20', 'access-control')"
            }
        }

    @classmethod
    def process_cli_args(cls, **kwargs) -> Dict[str, Any]:
        """Process CLI arguments for audit workflow."""
        return {
            "scope_files": list(kwargs.get("scope", [])),
            "context_docs": list(kwargs.get("context", [])),
            "focus_areas": list(kwargs.get("focus", []))
        }
```

## Flows Location
We can place AI flows into the:
1. `wake/ai/flows` folder
   - most straightforward option, but will require flows to be public so no
2. `wake_detectors` folder
   - private repo good
   - detectors have a quite limited output + auto-compile before by default
   - requires either updating the detector + its output classes or somehow mapping AI flow output to detector output (but then we are missing tructuring into description, epxloit, recommendation, etc.), too complex
3. `wake_printers` folder
    - private repo good
    - more flexible than detectors since we can print anything to output, but lacking export options
    - requires implementing export functionality
4. new `wake_ai` folder, analogous to `wake_detectors` or `wake_printers`
   - as flexible as we want
   - requires implementing fetching from private repo

### Structure

To keep AI flows as flexible as possible, we avoid limiting the output structure by implementing a base `AITask` class that can be extended for specific task types.

The base `AITask` class provides a foundation for any AI-powered task:

```python
class AITask(ABC):
    """Base class for AI tasks that run autonomously and return results.

    This class provides the foundation for various AI-powered tasks like:
    - Security audits
    - Code quality analysis
    - Gas optimization
    - Documentation generation
    - Any custom analysis
    """

    @abstractmethod
    def get_task_type(self) -> str:
        """Return the task type identifier (e.g., 'security-audit', 'code-quality')."""
        ...

    @abstractmethod
    def pretty_print(self, console: "Console") -> None:
        """Print results in a human-readable format to the console."""
        ...

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary format for serialization."""
        ...

    def export_json(self, path: Path) -> None:
        """Export results to JSON file.

        Default implementation uses to_dict(), but can be overridden.
        """
        import json

        data = self.to_dict()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
```

By implementing the `to_dict()` and `pretty_print()` methods, tasks can easily export results to dictionaries and display them in the console.

#### Example: Detection-Specific Task

Here's an example of a specialized task mimicking detectors:

```python

class DetectionTask(AITask):
    """Base class for AI tasks that produce detection-style results.

    This is a specialized AITask for security audits, bug detection,
    and similar tasks that produce a list of findings/detections.
    """

    def __init__(self, detections: List[Tuple[str, 'AIDetection']], working_dir: Path):
        self.detections = detections
        self.working_dir = working_dir

    def get_task_type(self) -> str:
        """Return the task type identifier."""
        return "detection-task"

    def pretty_print(self, console: "Console") -> None:
        """Print detections using the detection printer."""
        from .detections import print_ai_detection

        if self.detections:
            console.print(f"\n[bold]Found {len(self.detections)} detection(s):[/bold]")
            for detector_name, detection in self.detections:
                print_ai_detection(detector_name, detection, console)
        else:
            console.print(f"\n[yellow]No detections found[/yellow]")

        # Always show where full results are
        console.print(f"\n[dim]Full results available in:[/dim] {self.working_dir}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert all detections to dictionary format."""
        return {
            "task_type": self.get_task_type(),
            "detections": [
                {
                    "detector": detector_name,
                    **detection.to_dict()
                }
                for detector_name, detection in self.detections
            ],
            "working_directory": str(self.working_dir),
            "total_detections": len(self.detections)
        }

    def export_json(self, path: Path) -> None:
        """Use the existing export function for detection consistency."""
        from .detections import export_ai_detections_json
        export_ai_detections_json(self.detections, path)
```

The core runner handles output by calling either `pretty_print()` or `to_dict()` based on whether the user wants console output or has specified the `--export` flag.

This flexible architecture allows us to define new task types (e.g., fuzzing) that can have different output formats. For example, `wake ai fuzz` could return specialized fuzzing results or simply print to the console, and export functionality can be customized or disabled for specific task types.


## Todo
- [ ] Extract `framework` into a separate module + repo
- [ ] Add auto remove working folder option
- [ ] Sandbox Claude Code
- [ ] Enable defining AI flows in `wake_ai` folder under private repo
- [ ] Reach consensus on AI framework name
    - ***Trace*** – simple, clean, post-hoc or live path tracking; modern and very product-ready.
    - ***Tasks*** - simple, could also bre well marketed, i.e. we are introducing wake tasks
      - alternatively we could just swap `wake ai` for `wake task`, looks nice
    - ***Shikoro*** – "reasoning in motion"; also sounds a bit like a stylized Japanese name.
    - ***Michi*** – philosophical, elegant, the Way (道); perfect for a framework guiding agents.
    - ***Shikō*** – internal reasoning, decision-making; evokes the "mind" of the agent.
    - ***Kōro*** – technical, directional, navigating dynamic environments; feels advanced and system-level.
    - ***Sendō*** (先導) –  "Guidance / Leading the way" Suggests an agent that leads or follows intelligently.
- [ ] Reach consensus on AI detector output structure

1. Pure YAML with structured content blocks
```yaml
- name: Reentrancy in approve()
- severity: high
- detection_type: vulnerability
- location:
    - file: contracts/Token.sol
    - lines: 42-47
    - function: approve
description:
  - type: text
    content: |
      The `approve()` function does not emit an Approval event.
  - type: code
    source: CatCoin.sol
    language: solidity
    linenums: "42-47"
    content: |
      function approve(...) { ... }
```

1. YAML with Markdown/ADOC
```yaml
- name: Reentrancy in approve()
- severity: high
- detection_type: vulnerability
- location:
    - file: contracts/Token.sol
    - lines: 42-47
    - function: approve
description: |
  The `approve()` function does not emit an Approval event.

  ``solidity [CatCoin.sol:42-47]
  function approve(...) { ... }
  ``
```

3. Multi-file Structure (YAML + Markdown/ADOC Files)
```
catcoin-missing-approval-event/
  ├── meta.yaml
  ├── description.adoc
  ├── exploit.adoc
  └── recommendation.adoc
```

## Notes
- Steps can be dynamically added in between workflow steps by including a `after-step` hook
- Sessions can be resumed in between sessions by using the `resume` flag, by default new ones are created
  - This makes it possible to create different agents for each step, i.e. audit agent, validation agent, etc.
- Detector currently returns empty `DetectorResult[]` (AI results in working directory). If AI returns results into a JSON file, the detector will return the file contents as a `DetectorResult`
- Max costs can be exceeded in the current implementation and serve more like a guardrail than a hard limit.
  - A potential solution could be to request the session to be finished quicker once we exceed a percentage (i.e. 80%) of the max cost limit
- YAML files could be a good candidate for storing results, as they are human readable and can be easily parsed.
- Sandboxing Claude Code is not implemented atm, but should be added before running on servers.



