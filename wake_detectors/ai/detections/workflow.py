"""Security audit workflow for the detector."""

from pathlib import Path
from typing import List, Optional, Dict, Any

from wake.ai.flow import AIWorkflow


class DetectorAuditWorkflow(AIWorkflow):
    """Security audit workflow that loads prompts from detector directory."""
    
    # Default tools for detection - needs read, write, search capabilities
    allowed_tools = ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "LS", "Task", "TodoWrite", "MultiEdit"]

    def __init__(
        self,
        scope_files: Optional[List[str]] = None,
        context_docs: Optional[List[str]] = None,
        focus_areas: Optional[List[str]] = None,
        session=None,
        model: Optional[str] = "opus",
        working_dir: Optional[str] = None,
        execution_dir: Optional[str] = None,
        **kwargs
    ):
        """Initialize security audit workflow.

        Args:
            scope_files: List of files to audit (None = entire codebase)
            context_docs: Additional documentation/context files
            focus_areas: Specific vulnerabilities or ERCs to focus on
            session: Claude session to use (optional)
            model: Model name to create session with (ignored if session provided)
            working_dir: Working directory for the workflow
        """
        self.scope_files = scope_files or []
        self.context_docs = context_docs or []
        self.focus_areas = focus_areas or []

        # Load prompts from detector directory
        self._load_prompts()

        # Now call parent init which will call _setup_steps
        super().__init__("detector_audit", session=session, model=model, working_dir=working_dir, execution_dir=execution_dir, **kwargs)

    def _load_prompts(self):
        """Load audit prompts from detector's prompts directory."""
        prompts_dir = Path(__file__).parent / "prompts"

        self.prompts = {}
        # Using the detector approach (1-3 steps)
        prompt_files = [
            ("analyze_and_plan", "1-analyze-and-plan.md"),
            ("manual_review", "2-manual-review.md")
        ]

        for key, filename in prompt_files:
            prompt_path = prompts_dir / filename
            if prompt_path.exists():
                self.prompts[key] = prompt_path.read_text()
            else:
                raise FileNotFoundError(f"Audit prompt not found: {prompt_path}")

    def _setup_steps(self):
        """Setup the detector workflow steps."""

        # Step 1: Analyze and Plan
        self.add_step(
            name="analyze_and_plan",
            prompt_template=self.prompts["analyze_and_plan"],
            tools=["read", "search", "write", "grep", "bash"],
            max_cost=10.0
        )

        # Step 2: Manual Review and Generate Findings
        self.add_step(
            name="manual_review",
            prompt_template=self.prompts["manual_review"],
            tools=["read", "write", "search", "grep", "edit"],
            max_cost=10.0
        )

    def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Execute the audit workflow with proper context setup."""
        # Initialize context with audit-specific information
        audit_context = {
            "scope_files": ', '.join(self.scope_files) if self.scope_files else 'entire codebase',
            "context_docs": ', '.join(self.context_docs) if self.context_docs else 'none',
            "focus_areas": ', '.join(self.focus_areas) if self.focus_areas else "general security audit"
        }

        if context:
            audit_context.update(context)

        # Execute the workflow
        results = super().execute(context=audit_context, **kwargs)

        return results

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