"""Example workflow demonstrating custom result types."""

from typing import Dict, Any

from wake.ai.flow import AIWorkflow, AIResult
from wake.ai.results import SimpleResult


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
    
    def format_results(self, results: Dict[str, Any]) -> AIResult:
        """Return a simple key-value result."""
        # In a real workflow, you'd parse the Claude response
        # and extract structured data
        return SimpleResult({
            "workflow": self.name,
            "status": "completed",
            "working_directory": str(self.working_dir),
            "steps_completed": len(self.state.completed_steps),
            "total_cost": results.get("total_cost", 0)
        })
    
    @classmethod
    def get_cli_options(cls) -> Dict[str, Any]:
        """No special options for this example."""
        return {}
    
    @classmethod 
    def process_cli_args(cls, **kwargs) -> Dict[str, Any]:
        """No special processing needed."""
        return {}