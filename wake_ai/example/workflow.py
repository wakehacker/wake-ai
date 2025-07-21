"""Example workflow demonstrating custom result types."""

from typing import Dict, Any, Type

from wake.ai.framework.flow import AIWorkflow
from wake.ai.results import AIResult, SimpleResult


class ExampleWorkflow(AIWorkflow):
    """Example workflow that demonstrates custom result formatting."""
    
    name = "example"
    allowed_tools = ["Read", "Write", "Bash", "Grep"]
    
    def _setup_steps(self):
        """Setup a simple workflow with one step."""
        self.add_step(
            name="analyze",
            prompt_template="""
You are analyzing a codebase. Please:
1. Count the number of Solidity files
2. List the main contracts
3. Provide a brief summary

Working directory: {working_dir}
""",
            tools=["bash", "grep", "read"],
            max_cost=5.0
        )
    
    def get_result_class(self) -> Type[AIResult]:
        """Return SimpleResult for basic key-value output."""
        return SimpleResult
    
    @classmethod
    def get_cli_options(cls) -> Dict[str, Any]:
        """No special options for this example."""
        return {}
    
    @classmethod 
    def process_cli_args(cls, **kwargs) -> Dict[str, Any]:
        """No special processing needed."""
        return {}