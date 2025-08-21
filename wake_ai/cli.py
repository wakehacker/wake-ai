"""CLI interface for Wake AI."""

from __future__ import annotations

import rich_click as click
import logging
from pathlib import Path
from typing import Optional, Union, Dict, Any, Sequence, List, Type, TYPE_CHECKING

import rich.traceback
from rich.console import Console
from rich.logging import RichHandler
from wake_ai.utils.logging import get_logger, set_debug

if TYPE_CHECKING:
    from wake_ai import AIWorkflow


console = Console()

# Configure logging to use rich handler for pretty console output
# Only configure if not already configured to avoid duplicate handlers
root_logger = logging.getLogger()
if not root_logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)]
    )
logger = get_logger(__name__)


class WorkflowGroup(click.RichGroup):
    _current_plugin: Optional[str] = None
    _loading_from_plugins: bool = False
    _plugins_loaded: bool = False
    _failed_plugin_entry_points: set[tuple[str, Exception]] = set()
    _workflow_collisions: set[tuple[str, str, str]] = set()
    _completion_mode: bool  # if set, don't log errors

    loaded_from_plugins: dict[str, str] = {}
    workflow_sources: dict[str, set[Optional[str]]] = {}

    def __init__(
        self,
        name: Optional[str] = None,
        commands: Optional[
            Union[Dict[str, click.Command], Sequence[click.Command]]
        ] = None,
        **attrs: Any,
    ):
        super().__init__(name=name, commands=commands, **attrs)

        import os

        self._completion_mode = "_WAKE_AI_COMPLETE" in os.environ

    def _load_plugins(self) -> None:
        import sys

        if sys.version_info < (3, 10):
            from importlib_metadata import entry_points
        else:
            from importlib.metadata import entry_points

        self._loading_from_plugins = True
        for cmd in self.loaded_from_plugins.keys():
            self.commands.pop(cmd, None)
        self.loaded_from_plugins.clear()
        self.workflow_sources.clear()
        self._failed_plugin_entry_points.clear()
        self._workflow_collisions.clear()

        workflow_entry_points = entry_points().select(group="wake_ai.plugins.workflows")
        for entry_point in sorted(workflow_entry_points, key=lambda e: e.module):
            self._current_plugin = entry_point.module

            # unload target module and all its children
            for m in [
                k
                for k in sys.modules.keys()
                if k == entry_point.module or k.startswith(entry_point.module + ".")
            ]:
                sys.modules.pop(m)

            try:
                entry_point.load()
            except Exception as e:
                self._failed_plugin_entry_points.add((entry_point.module, e))
                if not self._completion_mode:
                    logger.error(
                        f"Failed to load detectors from plugin module '{entry_point.module}': {e}"
                    )

        self._loading_from_plugins = False

    def add_command(self, cmd: click.Command, name: Optional[str] = None) -> None:
        name = name or cmd.name
        assert name is not None
        if name in set():  # whitelisted commands that are not workflows
            super().add_command(cmd, name)
            return

        if name not in self.workflow_sources:
            self.workflow_sources[name] = {self._current_plugin}
        else:
            self.workflow_sources[name].add(self._current_plugin)

        if name in self.loaded_from_plugins:
            prev = f"plugin module '{self.loaded_from_plugins[name]}'"
            current = f"plugin module '{self._current_plugin}'"
            self._workflow_collisions.add((name, prev, current))

            if not self._completion_mode:
                logger.warning(f"Workflow '{name}' already loaded from plugin '{self.loaded_from_plugins[name]}'. Second load from '{self._current_plugin}' will be ignored.")
            return

        super().add_command(cmd, name)
        if self._loading_from_plugins:
            self.loaded_from_plugins[
                name
            ] = self._current_plugin  # pyright: ignore reportGeneralTypeIssues

    def get_command(
        self,
        ctx: click.Context,
        cmd_name: str,
        force_load_plugins: bool = False,
    ) -> Optional[click.Command]:
        if not self._plugins_loaded or force_load_plugins:
            self._load_plugins()
            self._plugins_loaded = True
        return self.commands.get(cmd_name)

    def list_commands(
        self,
        ctx: click.Context,
        force_load_plugins: bool = False,
    ) -> List[str]:
        if not self._plugins_loaded or force_load_plugins:
            self._load_plugins()
            self._plugins_loaded = True
        return sorted(self.commands)


# credits: https://stackoverflow.com/questions/3589311/get-defining-class-of-unbound-method-object-in-python-3/25959545#25959545
def list_workflows(ctx: click.Context, group: WorkflowGroup) -> None:
    """Display all available workflows in a formatted table."""
    from rich.table import Table

    # Get all workflow names using the existing method
    workflow_names = group.list_commands(ctx, force_load_plugins=True)

    # Create a table for display
    table = Table(title="Available Workflows", show_header=True, header_style="bold magenta")
    table.add_column("Workflow", style="cyan", no_wrap=True)
    table.add_column("Source", style="dim")
    table.add_column("Description", style="white")

    # Iterate through all workflows
    for name in workflow_names:
        cmd = group.commands[name]

        # Get source information
        source = "built-in"
        if name in group.loaded_from_plugins:
            source = f"plugin: {group.loaded_from_plugins[name]}"

        # Get description from docstring
        description = cmd.help or cmd.get_short_help_str() if hasattr(cmd, 'get_short_help_str') else "No description available"
        # Clean up description - take first line only
        if description:
            description = description.split('\n')[0].strip()

        # Check for collisions
        if name in group.workflow_sources and len(group.workflow_sources[name]) > 1:
            sources_list = [s if s else "built-in" for s in group.workflow_sources[name]]
            description += f" [yellow](⚠ Multiple sources: {', '.join(sources_list)})[/yellow]"

        table.add_row(name, source, description)

    # Show any failed plugin loads
    if group._failed_plugin_entry_points:
        console.print("\n[yellow]Warning: Some plugins failed to load:[/yellow]")
        for module, error in group._failed_plugin_entry_points:
            console.print(f"  • {module}: {error}")

    # Display the table
    console.print(table)

    # Show count
    console.print(f"\n[dim]Total workflows available: {len(workflow_names)}[/dim]")

    # Hint about running workflows
    console.print("\n[dim]Run a workflow with: wake-ai <workflow-name> [options][/dim]")
    console.print("[dim]Get help for a workflow: wake-ai <workflow-name> --help[/dim]")


