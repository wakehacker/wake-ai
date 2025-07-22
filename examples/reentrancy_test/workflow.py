"""Reentrancy vulnerability detector using Wake's built-in detection capabilities."""

from pathlib import Path
from wake_ai.core.flow import AIWorkflow
from wake_ai.templates.markdown_detector import MarkdownDetectorResult


class ReentrancyTestWorkflow(AIWorkflow):
    """Enhanced reentrancy detector that leverages Wake's static analysis."""

    name = "reentrancy-test"

    def __init__(self, **kwargs):
        """Initialize the reentrancy test workflow."""
        super().__init__(
            name=self.name,
            result_class=MarkdownDetectorResult,
            working_dir=Path.cwd() / ".wake" / "ai" / "20250722_132749_huu0ew",
            **kwargs
        )

    def _setup_steps(self):
        """Setup the reentrancy test workflow."""
        pass