"""Simple AI-powered security detector using Claude."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple, TYPE_CHECKING

import rich_click as click
from rich.console import Console

from wake.detectors import (
    Detector,
    DetectorResult,
    detector,
)

from .validator import validate_all_findings

if TYPE_CHECKING:
    from wake.compiler.build_data_model import ProjectBuild

logger = logging.getLogger(__name__)
console = Console()


class SimpleAIDetector(Detector):
    """Simple AI-powered security detector using Claude Code."""

    if TYPE_CHECKING:
        build: ProjectBuild

    def __init__(self):
        self.scope_files: List[str] = []
        self.context_docs: List[str] = []
        self.focus_areas: List[str] = []
        self.model: str = "sonnet"
        self.resume: bool = False

    def detect(self) -> List[DetectorResult]:
        """Run the simple AI detection workflow and convert results to DetectorResults."""
        detector_results = []
        
        try:
            # Import here to avoid circular imports and import errors
            try:
                from wake.ai import ClaudeNotAvailableError
                from wake.ai.detector_result_mock import DetectorResultFactory
                from wake.ai.utils import format_workflow_results
            except ImportError as e:
                logger.error(f"Failed to import wake.ai modules: {e}")
                console.print(f"[red]Error:[/red] AI modules not available. Ensure wake[ai] is installed.")
                return []

            from .workflow import SimpleDetectionsWorkflow

            console.print("[blue]Starting simple AI security detection...[/blue]")

            # Initialize workflow with model - let it handle session creation
            workflow = SimpleDetectionsWorkflow(
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

            # Parse findings and convert to DetectorResults
            findings_dir = Path(workflow.working_dir) / "findings"
            if findings_dir.exists():
                console.print(f"\n[blue]Parsing findings from:[/blue] {findings_dir}")
                
                # Validate and load findings
                valid_findings, errors = validate_all_findings(findings_dir)
                
                if errors:
                    console.print("[yellow]Validation errors:[/yellow]")
                    for error in errors:
                        console.print(f"  - {error}")
                
                if valid_findings:
                    # Create DetectorResultFactory with build
                    factory = DetectorResultFactory(self.build)
                    
                    # Convert findings to DetectorResults
                    try:
                        detector_results = factory.create_detector_results_batch(valid_findings)
                        console.print(f"[green]Successfully parsed {len(detector_results)} findings[/green]")
                    except Exception as e:
                        logger.error(f"Failed to create DetectorResults: {e}")
                        console.print(f"[red]Failed to create DetectorResults:[/red] {e}")
                else:
                    console.print("[yellow]No valid findings found[/yellow]")
            else:
                console.print(f"[yellow]No findings directory found at {findings_dir}[/yellow]")

            console.print(f"\n[green]Detection complete! Review full results in:[/green] {workflow.working_dir}/")

        except ClaudeNotAvailableError as e:
            console.print(f"[red]Error:[/red] {e}")
            return []
        except Exception as e:
            logger.error(f"Simple AI detection failed: {e}")
            console.print(f"[red]Simple AI detection failed:[/red] {e}")
            if self.resume:
                console.print("[yellow]Try running without --resume flag[/yellow]")

        return detector_results

    @detector.command(name="simple-ai")
    @click.option(
        "--model",
        "-m",
        default="sonnet",
        help="Claude model to use (sonnet, opus)"
    )
    @click.option(
        "--resume",
        is_flag=True,
        help="Resume from previous session"
    )
    @click.option(
        "-s", "--scope",
        multiple=True,
        type=click.Path(exists=True),
        help="Files/directories in detection scope (default: entire codebase)"
    )
    @click.option(
        "-c", "--context",
        multiple=True,
        type=click.Path(exists=True),
        help="Additional context files (docs, specs, etc.)"
    )
    @click.option(
        "-f", "--focus",
        multiple=True,
        help="Focus areas (e.g., 'reentrancy', 'ERC20', 'access-control')"
    )
    def cli(self, **kwargs) -> None:
        """
        Simple AI-powered security detection using Claude.

        This detector runs a streamlined security detection on your smart contracts
        using Claude to identify vulnerabilities in a single step.

        Examples:
            # Detect on entire codebase
            wake detect simple-ai

            # Detect on specific files
            wake detect simple-ai -s contracts/Token.sol

            # Add focus areas
            wake detect simple-ai -f reentrancy -f "access control"

            # Use a more powerful model
            wake detect simple-ai --model opus

            # Resume a previous detection
            wake detect simple-ai --resume
        """
        # Import workflow class
        from .workflow import SimpleDetectionsWorkflow

        # Process workflow arguments
        workflow_args = SimpleDetectionsWorkflow.process_cli_args(**kwargs)

        # Store configuration
        self.scope_files = workflow_args.get("scope_files", [])
        self.context_docs = workflow_args.get("context_docs", [])
        self.focus_areas = workflow_args.get("focus_areas", [])
        self.model = kwargs.get("model", "sonnet")
        self.resume = kwargs.get("resume", False)