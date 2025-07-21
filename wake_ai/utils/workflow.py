"""Workflow-related utility functions."""

import json
from pathlib import Path
from typing import Dict, Any, Union, List

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from ..core import AIWorkflow


def load_workflow_from_file(workflow_file: Union[str, Path]) -> AIWorkflow:
    """Load a custom workflow from a YAML or JSON file.

    Args:
        workflow_file: Path to the workflow definition file

    Returns:
        Configured AIWorkflow instance
    """
    path = Path(workflow_file)

    if path.suffix in ['.yaml', '.yml']:
        if not HAS_YAML:
            raise ImportError(
                "YAML support requires PyYAML. Install it with: pip install pyyaml"
            )
        with open(path) as f:
            config = yaml.safe_load(f)
    elif path.suffix == '.json':
        with open(path) as f:
            config = json.load(f)
    else:
        raise ValueError(f"Unsupported workflow file format: {path.suffix}")

    # Create custom workflow class
    class CustomWorkflow(AIWorkflow):
        def _setup_steps(self):
            for step_config in config.get('steps', []):
                self.add_step(
                    name=step_config['name'],
                    prompt_template=step_config['prompt'],
                    tools=step_config.get('tools')
                )

    # Create and return workflow instance
    workflow = CustomWorkflow(
        name=config.get('name', 'custom_workflow')
    )

    return workflow


def create_workflow_template(output_file: Union[str, Path]):
    """Create a template workflow file for users to customize.

    Args:
        output_file: Path to save the template
    """
    template = {
        "name": "example_workflow",
        "description": "Example workflow template",
        "steps": [
            {
                "name": "analyze",
                "prompt": "Analyze the codebase in {directory}",
                "tools": ["read", "grep"]
            },
            {
                "name": "report",
                "prompt": "Generate a report based on: {analyze_output}",
                "tools": []
            }
        ]
    }

    path = Path(output_file)

    if path.suffix in ['.yaml', '.yml']:
        if not HAS_YAML:
            # Fallback to JSON if YAML not available
            path = path.with_suffix('.json')
        else:
            with open(path, 'w') as f:
                yaml.dump(template, f, default_flow_style=False)
            return

    # Write as JSON (default or fallback)
    with open(path, 'w') as f:
        json.dump(template, f, indent=2)


def parse_tool_list(tools_str: str) -> List[str]:
    """Parse a comma-separated list of tools.

    Args:
        tools_str: Comma-separated tool names

    Returns:
        List of tool names
    """
    if not tools_str:
        return []

    return [tool.strip() for tool in tools_str.split(',') if tool.strip()]


def format_workflow_results(results: Dict[str, Any], output_format: str = "text") -> str:
    """Format workflow results for display.

    Args:
        results: Workflow execution results
        output_format: Output format (text, json, markdown)

    Returns:
        Formatted results string
    """
    if output_format == "json":
        return json.dumps(results, indent=2)

    elif output_format == "markdown":
        md_lines = [
            f"# Workflow: {results.get('workflow', 'Unknown')}",
            "",
            "## Summary",
            f"- Completed Steps: {len(results.get('completed_steps', []))}",
            f"- Errors: {len(results.get('errors', []))}",
            f"- Duration: {results.get('duration', 'N/A')} seconds",
            f"- Total cost: ${results.get('total_cost', 'N/A')}",
            "",
            "## Completed Steps",
        ]

        for step in results.get('completed_steps', []):
            md_lines.append(f"- ✓ {step}")

        if results.get('errors'):
            md_lines.extend([
                "",
                "## Errors",
            ])
            for error in results['errors']:
                md_lines.append(f"- **{error['step']}**: {error['error']}")

        return "\n".join(md_lines)

    else:  # text format
        lines = [
            f"Workflow: {results.get('workflow', 'Unknown')}",
            f"Completed: {len(results.get('completed_steps', []))} steps",
            f"Duration: {results.get('duration', 'N/A')} seconds",
        ]

        if results.get('errors'):
            lines.append(f"Errors: {len(results['errors'])}")

        return "\n".join(lines)