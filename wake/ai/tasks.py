"""Base AITask class for all AI-powered tasks."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from rich.console import Console
    from .detections import AIDetection

class AITask(ABC):
    """Base class for AI tasks that run autonomously and return results.

    This class provides the foundation for various AI-powered tasks like:
    - Security audits
    - Code quality analysis
    - Gas optimization
    - Documentation generation
    - Any custom analysis
    """

    @abstractmethod
    def get_task_type(self) -> str:
        """Return the task type identifier (e.g., 'security-audit', 'code-quality')."""
        ...

    @abstractmethod
    def pretty_print(self, console: "Console") -> None:
        """Print results in a human-readable format to the console."""
        ...

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary format for serialization."""
        ...

    def export_json(self, path: Path) -> None:
        """Export results to JSON file.

        Default implementation uses to_dict(), but can be overridden.
        """
        import json

        data = self.to_dict()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))




class DetectionTask(AITask):
    """Base class for AI tasks that produce detection-style results.

    This is a specialized AITask for security audits, bug detection,
    and similar tasks that produce a list of findings/detections.
    """

    def __init__(self, detections: List[Tuple[str, 'AIDetection']], working_dir: Path):
        self.detections = detections
        self.working_dir = working_dir

    def pretty_print(self, console: "Console") -> None:
        """Print detections using the detection printer."""
        from .detections import print_ai_detection

        if self.detections:
            console.print(f"\n[bold]Found {len(self.detections)} detection(s):[/bold]")
            for detector_name, detection in self.detections:
                print_ai_detection(detector_name, detection, console)
        else:
            console.print(f"\n[yellow]{self.get_no_detections_message()}[/yellow]")

        # Always show where full results are
        console.print(f"\n[dim]Full results available in:[/dim] {self.working_dir}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert all detections to dictionary format."""
        return {
            "task_type": self.get_task_type(),
            "detections": [
                {
                    "detector": detector_name,
                    **detection.to_dict()
                }
                for detector_name, detection in self.detections
            ],
            "working_directory": str(self.working_dir),
            "total_detections": len(self.detections)
        }

    def export_json(self, path: Path) -> None:
        """Use the existing export function for detection consistency."""
        from .detections import export_ai_detections_json
        export_ai_detections_json(self.detections, path)

    @abstractmethod
    def get_no_detections_message(self) -> str:
        """Return the message to display when no detections are found."""
        return "No detections found"

    @classmethod
    @abstractmethod
    def parse_results(cls, working_dir: Path) -> List[Tuple[str, 'AIDetection']]:
        """Parse task results from the working directory.

        Args:
            working_dir: Path to the task's working directory

        Returns:
            List of (detector_name, AIDetection) tuples
        """
        ...

    @classmethod
    def from_workflow_results(cls, workflow_results: Dict[str, Any], working_dir: Path):
        """Create instance from workflow execution results.

        Args:
            workflow_results: Raw results from workflow.execute() (for future use)
            working_dir: Path to the workflow's working directory

        Returns:
            Instance of the detection task result
        """
        detections = cls.parse_results(working_dir)
        return cls(detections, working_dir)