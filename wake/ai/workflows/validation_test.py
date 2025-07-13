"""Test workflow for validation feature."""

from typing import List, Tuple
from ..flow import AIWorkflow, ClaudeCodeResponse


class ValidationTestWorkflow(AIWorkflow):
    """Test workflow to demonstrate validation with retry."""

    name = "validation_test"

    def __init__(self, session=None, model=None, working_dir=None):
        """Initialize validation test workflow."""
        super().__init__(self.name, session=session, model=model, working_dir=working_dir)

    def _setup_steps(self):
        """Setup test steps with validators."""

        # Simple validator that checks for specific content
        def check_analysis_validator(response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
            errors = []

            # Check if response contains required sections
            if "## Summary" not in response.content:
                errors.append("Missing '## Summary' section")

            if "## Details" not in response.content:
                errors.append("Missing '## Details' section")

            if len(response.content) < 100:
                errors.append("Response is too short (minimum 100 characters)")

            return (len(errors) == 0, errors)

        # Add a step with validation
        self.add_step(
            name="analysis",
            prompt_template="""Analyze the following topic and provide a response with:
            1. A section titled '## Summary'
            2. A section titled '## Details'

            Topic: Python decorators

            Make sure your response is comprehensive (at least 100 characters).""",
            validator=check_analysis_validator,
            max_retries=2,

        )

        # Add a step that always fails first time
        def always_fail_first_validator(response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
            # Check if this is a retry by looking for "FIXED" marker
            if "FIXED" in response.content:
                return (True, [])
            else:
                return (False, ["Please add the word 'FIXED' to your response to indicate the issue has been resolved"])

        self.add_step(
            name="fix_test",
            prompt_template="Write a brief note about code quality.",
            validator=always_fail_first_validator,
            max_retries=1
        )