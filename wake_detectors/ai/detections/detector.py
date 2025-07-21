"""AI-powered security audit detector using Claude."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple, TYPE_CHECKING

import rich_click as click
from rich.console import Console

from wake.ai.detector import AIDetector
from wake.ai.detector_result import AIDetectionResult, AILocation
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


class AITestDetector(AIDetector):
    """AI-powered security audit detector using Claude Code."""

    if TYPE_CHECKING:
        build: ProjectBuild

    def __init__(self):
        self.scope_files: List[str] = []
        self.context_docs: List[str] = []
        self.focus_areas: List[str] = []
        self.model: str = "opus"
        self.output_dir: Path = Path(".audit")
        self.resume: bool = False

    def detect(self) -> List[DetectorResult]:
        """Run the AI audit workflow and convert results to DetectorResults."""
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
                    # Create AIDetector findings
                    for finding in valid_findings:
                        detector_results.append(AIDetectionResult(
                            name=finding["name"],
                            location=AILocation(
                                target=finding["target"],
                            ),
                            detection=finding["description"],
                            recommendation=finding["recommendation"],
                            exploit=finding["exploit"],
                            subdetections=[]
                        ))

                    console.print(f"[green]Successfully parsed {len(detector_results)} findings[/green]")
                else:
                    console.print("[yellow]No valid findings found[/yellow]")
            else:
                console.print(f"[yellow]No findings directory found at {findings_dir}[/yellow]")

            console.print(f"\n[green]Audit complete! Review full results in:[/green] {workflow.working_dir}/")

        except ClaudeNotAvailableError as e:
            console.print(f"[red]Error:[/red] {e}")
            return []
        except Exception as e:
            logger.error(f"AI audit failed: {e}")
            console.print(f"[red]AI audit failed:[/red] {e}")
            if self.resume:
                console.print("[yellow]Try running without --resume flag[/yellow]")

        return detector_results

    @detector.command(name="ai")
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
    @click.option(
        "-s", "--scope",
        multiple=True,
        type=click.Path(exists=True),
        help="Files/directories in audit scope (default: entire codebase)"
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