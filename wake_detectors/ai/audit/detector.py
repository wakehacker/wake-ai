"""AI-powered security audit detector using Claude."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

import rich_click as click
from rich.console import Console

from wake.ai.utils import format_workflow_results
from wake.detectors import (
    Detector,
    DetectorResult,
    detector,
)

logger = logging.getLogger(__name__)
console = Console()


def workflow_options_decorator(workflow_class):
    """Decorator to add workflow-specific options to a detector command."""
    def decorator(f):
        # Get workflow options and add them in reverse order
        options = workflow_class.get_cli_options()
        for opt_name, opt_config in reversed(list(options.items())):
            # Extract param_decls and create option
            param_decls = opt_config.pop("param_decls", [f"--{opt_name}"])
            click.option(*param_decls, **opt_config)(f)
        return f
    return decorator


class AIAuditDetector(Detector):
    """AI-powered security audit detector using Claude Code."""

    def __init__(self):
        self.scope_files: List[str] = []
        self.context_docs: List[str] = []
        self.focus_areas: List[str] = []
        self.model: str = "opus"
        self.output_dir: Path = Path(".audit")
        self.resume: bool = False

    def detect(self) -> List[DetectorResult]:
        """Run the AI audit workflow and convert results to DetectorResults."""
        try:
            # Import here to avoid circular imports
            from wake.ai import ClaudeNotAvailableError

            from .workflow import DetectorAuditWorkflow

            console.print("[blue]Starting AI security audit...[/blue]")

            # Initialize workflow with model - let it handle session creation
            workflow = DetectorAuditWorkflow(
                scope_files=self.scope_files,
                context_docs=self.context_docs,
                focus_areas=self.focus_areas,
                model=self.model  # Pass model instead of session
            )

            # Display working directory
            console.print(f"[blue]Working directory:[/blue] {workflow.working_dir}")

            # Display configuration
            if self.scope_files:
                console.print(f"[blue]Scope:[/blue] {', '.join(self.scope_files)}")
            else:
                console.print("[blue]Scope:[/blue] Entire codebase")

            if self.context_docs:
                console.print(f"[blue]Context docs:[/blue] {', '.join(self.context_docs)}")

            if self.focus_areas:
                console.print(f"[blue]Focus areas:[/blue] {', '.join(self.focus_areas)}")

            console.print(f"[blue]Model:[/blue] {self.model}")

            # Execute workflow
            results = workflow.execute(resume=self.resume)

            console.print(format_workflow_results(results, "text"))

            console.print(f"\n[green]Audit complete! Review results in:[/green] {workflow.working_dir}/")

        except ClaudeNotAvailableError as e:
            console.print(f"[red]Error:[/red] {e}")
            return []
        except Exception as e:
            logger.error(f"AI audit failed: {e}")
            console.print(f"[red]AI audit failed:[/red] {e}")
            if self.resume:
                console.print("[yellow]Try running without --resume flag[/yellow]")

        return []

    @detector.command(name="ai-audit")
    @click.option(
        "--model",
        "-m",
        default="sonnet",
        help="Claude model to use (sonnet, opus)"
    )
    @click.option(
        "--output",
        "-o",
        type=click.Path(),
        default=".audit",
        help="Output directory for results"
    )
    @click.option(
        "--resume",
        is_flag=True,
        help="Resume from previous session"
    )
    @workflow_options_decorator(None)  # Will be fixed below
    def cli(self, **kwargs) -> None:
        """
        AI-powered security audit using Claude.

        This detector runs a comprehensive security audit on your smart contracts
        using Claude to identify potential vulnerabilities. It follows industry
        best practices with multiple analysis steps.

        Examples:
            # Audit entire codebase
            wake detect ai-audit

            # Audit specific files
            wake detect ai-audit -s contracts/Token.sol -s contracts/Vault.sol

            # Add context and focus areas
            wake detect ai-audit -c docs/spec.md -f reentrancy -f "access control"

            # Use a more powerful model
            wake detect ai-audit --model opus

            # Resume a previous audit
            wake detect ai-audit --resume
        """
        # Import workflow class
        from .workflow import DetectorAuditWorkflow

        # Process workflow arguments
        workflow_args = DetectorAuditWorkflow.process_cli_args(**kwargs)

        # Store configuration
        self.scope_files = workflow_args.get("scope_files", [])
        self.context_docs = workflow_args.get("context_docs", [])
        self.focus_areas = workflow_args.get("focus_areas", [])
        self.model = kwargs.get("model", "sonnet")
        self.output_dir = Path(kwargs.get("output", ".audit"))
        self.resume = kwargs.get("resume", False)