"""Example workflow demonstrating conditional steps."""

from wake_ai import AIWorkflow, WorkflowStep
from wake_ai.results import MessageResult
from typing import Dict, Any


class ConditionalWorkflow(AIWorkflow):
    """Example workflow demonstrating conditional steps.
    
    This workflow shows how to use both lambda functions and class methods
    as conditions for controlling step execution.
    """
    
    def __init__(self, threshold: int = 5, **kwargs):
        """Initialize the workflow.
        
        Args:
            threshold: Threshold value for conditional logic
            **kwargs: Additional workflow arguments
        """
        self.threshold = threshold
        super().__init__(name="conditional_example", result_class=MessageResult, **kwargs)
        # Add threshold to context
        self.add_context("threshold", threshold)
    
    def _setup_steps(self):
        """Define workflow steps with conditions."""
        
        # Step 1: Always runs - analyze input
        self.add_step(
            name="analyze",
            prompt_template="""Analyze the codebase and count the number of Python files.
            
            Save the count to 'file_count.txt' in {{working_dir}}.
            Report the exact number found.""",
            allowed_tools=["Glob", "Write"]
        )
        
        # Step 2: Conditional using lambda - only runs if many files found
        self.add_step(
            name="large_project_analysis",
            prompt_template="""This is a large project with {{file_count}} Python files.
            
            Create a file 'large_project_notes.txt' in {{working_dir}} with:
            - Recommendations for organizing large codebases
            - Suggested project structure improvements
            """,
            allowed_tools=["Write"],
            condition=lambda ctx: int(ctx.get("file_count", 0)) > ctx.get("threshold", 5)
        )
        
        # Step 3: Conditional using class method - only runs if few files  
        self.add_step(
            name="small_project_analysis",
            prompt_template="""This is a small project with {{file_count}} Python files.
            
            Create a file 'small_project_notes.txt' in {{working_dir}} with:
            - Quick wins for small projects
            - Suggested next steps for growth
            """,
            allowed_tools=["Write"],
            condition=self._is_small_project  # Using class method as condition
        )
        
        # Step 4: Always runs - summary
        self.add_step(
            name="summary",
            prompt_template="""Create a project analysis summary.
            
            Project details:
            - Python files found: {{file_count}}
            - Threshold for large project: {{threshold}}
            - Analysis performed: {{completed_steps}}
            - Analysis skipped: {{skipped_steps}}
            
            Save the summary to 'summary.txt' in {{working_dir}}.""",
            allowed_tools=["Write"]
        )
    
    def _is_small_project(self, context: Dict[str, Any]) -> bool:
        """Check if this is a small project based on file count.
        
        This is an example of using a class method as a condition function.
        It has access to self and can use instance variables.
        """
        file_count = int(context.get("file_count", 0))
        # Small project if file count <= threshold
        return file_count <= self.threshold
    
    def _custom_context_update(self, step_name: str, response):
        """Extract the file count from the analysis step."""
        if step_name == "analyze":
            # Parse the file count from the response
            import re
            match = re.search(r'\b(\d+)\b', response.content)
            if match:
                self.add_context("file_count", int(match.group(1)))
                
    def _pre_step_hook(self, step: WorkflowStep):
        """Add dynamic context before summary step."""
        if step.name == "summary":
            # Add lists of completed and skipped steps
            self.add_context("completed_steps", ", ".join(self.state.completed_steps))
            self.add_context("skipped_steps", ", ".join(self.state.skipped_steps) if self.state.skipped_steps else "None")