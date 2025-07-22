"""Example workflow demonstrating custom result types."""

from typing import Dict, Any

from wake_ai.core.flow import AIWorkflow
from wake_ai.results import SimpleResult


class ExampleWorkflow(AIWorkflow):
    """Example workflow that demonstrates custom result formatting."""
    
    name = "example"
    allowed_tools = ["Read", "Write", "Bash", "Grep"]
    
    def __init__(self, **kwargs):
        """Initialize example workflow with SimpleResult."""
        super().__init__(
            name=self.name,
            result_class=SimpleResult,
            **kwargs
        )
    
    def _setup_steps(self):
        """Setup a simple workflow with one step."""
        self.add_step(
            name="analyze",
            prompt_template="""
You are analyzing a codebase. Please:
1. Count the number of Solidity files
2. List the main contracts
3. Provide a brief summary

Working directory: {{working_dir}}
""",
            allowed_tools=["bash", "grep", "read"],
            max_cost=5.0
        )
    
    
    @classmethod
    def get_cli_options(cls) -> Dict[str, Any]:
        """No special options for this example."""
        return {}
    
    @classmethod 
    def process_cli_args(cls, **kwargs) -> Dict[str, Any]:
        """No special processing needed."""
        return {}