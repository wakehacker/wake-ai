"""AI-assisted development commands for Wake."""

import click
from pathlib import Path
from typing import Optional

from wake.cli.console import console
from wake.ai import ClaudeCodeSession
from wake.ai.flow import CodeAnalysisWorkflow, RefactoringWorkflow
from wake.ai.utils import (
    load_workflow_from_file,
    create_workflow_template,
    format_workflow_results,
    validate_claude_cli,
    parse_tool_list
)


class NewCommandAlias(click.Group):
    """Command group that handles aliases."""
    
    def get_command(self, ctx, cmd_name):
        return super().get_command(ctx, cmd_name)


@click.group(name="ai", cls=NewCommandAlias)
@click.pass_context
def run_ai(ctx: click.Context):
    """AI-assisted development workflows powered by Claude Code.
    
    This command provides various AI-powered tools to help with
    code analysis, refactoring, test generation, and more.
    """
    try:
        validate_claude_cli()
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


@run_ai.command(name="analyze")
@click.option(
    "--focus",
    "-f",
    help="Specific areas to focus on (e.g., 'security,performance')",
    default=""
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Save analysis results to file"
)
@click.option(
    "--format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Output format"
)
@click.argument("directory", type=click.Path(exists=True), default=".")
@click.pass_context
def ai_analyze(
    ctx: click.Context,
    directory: str,
    focus: str,
    output: Optional[str],
    format: str
):
    """Analyze codebase structure and patterns.
    
    This command uses AI to understand your codebase structure,
    identify patterns, and provide recommendations.
    """
    console.print(f"[blue]Analyzing codebase in:[/blue] {directory}")
    
    # Create workflow
    workflow = CodeAnalysisWorkflow()
    
    # Prepare context
    context = {
        "directory": directory,
        "focus_areas": focus if focus else "general analysis"
    }
    
    try:
        # Execute workflow
        results = workflow.execute(context=context)
        
        # Format results
        formatted = format_workflow_results(results, format)
        
        # Output results
        if output:
            Path(output).write_text(formatted)
            console.print(f"[green]Analysis saved to:[/green] {output}")
        else:
            console.print(formatted)
            
    except Exception as e:
        console.print(f"[red]Analysis failed:[/red] {e}")
        ctx.exit(1)


@run_ai.command(name="refactor")
@click.option(
    "--target",
    "-t",
    required=True,
    type=click.Path(exists=True),
    help="Target file or directory to refactor"
)
@click.option(
    "--goal",
    "-g",
    required=True,
    help="Refactoring goal (e.g., 'improve readability', 'optimize performance')"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show refactoring plan without making changes"
)
@click.pass_context
def ai_refactor(
    ctx: click.Context,
    target: str,
    goal: str,
    dry_run: bool
):
    """AI-guided code refactoring.
    
    This command helps refactor code based on specified goals,
    providing step-by-step guidance and automated changes.
    """
    console.print(f"[blue]Refactoring target:[/blue] {target}")
    console.print(f"[blue]Goal:[/blue] {goal}")
    
    # Create workflow
    workflow = RefactoringWorkflow()
    
    # Prepare context
    context = {
        "target": target,
        "goal": goal
    }
    
    # If dry-run, limit tools
    if dry_run:
        # Override the workflow to not make actual changes
        for step in workflow.steps:
            if step.name == "implement_changes":
                step.tools = ["read"]  # Read-only for dry run
    
    try:
        # Execute workflow
        results = workflow.execute(context=context)
        
        # Display results
        if dry_run:
            console.print("\n[yellow]Dry run complete. No changes made.[/yellow]")
            console.print("\n[bold]Refactoring Plan:[/bold]")
            plan = results.get("context", {}).get("plan_refactoring_output", "")
            console.print(plan)
        else:
            console.print("\n[green]Refactoring complete![/green]")
            console.print(format_workflow_results(results, "text"))
            
    except Exception as e:
        console.print(f"[red]Refactoring failed:[/red] {e}")
        ctx.exit(1)


