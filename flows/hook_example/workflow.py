"""Example workflow demonstrating the use of pre/post step hooks."""

import logging
from datetime import datetime
from typing import Dict, Any
from pathlib import Path
import json

from wake_ai.core import AIWorkflow, WorkflowStep, ClaudeCodeResponse
from wake_ai.results import SimpleResult

logger = logging.getLogger(__name__)


class HookExampleWorkflow(AIWorkflow):
    """Example workflow that demonstrates pre/post step hooks for monitoring and logging."""
    
    name = "hook-example"
    allowed_tools = ["Read", "Write", "Grep", "Glob", "LS"]
    
    def __init__(self, **kwargs):
        """Initialize the hook example workflow."""
        # Track metrics for demonstration
        self.step_start_times = {}
        self.step_costs = {}
        
        super().__init__(
            name=self.name,
            result_class=SimpleResult,
            **kwargs
        )
    
    def _setup_steps(self):
        """Setup workflow steps - hooks are at workflow level only."""
        
        # Step 1: Analyze project structure
        self.add_step(
            name="analyze_structure",
            prompt_template="""Analyze the project structure in {working_dir}.
            List all files and directories and create a summary in structure.txt""",
            tools=["LS", "Write"],
            max_cost=2.0
        )
        
        # Step 2: Count files by extension
        self.add_step(
            name="count_files",
            prompt_template="""Count the number of files by extension in the project.
            Create a report in file_count.txt with the results.""",
            tools=["Glob", "Write"],
            max_cost=3.0
        )
        
        # Step 3: Generate final report with dynamic context
        self.add_step(
            name="generate_report",
            prompt_template="""Generate a final report in report.md that includes:
            - Project structure summary
            - File count statistics
            - Timestamp: {report_timestamp}
            - Total workflow cost so far: ${total_cost:.4f}
            - Step number: {step_number} of {total_steps}""",
            tools=["Read", "Write"],
            max_cost=2.0
        )
    
    # Workflow-level hooks that apply to all steps
    
    def _pre_step_hook(self, step: WorkflowStep) -> None:
        """Called before each step execution."""
        logger.info(f"[PRE-STEP] Starting step '{step.name}'")
        logger.info(f"  - Max cost limit: ${step.max_cost or 'unlimited'}")
        logger.info(f"  - Allowed tools: {step.tools or self.allowed_tools}")
        
        # Track step start time
        self.step_start_times[step.name] = datetime.now()
        
        # Add dynamic context based on the step
        if step.name == "generate_report":
            # Calculate total cost from previous steps
            total_cost = sum(self.step_costs.values())
            
            # Add dynamic context directly to self.state.context
            self.state.context["report_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.state.context["total_cost"] = total_cost
            logger.info(f"  - Added report context: timestamp and total cost ${total_cost:.4f}")
        
        # Always add step counter
        self.state.context["step_number"] = self.state.current_step + 1
        self.state.context["total_steps"] = len(self.steps)
    
    def _post_step_hook(self, step: WorkflowStep, response: ClaudeCodeResponse) -> None:
        """Called after each step execution."""
        # Calculate step duration
        if step.name in self.step_start_times:
            duration = (datetime.now() - self.step_start_times[step.name]).total_seconds()
        else:
            duration = 0
        
        # Track step cost
        self.step_costs[step.name] = response.cost
        
        logger.info(f"[POST-STEP] Completed step '{step.name}'")
        logger.info(f"  - Duration: {duration:.2f} seconds")
        logger.info(f"  - Cost: ${response.cost:.4f}")
        logger.info(f"  - Success: {response.success}")
        logger.info(f"  - Turns: {response.num_turns}")
        
        # Save metrics to file
        self._save_step_metrics(step, response, duration)
    
    def _save_step_metrics(self, step: WorkflowStep, response: ClaudeCodeResponse, duration: float) -> None:
        """Save step metrics to a JSON file."""
        metrics_file = self.working_dir / "metrics.json"
        
        # Create metric entry
        metric = {
            "step": step.name,
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": duration,
            "cost": response.cost,
            "success": response.success,
            "turns": response.num_turns,
            "session_id": response.session_id or "N/A"
        }
        
        # Load existing metrics or create new list
        if metrics_file.exists():
            metrics = json.loads(metrics_file.read_text())
        else:
            metrics = []
        
        # Append and save
        metrics.append(metric)
        metrics_file.write_text(json.dumps(metrics, indent=2))
        logger.debug(f"Saved metrics for step '{step.name}' to {metrics_file}")
    
    @classmethod
    def get_cli_options(cls) -> Dict[str, Any]:
        """No special CLI options for this example."""
        return {}
    
    @classmethod
    def process_cli_args(cls, **kwargs) -> Dict[str, Any]:
        """No special argument processing needed."""
        return {}