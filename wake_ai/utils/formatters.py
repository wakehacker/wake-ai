"""Formatting utilities for AI detections."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Tuple, Union

from ..detections import Detection, Severity

if TYPE_CHECKING:
    from rich.console import Console
    from rich.syntax import SyntaxTheme


def _parse_content_with_code_blocks(content: str, theme: Union[str, "SyntaxTheme"] = "monokai") -> List[Any]:
    """Parse content and convert code blocks to Syntax objects."""
    from rich.syntax import Syntax
    from rich.text import Text
    import re
    
    parts = []
    # Pattern to match code blocks with optional language
    code_block_pattern = r'```(\w*)\n?(.*?)```'
    
    last_end = 0
    for match in re.finditer(code_block_pattern, content, re.DOTALL):
        # Add text before code block
        if match.start() > last_end:
            text_before = content[last_end:match.start()].strip()
            if text_before:
                parts.append(Text.from_markup(text_before))
        
        # Add empty line before code block
        if parts and not isinstance(parts[-1], Text) or (isinstance(parts[-1], Text) and parts[-1].plain):
            parts.append(Text())
        
        # Add code block as Syntax object
        language = match.group(1) or "text"
        code = match.group(2).strip()
        if code:
            syntax = Syntax(code, language, theme=theme, line_numbers=False)
            parts.append(syntax)
        
        # Add empty line after code block
        parts.append(Text())
        
        last_end = match.end()
    
    # Add remaining text after last code block
    if last_end < len(content):
        remaining_text = content[last_end:].strip()
        if remaining_text:
            parts.append(Text.from_markup(remaining_text))
    
    # If no code blocks found, return the original content
    if not parts:
        parts.append(Text.from_markup(content))
    
    return parts


def print_detection(
    detector_name: str,
    detection: Detection,
    console: "Console",
    theme: Union[str, "SyntaxTheme"] = "monokai",
    *,
    file_link: bool = True,
) -> None:
    """Print a detection to the console."""
    from rich.console import Group
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.text import Text

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

    if detection.description:
        # Add detection section with improved formatting
        content_parts.append(Text.from_markup("[bold cyan]Detection[/bold cyan]"))
        # Parse and add content with code blocks
        content_with_code = _parse_content_with_code_blocks(detection.description.strip(), theme)
        content_parts.extend(content_with_code)

    if detection.recommendation:
        if content_parts:
            content_parts.append(Text())  # Empty line
        
        content_parts.append(Text.from_markup("[bold cyan]Recommendation[/bold cyan]"))
        # Parse and add content with code blocks
        content_with_code = _parse_content_with_code_blocks(detection.recommendation.strip(), theme)
        content_parts.extend(content_with_code)

    if detection.exploit:
        if content_parts:
            content_parts.append(Text())  # Empty line
        
        content_parts.append(Text.from_markup("[bold cyan]Exploit[/bold cyan]"))
        # Parse and add content with code blocks
        content_with_code = _parse_content_with_code_blocks(detection.exploit.strip(), theme)
        content_parts.extend(content_with_code)

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
            if content_parts:
                content_parts.append(Text())  # Empty line
            
            content_parts.append(Text.from_markup("[bold cyan]Source Code[/bold cyan]"))
            
            syntax = Syntax(
                loc.source_snippet,
                "solidity",
                theme=theme,
                line_numbers=True,
                start_line=loc.start_line or 1,
            )
            content_parts.append(syntax)

    # Create panel with all content using Group to combine renderables
    panel_content = Group(*content_parts) if content_parts else Text("No details available")

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