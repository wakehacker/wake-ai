"""Security audit workflow implementation."""

from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Union

from wake.ai.claude import ClaudeCodeSession

from ..flow import AIWorkflow, WorkflowStep, ClaudeCodeResponse


class AuditWorkflow(AIWorkflow):
    """Fixed security audit workflow following industry best practices."""

    name = "audit"
    # Default tools for auditing - needs read and write capabilities
    allowed_tools = ["Read", "Grep", "Glob", "LS", "Task", "TodoWrite", "Write", "Edit", "MultiEdit"]

    def __init__(
        self,
        scope_files: Optional[List[str]] = None,
        context_docs: Optional[List[str]] = None,
        focus_areas: Optional[List[str]] = None,
        session: Optional[ClaudeCodeSession] = None,
        model: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
        execution_dir: Optional[Union[str, Path]] = None,
        **kwargs
    ):
        """Initialize security audit workflow.

        Args:
            scope_files: List of files to audit (None = entire codebase)
            context_docs: Additional documentation/context files
            focus_areas: Specific vulnerabilities or ERCs to focus on
            session: Claude session to use
        """
        self.scope_files = scope_files or []
        self.context_docs = context_docs or []
        self.focus_areas = focus_areas or []

        self.add_context("scope_files", self.scope_files)
        self.add_context("context_docs", self.context_docs)
        self.add_context("focus_areas", self.focus_areas)

        # Load prompts from markdown files before parent init
        self._load_prompts()

        # Now call parent init which will call _setup_steps
        super().__init__(name=self.name, session=session, model=model, working_dir=working_dir, execution_dir=execution_dir, **kwargs)

    def _load_prompts(self):
        """Load audit prompts from markdown files."""
        prompts_dir = Path(__file__).parent.parent / "prompts"

        self.prompts = {}
        # Using the modular approach (1-4 steps)
        prompt_files = [
            ("analyze_and_plan", "1-analyze-and-plan.md"),
            ("static_analysis", "2-static-analysis.md"),
            ("manual_review", "3-manual-review.md"),
            ("executive_summary", "4-executive-summary.md")
        ]

        for key, filename in prompt_files:
            prompt_path = prompts_dir / filename
            if prompt_path.exists():
                self.prompts[key] = prompt_path.read_text()
            else:
                raise FileNotFoundError(f"Audit prompt not found: {prompt_path}")

    def _setup_steps(self):
        """Setup the fixed audit workflow steps."""

        # Step 1: Analyze and Plan
        self.add_step(
            name="analyze_and_plan",
            prompt_template=self._build_prompt("analyze_and_plan"),
            tools=["read", "search", "write", "grep", "bash"],
            max_cost=10.0
        )

        # Step 2: Static Analysis
        self.add_step(
            name="static_analysis",
            prompt_template=self._build_prompt("static_analysis"),
            tools=["read", "write", "bash", "edit"],
            max_cost=10.0
        )

        # Step 3: Manual Review
        self.add_step(
            name="manual_review",
            prompt_template=self._build_prompt("manual_review"),
            tools=["read", "write", "search", "grep", "edit"],
            max_cost=10.0
        )

        # Step 4: Executive Summary
        self.add_step(
            name="executive_summary",
            prompt_template=self._build_prompt("executive_summary"),
            tools=["read", "write"],
            max_cost=10.0
        )

    def _build_prompt(self, step_name: str) -> str:
        """Build prompt"""
        base_prompt = self.prompts[step_name]
        return base_prompt

    def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Execute the audit workflow with proper context setup."""
        # Initialize context with audit-specific information
        audit_context = {
            "scope": ', '.join(self.scope_files) if self.scope_files else 'entire codebase',
            "additional_context": ', '.join(self.context_docs) if self.context_docs else 'none',
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