@run_ai.command(name="custom")
@click.option(
    "--workflow",
    "-w",
    type=click.Path(exists=True),
    required=True,
    help="Path to custom workflow file (YAML or JSON)"
)
@click.option(
    "--context",
    "-c",
    multiple=True,
    help="Context values as key=value pairs"
)
@click.option(
    "--resume",
    is_flag=True,
    help="Resume from saved state"
)
@click.pass_context
def ai_custom(
    ctx: click.Context,
    workflow: str,
    context: tuple,
    resume: bool
):
    """Run a custom AI workflow.
    
    This allows you to define and run custom multi-step AI workflows
    using YAML or JSON configuration files.
    """
    console.print(f"[blue]Loading workflow:[/blue] {workflow}")
    
    try:
        # Load workflow
        ai_workflow = load_workflow_from_file(workflow)
        
        # Parse context
        workflow_context = {}
        for item in context:
            if "=" in item:
                key, value = item.split("=", 1)
                workflow_context[key] = value
        
        # Execute workflow
        results = ai_workflow.execute(
            context=workflow_context,
            resume=resume
        )
        
        # Display results
        console.print("\n[green]Workflow complete![/green]")
        console.print(format_workflow_results(results, "text"))
        
    except Exception as e:
        console.print(f"[red]Workflow failed:[/red] {e}")
        ctx.exit(1)


@run_ai.command(name="interactive")
@click.option(
    "--model",
    "-m",
    default="sonnet",
    help="Model to use (sonnet, opus, etc.)"
)
@click.option(
    "--tools",
    "-t",
    help="Comma-separated list of allowed tools"
)
@click.option(
    "--prompt",
    "-p",
    help="Initial prompt"
)
@click.pass_context
def ai_interactive(
    ctx: click.Context,
    model: str,
    tools: Optional[str],
    prompt: Optional[str]
):
    """Start an interactive AI session.
    
    This launches Claude Code in interactive mode for the current directory,
    allowing you to have a conversation about your codebase.
    """
    console.print(f"[blue]Starting interactive AI session with model:[/blue] {model}")
    
    # Parse tools
    allowed_tools = parse_tool_list(tools) if tools else None
    
    # Create session
    session = ClaudeCodeSession(
        model=model,
        allowed_tools=allowed_tools
    )
    
    try:
        # Start interactive session
        process = session.start_interactive(initial_prompt=prompt)
        
        # Let the process run interactively
        process.communicate()
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interactive session ended.[/yellow]")
    except Exception as e:
        console.print(f"[red]Interactive session failed:[/red] {e}")
        ctx.exit(1)


@run_ai.command(name="template")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="workflow_template.yaml",
    help="Output file for the template"
)
def ai_template(output: str):
    """Create a template workflow file.
    
    This generates a template workflow configuration that you can
    customize for your specific needs.
    """
    create_workflow_template(output)
    console.print(f"[green]Template created:[/green] {output}")
    console.print("\nEdit this file to define your custom workflow steps.")


@run_ai.command(name="query")
@click.argument("prompt")
@click.option(
    "--model",
    "-m",
    default="sonnet",
    help="Model to use"
)
@click.option(
    "--tools",
    "-t",
    help="Comma-separated list of allowed tools"
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output raw JSON response"
)
@click.pass_context
def ai_query(
    ctx: click.Context,
    prompt: str,
    model: str,
    tools: Optional[str],
    output_json: bool
):
    """Run a single AI query.
    
    This executes a one-off query without a full workflow,
    useful for quick questions or simple tasks.
    """
    # Parse tools
    allowed_tools = parse_tool_list(tools) if tools else None
    
    # Create session
    session = ClaudeCodeSession(
        model=model,
        allowed_tools=allowed_tools
    )
    
    try:
        # Execute query
        response = session.query(
            prompt,
            output_format="json" if output_json else "text"
        )
        
        if response.success:
            if output_json:
                console.print(response.raw_output)
            else:
                console.print(response.content)
        else:
            console.print(f"[red]Query failed:[/red] {response.error}")
            ctx.exit(1)
            
    except Exception as e:
        console.print(f"[red]Query failed:[/red] {e}")
        ctx.exit(1)