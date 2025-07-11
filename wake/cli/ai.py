"""Simplified AI audit command for Wake."""

import click
from pathlib import Path
from typing import Optional, List, Tuple

from wake.cli.console import console
from wake.ai.workflows import AVAILABLE_WORKFLOWS
from wake.ai.utils import validate_claude_cli, format_workflow_results


@click.command(name="ai")
@click.option(
    "--scope",
    "-s",
    multiple=True,
    type=click.Path(exists=True),
    help="Files/directories in audit scope (default: entire codebase)"
)
@click.option(
    "--context",
    "-c",
    multiple=True,
    type=click.Path(exists=True),
    help="Additional context files (docs, specs, etc.)"
)
@click.option(
    "--focus",
    "-f",
    multiple=True,
    help="Focus areas (e.g., 'reentrancy', 'ERC20', 'access-control')"
)
@click.option(
    "--flow",
    type=click.Choice(list(AVAILABLE_WORKFLOWS.keys())),
    default="audit",
    help="Workflow to run (future feature)"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="audit",
    help="Output directory for results"
)
@click.option(
    "--model",
    "-m",
    default="sonnet",
    help="Claude model to use"
)
@click.option(
    "--resume",
    is_flag=True,
    help="Resume from previous session"
)
@click.pass_context
def run_ai(
    ctx: click.Context,
    scope: Tuple[str, ...],
    context: Tuple[str, ...],
    focus: Tuple[str, ...],
    flow: str,
    output: str,
    model: str,
    resume: bool
):
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
    """
    try:
        validate_claude_cli()
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)

    # Show what we're doing
    console.print(f"[blue]Starting {flow} workflow[/blue]")
    if scope:
        console.print(f"[blue]Scope:[/blue] {', '.join(scope)}")
    else:
        console.print("[blue]Scope:[/blue] Entire codebase")

    if context:
        console.print(f"[blue]Context files:[/blue] {', '.join(context)}")

    if focus:
        console.print(f"[blue]Focus areas:[/blue] {', '.join(focus)}")

    # Create output directory
    output_path = Path(output)
    output_path.mkdir(exist_ok=True)

    # Get workflow class
    workflow_class = AVAILABLE_WORKFLOWS.get(flow)
    if not workflow_class:
        console.print(f"[red]Unknown workflow:[/red] {flow}")
        ctx.exit(1)

    # Build workflow initialization arguments based on the workflow type
    init_args = {"model": model}

    # Add workflow-specific arguments
    if flow == "audit":
        init_args.update({
            "scope_files": list(scope),
            "context_docs": list(context),
            "focus_areas": list(focus)
        })
    # Future workflows can add their own argument handling here

    workflow = workflow_class(**init_args)

    # Display working directory
    console.print(f"[blue]Working directory:[/blue] {workflow.working_dir}")

    try:
        # Execute workflow
        results = workflow.execute(resume=resume)

        # Display results
        console.print("\n[green]Audit complete![/green]")
        console.print(f"[green]Results saved to:[/green] {output}/")

        if results.get("issues_found", 0) > 0:
            console.print(f"\n[yellow]Found {results['issues_found']} potential issues[/yellow]")
            console.print(f"Review the detailed findings in {output}/issues/")
        else:
            console.print("\n[green]No significant issues found![/green]")

        # Show summary
        console.print("\n[bold]Summary:[/bold]")
        console.print(format_workflow_results(results, "text"))

    except KeyboardInterrupt:
        console.print("\n[yellow]Audit interrupted. Use --resume to continue.[/yellow]")
        ctx.exit(0)
    except Exception as e:
        console.print(f"[red]Audit failed:[/red] {e}")
        if resume:
            console.print("[yellow]Try running without --resume flag[/yellow]")
        ctx.exit(1)