"""Modular result system for AI workflows."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING, Type, List, Tuple
import json

if TYPE_CHECKING:
    from rich.console import Console
    from .detections import AIDetection


class AIResult(ABC):
    """Base class for AI workflow results.

    Any result type that implements these methods can be used by the AI CLI.
    This allows each workflow to define its own result structure and formatting.
    """

    @classmethod
    @abstractmethod
    def from_working_dir(cls, working_dir: Path, raw_results: Dict[str, Any]) -> "AIResult":
        """Create a result instance by parsing the working directory.
        
        Args:
            working_dir: Path to the workflow's working directory
            raw_results: Raw results dict from workflow execution
            
        Returns:
            An instance of the result class with parsed data
        """
        ...

    @abstractmethod
    def pretty_print(self, console: "Console") -> None:
        """Print the result in a human-readable format to the console."""
        ...

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary for JSON serialization."""
        ...

    def export_json(self, path: Path) -> None:
        """Export the result to a JSON file.

        Default implementation uses to_dict(), but can be overridden
        for custom export formats.
        """
        data = self.to_dict()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))


class SimpleResult(AIResult):
    """Simple key-value result implementation."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @classmethod
    def from_working_dir(cls, working_dir: Path, raw_results: Dict[str, Any]) -> "SimpleResult":
        """Create a SimpleResult from raw results.
        
        This implementation just packages the raw results with some metadata.
        """
        return cls({
            "status": "completed",
            "working_directory": str(working_dir),
            "total_cost": raw_results.get("total_cost", 0),
            **raw_results
        })

    def pretty_print(self, console: "Console") -> None:
        """Print as a formatted table."""
        from rich.table import Table

        table = Table(title="Result", show_header=True)
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        for key, value in self.data.items():
            table.add_row(key, str(value))

        console.print(table)

    def to_dict(self) -> Dict[str, Any]:
        """Return the data as-is."""
        return self.data


class MessageResult(AIResult):
    """Simple message result for workflows that just print status."""
    
    def __init__(self, message: str, working_dir: Path):
        self.message = message
        self.working_dir = working_dir
    
    @classmethod
    def from_working_dir(cls, working_dir: Path, raw_results: Dict[str, Any]) -> "MessageResult":
        """Create a MessageResult with a standard completion message."""
        return cls(
            f"Workflow completed successfully. Results saved to: {working_dir}",
            working_dir
        )
    
    def pretty_print(self, console: "Console") -> None:
        """Print the message."""
        console.print(f"\n[green]{self.message}[/green]")
    
    def to_dict(self) -> Dict[str, Any]:
        """Return message and working directory."""
        return {
            "message": self.message,
            "working_directory": str(self.working_dir)
        }


class DetectionResult(AIResult):
    """Base class for AI results that produce detection-style output.

    This is a specialized AIResult for security audits, bug detection,
    and similar tasks that produce a list of findings/detections.
    """

    def __init__(self, detections: List[Tuple[str, 'AIDetection']], working_dir: Path):
        self.detections = detections
        self.working_dir = working_dir

    @classmethod
    @abstractmethod
    def from_working_dir(cls, working_dir: Path, raw_results: Dict[str, Any]) -> "DetectionResult":
        """Parse detection results from the working directory.
        
        Subclasses must implement this to parse their specific output format.
        """
        ...

    def pretty_print(self, console: "Console") -> None:
        """Print detections using the detection printer."""
        from .detections import print_ai_detection

        if self.detections:
            console.print(f"\n[bold]Found {len(self.detections)} detection(s):[/bold]")
            for detector_name, detection in self.detections:
                print_ai_detection(detector_name, detection, console)
        else:
            console.print(f"\n[yellow]No detections found[/yellow]")

        # Always show where full results are
        console.print(f"\n[dim]Full results available in:[/dim] {self.working_dir}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert all detections to dictionary format."""
        return {
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


class AuditDetectionResult(DetectionResult):
    """Detection result specifically for security audit workflows."""
    
    @classmethod
    def from_working_dir(cls, working_dir: Path, raw_results: Dict[str, Any]) -> "AuditDetectionResult":
        """Parse audit workflow results from the working directory.
        
        Looks for the standard audit output structure and parses YAML/AsciiDoc files.
        """
        from .detections import AuditResultParser
        
        # Use the existing parser to get detections
        detections = AuditResultParser.parse_audit_results(working_dir)
        
        # Create instance with parsed detections
        return cls(detections, working_dir)
