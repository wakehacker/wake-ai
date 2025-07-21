"""Modular result system for AI workflows."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from rich.console import Console


class AIResult(ABC):
    """Protocol for AI workflow results.

    Any result type that implements these methods can be used by the AI CLI.
    This allows each workflow to define its own result structure and formatting.
    """

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
