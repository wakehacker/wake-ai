"""AI-specific detector result classes without IR node dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from wake.utils import StrEnum


class AISeverity(StrEnum):
    """Severity levels for AI detector results."""

    INFO = "info"
    WARNING = "warning"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AILocation:
    """Location information without IR dependency."""

    target: str  # e.g., "ContractName", "ContractName.functionName", "global"
    file_path: Optional[Path] = None
    source_unit_name: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    source_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {"target": self.target}

        if self.file_path:
            data["file_path"] = str(self.file_path)
        if self.source_unit_name:
            data["source_unit_name"] = self.source_unit_name
        if self.start_line is not None:
            data["start_line"] = self.start_line
        if self.end_line is not None:
            data["end_line"] = self.end_line
        if self.start_offset is not None:
            data["start_offset"] = self.start_offset
        if self.end_offset is not None:
            data["end_offset"] = self.end_offset
        if self.source_snippet:
            data["source_snippet"] = self.source_snippet

        return data


@dataclass
class AIDetectionResult:
    """Detection without IR node requirement."""

    name: str  # Detection title/name
    location: Optional[AILocation] = None
    detection: Optional[str] = None  # Main detection description
    recommendation: Optional[str] = None
    exploit: Optional[str] = None
    subdetections: Tuple[AIDetectionResult, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {
            "name": self.name,
        }

        if self.location:
            data["location"] = self.location.to_dict()
        if self.detection:
            data["detection"] = self.detection
        if self.recommendation:
            data["recommendation"] = self.recommendation
        if self.exploit:
            data["exploit"] = self.exploit
        if self.subdetections:
            data["subdetections"] = [sub.to_dict() for sub in self.subdetections]

        return data


@dataclass
class AIDetectorResult:
    """Detector result for AI-based detectors."""

    detection: AIDetection
    severity: AISeverity
    detection_type: str  # e.g., "vulnerability", "gas-optimization", "best-practice"
    uri: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {
            "detection": self.detection.to_dict(),
            "severity": self.severity.value,
            "detection_type": self.detection_type,
        }

        if self.uri:
            data["uri"] = self.uri
        if self.metadata:
            data["metadata"] = self.metadata

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AIDetectorResult:
        """Create AIDetectorResult from dictionary."""
        # Parse location if present
        location = None
        if "location" in data["detection"]:
            loc_data = data["detection"]["location"]
            location = AILocation(
                target=loc_data["target"],
                file_path=Path(loc_data["file_path"]) if "file_path" in loc_data else None,
                source_unit_name=loc_data.get("source_unit_name"),
                start_line=loc_data.get("start_line"),
                end_line=loc_data.get("end_line"),
                start_offset=loc_data.get("start_offset"),
                end_offset=loc_data.get("end_offset"),
                source_snippet=loc_data.get("source_snippet"),
            )

        # Parse subdetections recursively
        subdetections = []
        if "subdetections" in data["detection"]:
            for sub_data in data["detection"]["subdetections"]:
                # Parse sublocation if present
                sublocation = None
                if "location" in sub_data:
                    sub_loc_data = sub_data["location"]
                    sublocation = AILocation(
                        target=sub_loc_data["target"],
                        file_path=Path(sub_loc_data["file_path"]) if "file_path" in sub_loc_data else None,
                        source_unit_name=sub_loc_data.get("source_unit_name"),
                        start_line=sub_loc_data.get("start_line"),
                        end_line=sub_loc_data.get("end_line"),
                        start_offset=sub_loc_data.get("start_offset"),
                        end_offset=sub_loc_data.get("end_offset"),
                        source_snippet=sub_loc_data.get("source_snippet"),
                    )

                subdetection = AIDetection(
                    name=sub_data["name"],
                    location=sublocation,
                    detection=sub_data.get("detection"),
                    recommendation=sub_data.get("recommendation"),
                    exploit=sub_data.get("exploit"),
                )
                subdetections.append(subdetection)

        # Create main detection
        detection = AIDetection(
            name=data["detection"]["name"],
            location=location,
            detection=data["detection"].get("detection"),
            recommendation=data["detection"].get("recommendation"),
            exploit=data["detection"].get("exploit"),
            subdetections=tuple(subdetections),
        )

        return cls(
            detection=detection,
            severity=AISeverity(data["severity"]),
            detection_type=data["detection_type"],
            uri=data.get("uri"),
            metadata=data.get("metadata", {}),
        )


def print_ai_detection(
    detector_name: str,
    result: AIDetectorResult,
    console: "rich.console.Console",
    theme: Union[str, "SyntaxTheme"] = "monokai",
    *,
    file_link: bool = True,
) -> None:
    """Print an AI detector result to the console."""
    from rich.panel import Panel
    from rich.style import Style
    from rich.syntax import Syntax
    from rich.tree import Tree

    def print_result(
        detection: AIDetection,
        tree: Optional[Tree],
        detector_id: Optional[str],
        severity: Optional[AISeverity] = None,
    ) -> Tree:
        # Build title with severity indicators
        title = ""
        if severity:
            if severity == AISeverity.INFO:
                title += "[[bold blue]INFO[/bold blue]] "
            elif severity == AISeverity.WARNING:
                title += "[[bold yellow]WARNING[/bold yellow]] "
            elif severity == AISeverity.LOW:
                title += "[[bold cyan]LOW[/bold cyan]] "
            elif severity == AISeverity.MEDIUM:
                title += "[[bold magenta]MEDIUM[/bold magenta]] "
            elif severity == AISeverity.HIGH:
                title += "[[bold red]HIGH[/bold red]] "
            elif severity == AISeverity.CRITICAL:
                title += "[[bold red]CRITICAL[/bold red]] "

        title += detection.name
        if detector_id:
            title += f" \\[{detector_id}]"

        # Build content
        content_parts = []

        if detection.detection:
            content_parts.append(f"[bold]Detection:[/bold]\n{detection.detection}")

        if detection.recommendation:
            content_parts.append(f"\n[bold]Recommendation:[/bold]\n{detection.recommendation}")

        if detection.exploit:
            content_parts.append(f"\n[bold red]Exploit:[/bold red]\n{detection.exploit}")

        # Handle location and source
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
        else:
            subtitle = None

        # Create panel with all content
        panel_content = "\n".join(str(part) for part in content_parts) if content_parts else "No details available"

        panel = Panel.fit(
            panel_content,
            title=title,
            title_align="left",
            subtitle=subtitle,
            subtitle_align="left",
        )

        if tree is None:
            t = Tree(panel)
        else:
            t = tree.add(panel)

        # Add subdetections
        for subdetection in detection.subdetections:
            print_result(subdetection, t, None, None)

        return t

    console.print("\n")
    tree = print_result(result.detection, None, detector_name, result.severity)
    console.print(tree)


def export_ai_detections_json(
    detections: List[Tuple[str, AIDetectorResult]],
    output_path: Path,
) -> None:
    """Export AI detections to JSON format."""
    import json

    data = []
    for detector_name, result in detections:
        detection_data = result.to_dict()
        detection_data["detector_name"] = detector_name
        data.append(detection_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2))