"""Modular result system for AI workflows."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from rich.console import Console


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

        This implementation packages the raw results into a simple format.
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

