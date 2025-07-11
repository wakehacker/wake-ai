"""AI-powered security audit detector using Claude."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

import rich_click as click
from rich.console import Console

from wake.detectors import (
    Detection,
    Detector,
    DetectorConfidence,
    DetectorImpact,
    DetectorResult,
    detector,
)

logger = logging.getLogger(__name__)
console = Console()


class AIAuditDetector(Detector):
    """AI-powered security audit detector using Claude Code."""
    
    def __init__(self):
        self.detections = []
        self.scope_files: List[str] = []
        self.context_docs: List[str] = []
        self.focus_areas: List[str] = []
        self.model: str = "sonnet"
        self.output_dir: Path = Path(".audit")
        self.resume: bool = False

    def detect(self) -> List[DetectorResult]:
        """Run the AI audit workflow and convert results to DetectorResults."""
        try:
            # Import here to avoid circular imports
            from wake.ai import ClaudeNotAvailableError
            from .workflow import DetectorAuditWorkflow
            
            console.print("[blue]Starting AI security audit...[/blue]")
            
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
            
            # Initialize workflow with model - let it handle session creation
            workflow = DetectorAuditWorkflow(
                scope_files=self.scope_files,
                context_docs=self.context_docs,
                focus_areas=self.focus_areas,
                model=self.model  # Pass model instead of session
            )
            
            # Override state directory
            workflow.state_dir = self.output_dir
            workflow.state_dir.mkdir(parents=True, exist_ok=True)
            
            # Execute workflow
            results = workflow.execute(resume=self.resume)
            
            # Convert workflow results to detector results
            issues_found = results.get("issues_found", 0)
            
            if issues_found > 0:
                console.print(f"\n[yellow]Found {issues_found} potential issues[/yellow]")
                console.print(f"Review the detailed findings in {self.output_dir}/")
                
                # Create a summary detection
                self.detections.append(
                    DetectorResult(
                        detection=Detection(
                            detector_name="ai-audit",
                            impact=DetectorImpact.HIGH,
                            confidence=DetectorConfidence.HIGH,
                            description=f"AI audit found {issues_found} potential security issues",
                            source_units=[]  # AI audit covers multiple files
                        ),
                        uri=f"file://{self.output_dir.absolute()}"
                    )
                )
            else:
                console.print("\n[green]No significant issues found![/green]")
            
            console.print(f"\n[green]Audit complete! Results saved to:[/green] {self.output_dir}/")
            
            # Show completed steps
            if "completed_steps" in results:
                console.print("\n[bold]Completed workflow steps:[/bold]")
                for step in results["completed_steps"]:
                    console.print(f"  ✓ {step}")
            
        except ClaudeNotAvailableError as e:
            console.print(f"[red]Error:[/red] {e}")
            return []
        except Exception as e:
            logger.error(f"AI audit failed: {e}")
            console.print(f"[red]AI audit failed:[/red] {e}")
            if self.resume:
                console.print("[yellow]Try running without --resume flag[/yellow]")
        
        return self.detections

    @detector.command(name="ai-audit")
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
    def cli(
        self,
        scope: Tuple[str, ...],
        context: Tuple[str, ...],
        focus: Tuple[str, ...],
        model: str,
        output: str,
        resume: bool
    ) -> None:
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
        # Store configuration
        self.scope_files = list(scope)
        self.context_docs = list(context)
        self.focus_areas = list(focus)
        self.model = model
        self.output_dir = Path(output)
        self.resume = resume
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)