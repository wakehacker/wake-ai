"""Security audit workflow implementation."""

from pathlib import Path
from typing import List, Optional, Dict, Any

from wake.ai.claude import ClaudeCodeSession

from ..flow import AIWorkflow, WorkflowStep, ClaudeCodeResponse


class AuditWorkflow(AIWorkflow):
    """Fixed security audit workflow following industry best practices."""

    def __init__(
        self,
        scope_files: Optional[List[str]] = None,
        context_docs: Optional[List[str]] = None,
        focus_areas: Optional[List[str]] = None,
        session: Optional[ClaudeCodeSession] = None,
        model: Optional[str] = None,
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

        # Load prompts from markdown files before parent init
        self._load_prompts()

        # Now call parent init which will call _setup_steps
        super().__init__(name="audit", session=session, model=model)

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
        """Build prompt with context injection points."""
        base_prompt = self.prompts[step_name]

        # Add scope information
        if self.scope_files:
            scope_section = f"\n\nFILES IN SCOPE:\n" + "\n".join(f"- {f}" for f in self.scope_files)
        else:
            scope_section = "\n\nSCOPE: Entire codebase"

        # Add context documents
        if self.context_docs:
            context_section = f"\n\nADDITIONAL CONTEXT:\n" + "\n".join(f"- {doc}" for doc in self.context_docs)
        else:
            context_section = ""

        # Add focus areas
        if self.focus_areas:
            focus_section = f"\n\nFOCUS AREAS:\n" + "\n".join(f"- {area}" for area in self.focus_areas)
        else:
            focus_section = ""

        return base_prompt + scope_section + context_section + focus_section

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

        # Add audit-specific results
        results["audit_report_path"] = ".audit/"
        results["issues_found"] = len(self.state.context.get("confirmed_issues", []))

        return results