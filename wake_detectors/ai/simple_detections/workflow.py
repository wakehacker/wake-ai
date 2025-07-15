"""Simple detection workflow for finding vulnerabilities."""

from pathlib import Path
from typing import List, Optional, Dict, Any

from wake.ai.flow import AIWorkflow


class SimpleDetectionsWorkflow(AIWorkflow):
    """Simple detection workflow that directly finds vulnerabilities."""

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
        """Initialize simple detection workflow.

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
        super().__init__("simple_detections", session=session, model=model, working_dir=working_dir, execution_dir=execution_dir, **kwargs)

    def _load_prompts(self):
        """Load detection prompt."""
        prompts_dir = Path(__file__).parent / "prompts"

        self.prompts = {}
        # Single step - direct detection
        prompt_files = [
            ("find_detections", "find-detections.md")
        ]

        for key, filename in prompt_files:
            prompt_path = prompts_dir / filename
            if prompt_path.exists():
                self.prompts[key] = prompt_path.read_text()
            else:
                raise FileNotFoundError(f"Detection prompt not found: {prompt_path}")

    def _setup_steps(self):
        """Setup the simple detection workflow."""

        # Single Step: Find Detections
        self.add_step(
            name="find_detections",
            prompt_template=self.prompts["find_detections"],
            max_cost=15.0
        )

    def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Execute the detection workflow with proper context setup."""
        # Initialize context with detection-specific information
        detection_context = {
            "scope_files": ', '.join(self.scope_files) if self.scope_files else 'entire codebase',
            "context_docs": ', '.join(self.context_docs) if self.context_docs else 'none',
            "focus_areas": ', '.join(self.focus_areas) if self.focus_areas else "general security detection"
        }

        if context:
            detection_context.update(context)

        # Execute the workflow
        results = super().execute(context=detection_context, **kwargs)

        return results

    @classmethod
    def get_cli_options(cls) -> Dict[str, Any]:
        """Return detection workflow CLI options."""
        import click
        return {
            "scope": {
                "param_decls": ["-s", "--scope"],
                "multiple": True,
                "type": click.Path(exists=True),
                "help": "Files/directories in detection scope (default: entire codebase)"
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
        """Process CLI arguments for detection workflow."""
        return {
            "scope_files": list(kwargs.get("scope", [])),
            "context_docs": list(kwargs.get("context", [])),
            "focus_areas": list(kwargs.get("focus", []))
        }