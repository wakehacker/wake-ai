"""Simple test workflow implementation."""

from typing import Dict, Any
from wake.ai.flow import AIWorkflow


class TestWorkflow(AIWorkflow):
    """Simple test workflow with two greeting steps."""
    
    name = "test"
    # Test workflow doesn't need any tools
    allowed_tools = []

    def __init__(self, session=None, model=None, working_dir=None, execution_dir=None, **kwargs):
        """Initialize test workflow.

        Args:
            session: Claude session to use (optional)
            model: Model name to create session with (ignored if session provided)
            working_dir: Directory for AI to work in
            execution_dir: Directory where Claude CLI is executed
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(self.name, session=session, model=model, working_dir=working_dir, execution_dir=execution_dir, **kwargs)

    def _setup_steps(self):
        """Setup the test workflow steps."""

        # Step 1: Say hi
        self.add_step(
            name="say_hi",
            prompt_template="Please respond with exactly 'Hi!' and nothing else.",
            tools=[],  # No tools needed
            max_cost=0.1  # Very low cost since it's simple
        )

        # Step 2: Ask how are you
        self.add_step(
            name="ask_how_are_you",
            prompt_template="Please respond with exactly 'How are you?' and nothing else.",
            tools=[],  # No tools needed
            max_cost=0.1
        )

    @classmethod
    def get_cli_options(cls) -> Dict[str, Any]:
        """Return test workflow CLI options."""
        return {}  # Test workflow doesn't need special options

    @classmethod
    def process_cli_args(cls, **kwargs) -> Dict[str, Any]:
        """Process CLI arguments for test workflow."""
        return {}  # No special processing needed