def get_class_that_defined_method(meth):
    import functools
    import inspect

    if isinstance(meth, functools.partial):
        return get_class_that_defined_method(meth.func)
    if inspect.ismethod(meth):
        for c in inspect.getmro(meth.__self__.__class__):
            if meth.__name__ in c.__dict__:
                return c
        meth = getattr(meth, "__func__", meth)  # fallback to __qualname__ parsing
    if inspect.isfunction(meth):
        c = getattr(
            inspect.getmodule(meth),
            meth.__qualname__.split(".<locals>", 1)[0].rsplit(".", 1)[0],
            None,
        )
        if isinstance(c, type):
            return c
    return getattr(meth, "__objclass__", None)  # handle special descriptor objects


@click.group(cls=WorkflowGroup, invoke_without_command=True)
@click.option(
    "--working-dir",
    "-w",
    type=click.Path(),
    help="Working directory for AI workflow (defaults to .wake/ai/<session-id>)"
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
@click.option(
    "--no-progress",
    is_flag=True,
    help="Disable progress bar during workflow execution"
)
@click.option(
    "--list",
    "-l",
    is_flag=True,
    help="List all available workflows"
)
@click.pass_context
def main(ctx: click.Context, working_dir: str | None, model: str, resume: bool, execution_dir: str | None, export: str | None, no_cleanup: bool, verbose: bool, no_progress: bool, list: bool):
    """AI-powered smart contract security analysis.

    This command runs various AI workflows for smart contract analysis
    using Claude to identify potential vulnerabilities and issues.
    """
    rich.traceback.install(console=console)

    # Set logging level based on verbose flag
    if verbose:
        set_debug(True)
        console.print("[dim]Debug logging enabled[/dim]")

    # Handle list flag
    if list:
        # Get the command group
        group = ctx.command
        if not isinstance(group, WorkflowGroup):
            console.print("[red]Error: Cannot access workflow group[/red]")
            ctx.exit(1)

        list_workflows(ctx, group)
        ctx.exit(0)

    if ctx.invoked_subcommand is not None:
        ctx.ensure_object(dict)
        ctx.obj["name"] = ctx.invoked_subcommand
        ctx.obj["model"] = model
        ctx.obj["working_dir"] = working_dir
        ctx.obj["execution_dir"] = execution_dir
        ctx.obj["cleanup_working_dir"] = not no_cleanup
        ctx.obj["show_progress"] = not no_progress
        ctx.obj["console"] = console  # Pass console for coordinated output


if __name__ == "__main__":
    main()

@main.result_callback()
def factory_callback(workflow: Optional[AIWorkflow], model: str, resume: bool, working_dir: str | None, execution_dir: str | None, no_cleanup: bool, export: str | None, no_progress: bool, **kwargs):
    ctx = click.get_current_context()
    workflow_name = ctx.invoked_subcommand

    # Skip if no workflow was invoked
    if workflow is None:
        click.echo(ctx.get_help())
        return

    try:
        console.print(f"[blue]Starting {workflow_name} workflow[/blue]")

        # Display working directory and cleanup info
        console.print(f"[blue]Working directory:[/blue] {workflow.working_dir}")
        if workflow.cleanup_working_dir:
            console.print(f"[dim]Working directory will be cleaned up after completion. Use --no-cleanup to preserve it.[/dim]")
        else:
            console.print(f"[dim]Working directory will be preserved after completion.[/dim]")

        # Execute workflow
        results, formatted_results = workflow.execute(resume=resume)

        # Display results
        console.print("\n[green]Workflow complete![/green]")


        if export:
            # Export to JSON
            if hasattr(formatted_results, 'export_json'):
                import json
                results = {
                    "results": formatted_results.to_dict(),
                    "metadata": results["metadata"],
                }
                Path(export).parent.mkdir(parents=True, exist_ok=True)
                Path(export).write_text(json.dumps(results, indent=2))
                console.print(f"[green]Results exported to:[/green] {export}")
        else:
            # Pretty print to console
            # results["metadata"] content is already shown as table in the command output.
            if hasattr(formatted_results, 'pretty_print'):
                formatted_results.pretty_print(console)
            else:
                console.print(formatted_results)

    except KeyboardInterrupt:
        console.print("\n[yellow]Workflow interrupted. Use --resume to continue.[/yellow]")
        ctx.exit(0)
    except Exception as e:
        console.print_exception()
        if resume:
            console.print("[yellow]Try running without --resume flag[/yellow]")
        ctx.exit(1)
