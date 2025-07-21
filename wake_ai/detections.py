"""Detection-specific classes and utilities for AI tasks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union
from .utils import StrEnum
import yaml

if TYPE_CHECKING:
    from rich.console import Console
    from rich.syntax import SyntaxTheme


class Severity(StrEnum):
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
class AIDetection:
    """AI detection result combining all detection information."""

    name: str  # Detection title/name
    severity: Severity
    detection_type: str  # e.g., "vulnerability", "gas-optimization", "best-practice"
    location: Optional[AILocation] = None
    detection: Optional[str] = None  # Main detection description
    recommendation: Optional[str] = None
    exploit: Optional[str] = None
    uri: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {
            "name": self.name,
            "severity": self.severity.value,
            "detection_type": self.detection_type,
        }

        if self.location:
            data["location"] = self.location.to_dict()
        if self.detection:
            data["detection"] = self.detection
        if self.recommendation:
            data["recommendation"] = self.recommendation
        if self.exploit:
            data["exploit"] = self.exploit
        if self.uri:
            data["uri"] = self.uri
        if self.metadata:
            data["metadata"] = self.metadata

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AIDetection:
        """Create AIDetection from dictionary."""
        # Parse location if present
        location = None
        if "location" in data:
            loc_data = data["location"]
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

        return cls(
            name=data["name"],
            severity=Severity(data["severity"]),
            detection_type=data["detection_type"],
            location=location,
            detection=data.get("detection"),
            recommendation=data.get("recommendation"),
            exploit=data.get("exploit"),
            uri=data.get("uri"),
            metadata=data.get("metadata", {}),
        )


class AIDetectionResult:
    """Detection result specifically for security audit workflows."""

    def __init__(self, detections: List[Tuple[str, AIDetection]], working_dir: Path):
        self.detections = detections
        self.working_dir = working_dir

    @classmethod
    def from_working_dir(cls, working_dir: Path, raw_results: Dict[str, Any]) -> "AIDetectionResult":
        """Parse audit workflow results from the working directory.

        Looks for the standard audit output structure and parses YAML/AsciiDoc files.
        """
        # Create instance first
        instance = cls([], working_dir)
        # Then parse detections using instance method
        instance.detections = instance.parse_audit_results(working_dir)
        return instance

    def parse_audit_results(self, working_dir: Path) -> List[Tuple[str, AIDetection]]:
        """Parse audit workflow results into AIDetection format.

        Args:
            working_dir: Path to the workflow working directory

        Returns:
            List of (detector_name, AIDetection) tuples
        """
        results = []
        audit_dir = working_dir / "audit"

        if not audit_dir.exists():
            return results

        # Read the plan.yaml file
        plan_file = audit_dir / "plan.yaml"
        if not plan_file.exists():
            return results

        try:
            with open(plan_file, 'r') as f:
                plan_data = yaml.safe_load(f)
        except Exception:
            return results

        # Convert true positive issues to AIDetectorResult
        for contract in plan_data.get('contracts', []):
            contract_name = contract.get('name', 'Unknown')

            for issue in contract.get('issues', []):
                if issue.get('status') != 'true_positive':
                    continue

                # Map severity
                severity_map = {
                    'critical': Severity.CRITICAL,
                    'high': Severity.HIGH,
                    'medium': Severity.MEDIUM,
                    'low': Severity.LOW,
                    'info': Severity.INFO,
                    'warning': Severity.WARNING
                }
                severity = severity_map.get(issue.get('severity', 'medium').lower(), Severity.MEDIUM)

                # Build location
                location = None
                if 'location' in issue:
                    loc_data = issue['location']
                    location = AILocation(
                        target=f"{contract_name}.{loc_data.get('function', 'contract')}",
                        file_path=Path(loc_data['file']) if 'file' in loc_data else None,
                        start_line=loc_data.get('lines', {}).get('start'),
                        end_line=loc_data.get('lines', {}).get('end'),
                        source_snippet=loc_data.get('code_snippet')
                    )

                # Get issue details from the issue file if it exists
                detection_text = issue.get('description', '')
                recommendation = issue.get('recommendation', '')
                exploit = issue.get('exploit', '')

                # Try to find the detailed issue file
                issues_dir = audit_dir / "issues"
                if issues_dir.exists():
                    issue_file = self._find_issue_file(issues_dir, issue, contract_name)

                    if issue_file:
                        sections = self._parse_adoc_file(issue_file)

                        # Use parsed sections
                        if 'Description' in sections:
                            detection_text = sections['Description']
                        if 'Recommendation' in sections:
                            recommendation = sections['Recommendation']
                        if 'Proof of Concept' in sections or 'Exploit Scenario' in sections:
                            exploit = sections.get('Proof of Concept', sections.get('Exploit Scenario', ''))

                # Create the detection
                detection = AIDetection(
                    name=issue.get('title', 'Unnamed Issue'),
                    severity=severity,
                    detection_type="vulnerability",
                    location=location,
                    detection=detection_text,
                    recommendation=recommendation,
                    exploit=exploit,
                    metadata={
                        "contract": contract_name,
                        "validation_comment": issue.get('comment', '')
                    }
                )

                results.append(("ai-audit", detection))

        return results

    def _find_issue_file(self, issues_dir: Path, issue: Dict[str, Any], contract_name: str) -> Optional[Path]:
        """Find the detailed issue file for a given issue."""
        # Create a safe filename from the issue title
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', issue.get('title', 'issue'))
        possible_files = [
            issues_dir / f"{safe_title}.adoc",
            issues_dir / f"{contract_name}_{safe_title}.adoc"
        ]

        for pf in possible_files:
            if pf.exists():
                return pf

        # If still not found, try to match by content
        for adoc_file in issues_dir.glob("*.adoc"):
            content = adoc_file.read_text()
            if issue.get('title', '') in content:
                return adoc_file

        return None

    def _parse_adoc_file(self, file_path: Path) -> Dict[str, str]:
        """Parse an AsciiDoc file and extract sections."""
        content = file_path.read_text()

        # Extract sections (simplified parsing)
        sections = {}
        current_section = None
        current_content = []

        for line in content.split('\n'):
            if line.startswith('== '):
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = line[3:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)

        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()

        return sections


def print_ai_detection(
    detector_name: str,
    detection: AIDetection,
    console: "Console",
    theme: Union[str, "SyntaxTheme"] = "monokai",
    *,
    file_link: bool = True,
) -> None:
    """Print an AI detection to the console."""
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


def export_ai_detections_json(
    detections: List[Tuple[str, AIDetection]],
    output_path: Path,
) -> None:
    """Export AI detections to JSON format."""
    data = []
    for detector_name, detection in detections:
        detection_data = detection.to_dict()
        detection_data["detector_name"] = detector_name
        data.append(detection_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2))