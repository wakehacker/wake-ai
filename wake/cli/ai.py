"""Simplified AI audit command for Wake."""

import click
from pathlib import Path
from typing import Optional, List, Tuple

from wake.cli.console import console
from wake.ai.workflows import AVAILABLE_WORKFLOWS
from wake.ai.utils import validate_claude_cli


def all_workflow_options():
    """Decorator to add all workflow-specific options to a Click command.

    Since we can't know which workflow will be selected at decoration time,
    we add all possible options from all workflows.
    """
    def decorator(f):
        # Collect all unique options from all workflows
        all_options = {}
        for workflow_name, workflow_class in AVAILABLE_WORKFLOWS.items():
            workflow_options = workflow_class.get_cli_options()
            for opt_name, opt_config in workflow_options.items():
                if opt_name not in all_options:
                    # Make a copy to avoid modifying the original
                    all_options[opt_name] = opt_config.copy()

        # Add options in reverse order (Click requirement)
        for opt_name, opt_config in reversed(list(all_options.items())):
            # Extract param_decls and create option
            param_decls = opt_config.pop("param_decls", [f"--{opt_name}"])
            click.option(*param_decls, **opt_config)(f)
        return f
    return decorator


@click.command(name="ai")
@click.option(
    "--flow",
    type=click.Choice(list(AVAILABLE_WORKFLOWS.keys())),
    default="audit",
    help="Workflow to run"
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
@all_workflow_options()  # Add all workflow options
@click.pass_context
def run_ai(ctx: click.Context, **kwargs):
        """AI-powered smart contract security audit.

        This command runs a comprehensive security audit on your smart contracts
        using Claude to identify potential vulnerabilities.

        Examples:
            # Audit entire codebase
            wake ai

            # Audit specific files
            wake ai -s contracts/Token.sol -s contracts/Vault.sol

            # Add context and focus areas
            wake ai -c docs/spec.md -f reentrancy -f "access control"
            
            # Export results to JSON
            wake ai --export results.json
        """
        # Show what we're doing
        flow = kwargs["flow"]
        working_dir = kwargs.get("working_dir")
        resume = kwargs["resume"]

        console.print(f"[blue]Starting {flow} workflow[/blue]")

        # Display workflow-specific options
        if "scope" in kwargs and kwargs["scope"]:
            console.print(f"[blue]Scope:[/blue] {', '.join(kwargs['scope'])}")
        elif flow == "audit":
            console.print("[blue]Scope:[/blue] Entire codebase")

        if "context" in kwargs and kwargs["context"]:
            console.print(f"[blue]Context files:[/blue] {', '.join(kwargs['context'])}")

        if "focus" in kwargs and kwargs["focus"]:
            console.print(f"[blue]Focus areas:[/blue] {', '.join(kwargs['focus'])}")

        # Get workflow class
        workflow_class = AVAILABLE_WORKFLOWS.get(flow)
        if not workflow_class:
            console.print(f"[red]Unknown workflow:[/red] {flow}")
            ctx.exit(1)

        # Process arguments using workflow's processor
        init_args = workflow_class.process_cli_args(**kwargs)

        # Add common parameters
        init_args["model"] = kwargs["model"]
        if kwargs.get("execution_dir"):
            init_args["execution_dir"] = kwargs["execution_dir"]
        if working_dir:
            init_args["working_dir"] = working_dir

        # Create workflow instance
        workflow = workflow_class(**init_args)

        # Display working directory
        console.print(f"[blue]Working directory:[/blue] {workflow.working_dir}")

        try:
            # Execute workflow
            results = workflow.execute(resume=resume)

            # Display basic completion message
            console.print("\n[green]Workflow complete![/green]")
            
            # Get formatted results from the workflow
            formatted_results = workflow.format_results(results)
            
            export_path = kwargs.get("export")
            
            if export_path:
                # Export to JSON using the result's export method
                formatted_results.export_json(export_path)
                console.print(f"[green]Results exported to:[/green] {export_path}")
            else:
                # Pretty print to console using the result's print method
                formatted_results.pretty_print(console)

        except KeyboardInterrupt:
            console.print("\n[yellow]Workflow interrupted. Use --resume to continue.[/yellow]")
            ctx.exit(0)
        except Exception as e:
            console.print(f"[red]Workflow failed:[/red] {e}")
            if resume:
                console.print("[yellow]Try running without --resume flag[/yellow]")
            ctx.exit(1)

