"""Formatting utilities for AI detections."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Tuple, Union

from ..detections import Detection, Severity

if TYPE_CHECKING:
    from rich.console import Console
    from rich.syntax import SyntaxTheme


def print_detection(
    detector_name: str,
    detection: Detection,
    console: "Console",
    theme: Union[str, "SyntaxTheme"] = "monokai",
    *,
    file_link: bool = True,
) -> None:
    """Print a detection to the console."""
    from rich.panel import Panel
    from rich.syntax import Syntax

    # Build title with severity indicators
    title = ""
    if detection.severity == Severity.INFO:
        title += "[[bold blue]INFO[/bold blue]] "
    elif detection.severity == Severity.WARNING:
        title += "[[bold yellow]WARNING[/bold yellow]] "
    elif detection.severity == Severity.LOW:
        title += "[[bold cyan]LOW[/bold cyan]] "
    elif detection.severity == Severity.MEDIUM:
        title += "[[bold magenta]MEDIUM[/bold magenta]] "
    elif detection.severity == Severity.HIGH:
        title += "[[bold red]HIGH[/bold red]] "
    elif detection.severity == Severity.CRITICAL:
        title += "[[bold red]CRITICAL[/bold red]] "

    title += detection.name
    if detector_name:
        title += f" \\[{detector_name}]"

    # Build content
    content_parts = []

    if detection.detection:
        content_parts.append(f"[bold]Detection:[/bold]\n{detection.detection}")

    if detection.recommendation:
        content_parts.append(f"\n[bold]Recommendation:[/bold]\n{detection.recommendation}")

    if detection.exploit:
        content_parts.append(f"\n[bold red]Exploit:[/bold red]\n{detection.exploit}")

    # Handle location and source
    subtitle = None
    if detection.location:
        loc = detection.location
        subtitle_parts = []

        if loc.source_unit_name:
            subtitle_parts.append(loc.source_unit_name)
        elif loc.file_path:
            subtitle_parts.append(str(loc.file_path))

        if loc.start_line:
            subtitle_parts.append(f"line {loc.start_line}")

        subtitle = " - ".join(subtitle_parts) if subtitle_parts else None

        # Add source snippet if available
        if loc.source_snippet:
            syntax = Syntax(
                loc.source_snippet,
                "solidity",
                theme=theme,
                line_numbers=True,
                start_line=loc.start_line or 1,
            )
            content_parts.append(syntax)

    # Create panel with all content
    panel_content = "\n".join(str(part) for part in content_parts) if content_parts else "No details available"

    panel = Panel.fit(
        panel_content,
        title=title,
        title_align="left",
        subtitle=subtitle,
        subtitle_align="left",
    )

    console.print("\n")
    console.print(panel)


def export_detections_json(
    detections: List[Tuple[str, Detection]],
    output_path: Path,
) -> None:
    """Export detections to JSON format."""
    data = []
    for detector_name, detection in detections:
        detection_data = detection.to_dict()
        detection_data["detector_name"] = detector_name
        data.append(detection_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2))