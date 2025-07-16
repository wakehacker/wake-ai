"""Test detector that skips AI and reads findings from a predefined directory."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, TYPE_CHECKING

import rich_click as click
from rich.console import Console

from wake.detectors import (
    Detector,
    DetectorResult,
    detector,
)

# Import validator from simple_detections
from ..simple_detections.validator import validate_all_findings

if TYPE_CHECKING:
    from wake.compiler.build_data_model import ProjectBuild

logger = logging.getLogger(__name__)
console = Console()


class TestDetector(Detector):
    """Test detector that reads findings from a predefined directory without AI."""

    if TYPE_CHECKING:
        build: ProjectBuild

    def __init__(self):
        self.test_folder: str = "/Users/lukasrajnoha/Data/Work/ABCH/test/test-wake-ai/.wake/ai/20250716_001432_rke1g8"

    def detect(self) -> List[DetectorResult]:
        """Read findings from the test folder and convert to DetectorResults."""
        detector_results = []
        
        try:
            # Import here to avoid circular imports and import errors
            try:
                from wake.ai.detector_result_mock import DetectorResultFactory
            except ImportError as e:
                logger.error(f"Failed to import wake.ai modules: {e}")
                console.print(f"[red]Error:[/red] AI modules not available. Ensure wake[ai] is installed.")
                return []

            console.print("[blue]Starting test detection (reading from predefined folder)...[/blue]")
            console.print(f"[blue]Test folder:[/blue] {self.test_folder}")

            # Parse findings and convert to DetectorResults
            findings_dir = Path(self.test_folder) / "findings"
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
                console.print(f"[red]No findings directory found at {findings_dir}[/red]")

            console.print(f"\n[green]Detection complete! Read results from:[/green] {self.test_folder}/")

        except Exception as e:
            logger.error(f"Test detection failed: {e}")
            console.print(f"[red]Test detection failed:[/red] {e}")

        return detector_results


@detector.command(name="test-ai")
@click.option(
    "--folder",
    "-f",
    help="Override test folder path"
)
def cli(**kwargs) -> None:
    """
    Test detector that reads findings from a predefined directory.

    This detector skips the AI part and directly reads findings from:
    /Users/lukasrajnoha/Data/Work/ABCH/test/test-wake-ai/.wake/ai/20250716_001432_rke1g8

    Examples:
        # Use default test folder
        wake detect test-ai

        # Override test folder
        wake detect test-ai --folder /path/to/test/folder
    """
    detector = TestDetector()
    # Override test folder if provided
    if kwargs.get("folder"):
        detector.test_folder = kwargs["folder"]