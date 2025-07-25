"""Example workflow demonstrating dynamic step generation.

This workflow:
1. Analyzes Python files to find classes
2. Dynamically generates investigation steps for each class found
3. Summarizes all findings
"""

import re
from typing import Dict, Any, List
from wake_ai import AIWorkflow, WorkflowStep
from wake_ai.core.claude import ClaudeCodeResponse


class DynamicAnalysisWorkflow(AIWorkflow):
    """Workflow that dynamically creates steps based on initial analysis."""
    
    def __init__(self, target_dir: str = ".", **kwargs):
        self.target_dir = target_dir
        super().__init__(name="dynamic_analysis", **kwargs)
    
    def _setup_steps(self):
        """Setup initial workflow steps."""
        # Step 1: Find all Python classes
        self.add_step(
            name="find_classes",
            prompt_template="""Find all Python classes in {{target_dir}}.
            
For each class found, output:
- File path
- Class name  
- Line number where class is defined

Format your response as a numbered list like:
1. `path/to/file.py` - ClassName (line 42)
2. `another/file.py` - AnotherClass (line 15)
""",
            allowed_tools=["Glob", "Grep", "Read"],
            max_cost=3.0
        )
        
        # Register dynamic step generator
        self.add_dynamic_steps(
            name="investigate_classes",
            generator=self._generate_class_investigation_steps,
            after_step="find_classes"
        )
        
        # Final step: Summarize findings
        self.add_step(
            name="summarize",
            prompt_template="""Create a summary of all the classes you've analyzed.

Include:
- Total number of classes analyzed
- Key patterns or observations
- Any potential issues or improvements

{% for step_name in _completed_steps %}
{% if step_name.startswith('investigate_class_') %}
## {{ step_name }}
{{ _get_output(step_name) }}

{% endif %}
{% endfor %}
""",
            max_cost=2.0
        )
    
    def _generate_class_investigation_steps(self, response: ClaudeCodeResponse, 
                                          context: Dict[str, Any]) -> List[WorkflowStep]:
        """Generate investigation steps for each class found."""
        # Parse classes from the response
        content = response.content
        
        # Pattern to match our expected format: 1. `path/file.py` - ClassName (line N)
        pattern = r'\d+\.\s*`([^`]+)`\s*-\s*(\w+)\s*\(line\s*(\d+)\)'
        matches = re.findall(pattern, content)
        
        steps = []
        for i, (file_path, class_name, line_num) in enumerate(matches[:5]):  # Limit to 5 classes
            steps.append(WorkflowStep(
                name=f"investigate_class_{i}_{class_name.lower()}",
                prompt_template=f"""Analyze the class {class_name} in {file_path} (around line {line_num}).

Provide:
1. Purpose and responsibility of the class
2. Key methods and their functionality
3. Any design patterns used
4. Potential improvements or issues

Keep your analysis concise (3-5 sentences per section).""",
                allowed_tools=["Read"],
                max_cost=1.5,
                continue_session=False  # Each investigation gets fresh context
            ))
        
        if not steps:
            # No classes found, add a placeholder step
            steps.append(WorkflowStep(
                name="no_classes_found",
                prompt_template="No Python classes were found in the target directory. Please verify the directory contains Python files.",
                max_cost=0.1
            ))
        
        return steps
    
    def _custom_context_update(self, step_name: str, response: ClaudeCodeResponse):
        """Store outputs for the summary step."""
        # Make completed steps and outputs available to templates
        if not hasattr(self.state.context, '_completed_steps'):
            self.state.context['_completed_steps'] = []
            self.state.context['_outputs'] = {}
        
        self.state.context['_completed_steps'].append(step_name)
        self.state.context['_outputs'][step_name] = response.content
        
        # Helper function for templates
        self.state.context['_get_output'] = lambda name: self.state.context['_outputs'].get(name, '')


if __name__ == "__main__":
    # Example usage
    workflow = DynamicAnalysisWorkflow(target_dir="wake_ai/core")
    
    # Add initial context
    workflow.add_context("target_dir", "wake_ai/core")
    
    # Execute workflow
    results, ai_result = workflow.execute()
    
    print("\n=== Workflow Results ===")
    print(f"Total steps executed: {len(workflow.state.completed_steps)}")
    print(f"Dynamic steps added: {len([s for s in workflow.state.completed_steps if 'investigate_class_' in s])}")
    
    if ai_result.success:
        print("\nWorkflow completed successfully!")
        print(f"\nSummary:\n{results.get('summarize_output', 'No summary available')}")
    else:
        print("\nWorkflow failed!")
        print(f"Errors: {ai_result.error}")