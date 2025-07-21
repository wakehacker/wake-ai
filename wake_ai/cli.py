"""CLI interface for Wake AI."""

import click
import logging
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

# Import available workflows from flows module
from flows.audit import AuditWorkflow
from flows.example import ExampleWorkflow
from flows.test import TestWorkflow
from flows.validation_test import ValidationTestWorkflow
from flows.uniswap_detector import UniswapDetector
from flows.reentrancy_detector import ReentrancyDetector

console = Console()

# Configure logging to use rich handler for pretty console output
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)

# Register available workflows
AVAILABLE_WORKFLOWS = {
    "audit": AuditWorkflow,
    "example": ExampleWorkflow,
    "test": TestWorkflow,
    "validation-test": ValidationTestWorkflow,
    "uniswap": UniswapDetector,
    "reentrancy": ReentrancyDetector,
}


def all_workflow_options():
    """Decorator to add all workflow-specific options to a Click command."""
    def decorator(f):
        # Collect all unique options from all workflows
        all_options = {}
        for workflow_name, workflow_class in AVAILABLE_WORKFLOWS.items():
            if hasattr(workflow_class, 'get_cli_options'):
                workflow_options = workflow_class.get_cli_options()
                for opt_name, opt_config in workflow_options.items():
                    if opt_name not in all_options:
                        all_options[opt_name] = opt_config.copy()

        # Add options in reverse order (Click requirement)
        for opt_name, opt_config in reversed(list(all_options.items())):
            param_decls = opt_config.pop("param_decls", [f"--{opt_name}"])
            click.option(*param_decls, **opt_config)(f)
        return f
    return decorator


@click.command()
@click.argument(
    "workflow",
    type=click.Choice(list(AVAILABLE_WORKFLOWS.keys())),
    required=True
)
@click.option(
    "--working-dir",
    "-w",
    type=click.Path(),
    help="Working directory for AI workflow (defaults to .wake/ai/<session-id>)"
)
@click.option(
    "--model",
    "-m",
    help="Claude model to use"
)
@click.option(
    "--resume",
    is_flag=True,
    help="Resume from previous session"
)
@click.option(
    "--execution-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    help="Directory where Claude CLI is executed (defaults to current directory)"
)
@click.option(
    "--export",
    "-e",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Export detections to JSON file"
)
@click.option(
    "--no-cleanup/--cleanup",
    default=None,
    help="Don't clean up working directory after completion (default: cleanup for most workflows, keep for audit)"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging (debug level)"
)
@all_workflow_options()
@click.pass_context
def main(ctx: click.Context, **kwargs):
    """AI-powered smart contract security analysis.

    This command runs various AI workflows for smart contract analysis
    using Claude to identify potential vulnerabilities and issues.

    Examples:
        # Run audit workflow on entire codebase
        wake-ai audit

        # Audit specific files
        wake-ai audit -s contracts/Token.sol -s contracts/Vault.sol

        # Add context and focus areas
        wake-ai audit -c docs/spec.md -f reentrancy -f "access control"

        # Export results to JSON
        wake-ai audit --export results.json

        # Run example workflow
        wake-ai example

        # Resume previous session
        wake-ai --resume
    """
    # Set logging level based on verbose flag
    if kwargs.get("verbose"):
        logging.getLogger().setLevel(logging.DEBUG)
        console.print("[dim]Debug logging enabled[/dim]")

    workflow = kwargs["workflow"]
    console.print(f"[blue]Starting {workflow} workflow[/blue]")

    # Get workflow class
    workflow_class = AVAILABLE_WORKFLOWS.get(workflow)
    if not workflow_class:
        console.print(f"[red]Unknown workflow:[/red] {workflow}")
        ctx.exit(1)

    # Process arguments using workflow's processor if available
    if hasattr(workflow_class, 'process_cli_args'):
        init_args = workflow_class.process_cli_args(**kwargs)
    else:
        init_args = {}

    # Add common parameters
    if kwargs.get("model"):
        init_args["model"] = kwargs["model"]
    if kwargs.get("execution_dir"):
        init_args["execution_dir"] = kwargs["execution_dir"]
    if kwargs.get("working_dir"):
        init_args["working_dir"] = kwargs["working_dir"]
    if kwargs.get("no_cleanup") is not None:
        # CLI uses --no-cleanup flag, so invert it to get cleanup_working_dir
        init_args["cleanup_working_dir"] = not kwargs["no_cleanup"]

    try:
        # Create workflow instance
        workflow = workflow_class(**init_args)

        # Display working directory
        console.print(f"[blue]Working directory:[/blue] {workflow.working_dir}")

        # Execute workflow
        results = workflow.execute(resume=kwargs["resume"])

        # Display results
        console.print("\n[green]Workflow complete![/green]")

        # Get formatted results from the workflow
        if hasattr(workflow, 'format_results'):
            formatted_results = workflow.format_results(results)

            export_path = kwargs.get("export")

            if export_path:
                # Export to JSON
                if hasattr(formatted_results, 'export_json'):
                    formatted_results.export_json(export_path)
                    console.print(f"[green]Results exported to:[/green] {export_path}")
            else:
                # Pretty print to console
                if hasattr(formatted_results, 'pretty_print'):
                    formatted_results.pretty_print(console)
                else:
                    console.print(formatted_results)

    except KeyboardInterrupt:
        console.print("\n[yellow]Workflow interrupted. Use --resume to continue.[/yellow]")
        ctx.exit(0)
    except Exception as e:
        console.print(f"[red]Workflow failed:[/red] {e}")
        if kwargs["resume"]:
            console.print("[yellow]Try running without --resume flag[/yellow]")
        ctx.exit(1)


if __name__ == "__main__":
    main()