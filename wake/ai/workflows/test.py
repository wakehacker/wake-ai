"""Simple test workflow implementation."""

from ..flow import AIWorkflow


class TestWorkflow(AIWorkflow):
    """Simple test workflow with two greeting steps."""

    def __init__(self, session=None):
        """Initialize test workflow.

        Args:
            session: Claude session to use
        """
        super().__init__("test_workflow", session=session)

    def _setup_steps(self):
        """Setup the test workflow steps."""
        
        # Step 1: Say hi
        self.add_step(
            name="say_hi",
            prompt_template="Please respond with exactly 'Hi!' and nothing else.",
            tools=[],  # No tools needed
            context_keys=[],
            max_cost=0.1  # Very low cost since it's simple
        )

        # Step 2: Ask how are you
        self.add_step(
            name="ask_how_are_you",
            prompt_template="Please respond with exactly 'How are you?' and nothing else.",
            tools=[],  # No tools needed
            context_keys=["say_hi_output"],  # Can access previous output if needed
            max_cost=0.1
        )