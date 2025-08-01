"""CLI interface for Wake AI."""

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
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = get_logger(__name__)


class WorkflowGroup(click.Group):
    _current_plugin: str | None = None
    _loading_from_plugins: bool = False
    _plugins_loaded: bool = False
    _failed_plugin_entry_points: set[tuple[str, Exception]] = set()
    _workflow_collisions: set[tuple[str, str, str]] = set()
    _completion_mode: bool  # if set, don't log errors

    loaded_from_plugins: dict[str, str] = {}
    workflow_sources: dict[str, set[str | None]] = {}

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

        workflow_entry_points = entry_points().select(group="wake-ai.plugins.workflows")
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

    def invoke(self, ctx: click.Context):
        ctx.ensure_object(dict)
        ctx.obj["subcommand_args"] = ctx.args
        ctx.obj["subcommand_protected_args"] = ctx.protected_args
        super().invoke(ctx)


# credits: https://stackoverflow.com/questions/3589311/get-defining-class-of-unbound-method-object-in-python-3/25959545#25959545
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


@click.group(cls=WorkflowGroup)
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
@click.pass_context
def main(ctx: click.Context, model: str, **kwargs):
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
    rich.traceback.install(console=console)

    # Set logging level based on verbose flag
    if kwargs.get("verbose"):
        set_debug(True)
        console.print("[dim]Debug logging enabled[/dim]")

    if "--help" in ctx.obj["subcommand_args"]:
        return

    if ctx.invoked_subcommand is not None:
        try:
            workflow_name = ctx.invoked_subcommand
            console.print(f"[blue]Starting {workflow_name} workflow[/blue]")

            command: Optional[click.Command] = main.get_command(ctx, workflow_name)
            if command is None:
                console.print(f"[red]Unknown workflow:[/red] {workflow_name}")
                ctx.exit(1)

            args = [*ctx.obj["subcommand_protected_args"][1:], *ctx.obj["subcommand_args"]]

            cls: Type[AIWorkflow] = get_class_that_defined_method(command.callback)
            workflow = object.__new__(cls)
            workflow._pre_init(
                name=workflow_name,
                model=model,
                working_dir=kwargs.get("working_dir"),
                execution_dir=kwargs.get("execution_dir"),
                cleanup_working_dir=not kwargs.get("no_cleanup"),
            )
            workflow.__init__()

            original_callback = command.callback
            command.callback = lambda *args, **kwargs: original_callback(workflow, *args, **kwargs)

            sub_ctx = command.make_context(
                command.name,
                list(args),
                parent=ctx,
            )
            with sub_ctx:
                sub_ctx.command.invoke(sub_ctx)

            command.callback = original_callback

            # Display working directory and cleanup info
            console.print(f"[blue]Working directory:[/blue] {workflow.working_dir}")
            if workflow.cleanup_working_dir:
                console.print(f"[dim]Working directory will be cleaned up after completion. Use --no-cleanup to preserve it.[/dim]")
            else:
                console.print(f"[dim]Working directory will be preserved after completion.[/dim]")

            # Execute workflow
            results, formatted_results = workflow.execute(resume=kwargs["resume"])

            # Display results
            console.print("\n[green]Workflow complete![/green]")

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
            console.print_exception()
            if kwargs["resume"]:
                console.print("[yellow]Try running without --resume flag[/yellow]")
            ctx.exit(1)

    # prevent execution of subcommands
    ctx.exit(0)


if __name__ == "__main__":
    main()
