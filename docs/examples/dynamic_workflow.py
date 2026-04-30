"""Example workflow demonstrating dynamic step generation.

This workflow:
1. Analyzes Python files to find classes
2. Dynamically generates investigation steps for each class found
3. Summarizes all findings
"""

import re
import rich_click as click
from wake_ai import AIWorkflow, DynamicWorkflowStep, workflow


class DynamicAnalysisWorkflow(AIWorkflow):
    """Workflow that dynamically creates steps based on initial analysis."""

    def __init__(self, **kwargs):
        """Initialize the workflow."""
        super().__init__(**kwargs)

    @workflow.command("dynamic-analysis")
    @click.option("--target-dir", "-d", type=str, default=".", help="Directory to analyze")
    def cli(self, target_dir):
        """Run dynamic analysis workflow."""
        self.target_dir = target_dir

    def _setup_steps(self):
        """Setup initial workflow steps."""
        # Step 1: Find all Python classes
        find_step = self.add_step(
            name="find_classes",
            prompt_template="""Find all Python classes in {{target_dir}}.

For each class found, write one line per class to {{working_dir}}/classes.txt:
path/to/file.py:ClassName:42
""",
            model="claude-opus-4-5",
            max_cost=3.0
        )

        # Dynamic step: generate one investigation step per discovered class
        self.add_dynamic_step(
            name="investigate_classes",
            handler=self._investigate_classes_handler,
            requires=[find_step],
        )

        # Final step: Summarize findings
        self.add_step(
            name="summarize",
            prompt_template="""Create a summary report in {{working_dir}}/summary.md of all class analyses found in {{working_dir}}.

Include:
- Total number of classes analyzed
- Key patterns or observations
- Any potential issues or improvements
""",
            model="claude-opus-4-5",
            max_cost=2.0
        )

    async def _investigate_classes_handler(self, _step: DynamicWorkflowStep) -> None:
        """Spawn one WorkflowStep per class found by find_classes."""
        classes_file = self.working_dir / "classes.txt"
        if not classes_file.exists():
            return

        # Pattern: path/to/file.py:ClassName:42
        pattern = re.compile(r'^(.+):(\w+):(\d+)$')
        matches = []
        for line in classes_file.read_text().splitlines():
            m = pattern.match(line.strip())
            if m:
                matches.append(m.groups())

        for i, (file_path, class_name, line_num) in enumerate(matches[:5]):  # Limit to 5
            self.add_step(
                name=f"investigate_class_{i}_{class_name.lower()}",
                prompt_template=f"""Analyze the class {class_name} in {file_path} (around line {line_num}).

Provide:
1. Purpose and responsibility of the class
2. Key methods and their functionality
3. Any design patterns used
4. Potential improvements or issues

Write your analysis to {{{{working_dir}}}}/{class_name.lower()}_analysis.md""",
                model="claude-opus-4-5",
                max_cost=1.5,
            )


if __name__ == "__main__":
    # Example usage
    wf = DynamicAnalysisWorkflow()
    wf.add_context("target_dir", "wake_ai/core")

    result = wf.run()
    print(f"\nWorkflow status: {result.status}")
