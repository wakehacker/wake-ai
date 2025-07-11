"""Simple test workflow implementation."""

from ..flow import AIWorkflow


class TestWorkflow(AIWorkflow):
    """Simple test workflow with two greeting steps."""

    def __init__(self, session=None, model=None, state_dir=None, working_dir=None):
        """Initialize test workflow.

        Args:
            session: Claude session to use (optional)
            model: Model name to create session with (ignored if session provided)
            state_dir: Directory to store workflow state
            working_dir: Directory for AI to work in
        """
        super().__init__("test", session=session, model=model, state_dir=state_dir, working_dir=working_dir)

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