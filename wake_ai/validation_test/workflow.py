"""Test workflow for validation feature.

This workflow demonstrates:
1. Validation with retry logic
2. Tool configuration (allowed and disallowed tools)

Tool configuration examples:
- tools=[]: Empty list means no tools are allowed for this step
- tools=["Read", "Grep"]: Only these specific tools are allowed
- tools=None: Use session default allowed tools
- disallowed_tools=["Bash", "Write"]: These tools are explicitly forbidden
- disallowed_tools=None: Use session default disallowed tools

Note: Tools requiring permission (Bash, Edit, Write, etc.) must be in the
allowed_tools list to be used. Tools not requiring permission (Read, Grep, etc.)
are always available unless explicitly disallowed.
"""

from typing import List, Tuple
from wake.ai.framework.flow import AIWorkflow, ClaudeCodeResponse


class ValidationTestWorkflow(AIWorkflow):
    """Test workflow to demonstrate validation with retry."""

    name = "validation_test"
    # Default tools for testing - needs write access to demonstrate validation
    allowed_tools = ["Read", "Write", "Grep", "TodoWrite", "Edit"]

    def __init__(self, session=None, model=None, working_dir=None, execution_dir=None, **kwargs):
        """Initialize validation test workflow."""
        super().__init__(self.name, session=session, model=model, working_dir=working_dir, execution_dir=execution_dir, **kwargs)

    def _setup_steps(self):
        """Setup test steps with validators."""

        # Validator that checks if a file was created with proper content
        def check_analysis_validator(response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
            from pathlib import Path
            errors = []

            # Check if the analysis file was created
            analysis_file = Path(self.working_dir) / "python_decorators_analysis.md"
            if not analysis_file.exists():
                errors.append(f"Analysis file not created at {analysis_file}")
                return (False, errors)

            # Check file content
            content = analysis_file.read_text()
            if "## Summary" not in content:
                errors.append("Missing '## Summary' section in the file")

            if "## Details" not in content:
                errors.append("Missing '## Details' section in the file")

            if len(content) < 100:
                errors.append("File content is too short (minimum 100 characters)")

            return (len(errors) == 0, errors)

        # Add a step with validation
        self.add_step(
            name="analysis",
            prompt_template="""Analyze the topic of Python decorators and create a file named 'python_decorators_analysis.md' in the working directory {working_dir} with:
            1. A section titled '## Summary'
            2. A section titled '## Details'

            The file must be comprehensive (at least 100 characters total).

            Use the Write tool to create the file.""",
            tools=["Read", "Grep", "TodoWrite", "Edit", "Write"],  # Tools that don't require permission
            validator=check_analysis_validator,
            max_retries=2
        )

        # Add a step that always fails first time
        def always_fail_first_validator(response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
            from pathlib import Path

            # Check if the file exists
            note_file = Path(self.working_dir) / "code_quality_note.txt"
            if not note_file.exists():
                return (False, ["File 'code_quality_note.txt' was not created"])

            # Check if this is a retry by looking for "FIXED" marker in the file
            content = note_file.read_text()
            if "FIXED" in content:
                return (True, [])
            else:
                return (False, ["Please add the word 'FIXED' to the file content to indicate the issue has been resolved"])

        self.add_step(
            name="fix_test",
            prompt_template="Write a brief note about code quality to a file named 'code_quality_note.txt' in {working_dir}.",
            validator=always_fail_first_validator,
            max_retries=1
        )
    
