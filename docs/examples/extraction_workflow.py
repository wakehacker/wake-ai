"""Example workflow demonstrating extraction steps."""

from pathlib import Path
from typing import List, Optional
import rich_click as click
from pydantic import BaseModel

from wake_ai import AIWorkflow, AIResult, MessageResult


class CodeIssue(BaseModel):
    """Represents a single code issue."""
    type: str
    severity: str  # low, medium, high, critical
    description: str
    file: Optional[str] = None
    line: Optional[int] = None
    suggestion: Optional[str] = None


class IssuesList(BaseModel):
    """List of code issues found."""
    issues: List[CodeIssue]
    total_files_analyzed: int = 1


class ExtractionWorkflow(AIWorkflow):
    """Example workflow showing extraction steps."""

    def __init__(self, target_file: Optional[str] = None, **kwargs):
        kwargs["name"] = "extraction_example"
        kwargs["result_class"] = MessageResult
        super().__init__(**kwargs)

        # Add target file to context
        if target_file:
            self.state.context["target_file"] = target_file
        else:
            # Use a default example file
            self.state.context["target_file"] = "example_code.py"

    def _setup_steps(self):
        """Define workflow steps."""

        # Step 1: Analyze code without format constraints
        self.add_step(
            name="analyze",
            prompt_template="""Analyze the following Python code for potential issues, bugs, or improvements.

First, read the file: {{target_file}}

Look for:
- Potential bugs or errors
- Security vulnerabilities
- Performance issues
- Code style improvements
- Best practice violations

Provide a detailed analysis of what you find.""",
            allowed_tools=None,  # Use default tools
            max_cost=2.0
        )

        # Step 2: Extract structured data from analysis
        self.add_extraction_step(
            after_step="analyze",
            output_schema=IssuesList,
            max_cost=0.5
        )

        # Step 3: Create summary using extracted data
        self.add_step(
            name="summarize",
            prompt_template="""Based on the extracted issues data, create a summary report.

The parsed data shows {{analyze_data.issues|length}} issues were found.

Create a brief summary that includes:
1. Total number of issues by severity
2. Most critical issues that need immediate attention
3. General recommendations

Format as a simple markdown report.""",
            continue_session=True,
            max_cost=1.0
        )

    def format_results(self, results):
        """Format the results."""
        # Get the summary from the last step
        summary = self.state.responses.get("summarize")
        if summary:
            return MessageResult(summary.content)

        # Fallback to showing all responses
        all_content = []
        for step_name, response in self.state.responses.items():
            all_content.append(f"## {step_name}\n{response.content}")

        return MessageResult("\n\n".join(all_content))

    @classmethod
    def get_cli_options(cls):
        """Define CLI options."""
        return {
            "target_file": {
                "param_decls": ["-f", "--file"],
                "type": click.Path(exists=True),
                "help": "Python file to analyze"
            }
        }

    @classmethod
    def process_cli_args(cls, **kwargs):
        """Process CLI arguments."""
        return {
            "target_file": kwargs.get("target_file")
        }