"""Audit workflow specific detection result parsing."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional, TYPE_CHECKING
import yaml

from wake_ai.detections import Location
from wake_ai.results import AIResult

if TYPE_CHECKING:
    from rich.console import Console


@dataclass
class AuditDetection:
    """Audit-specific detection with impact and confidence instead of severity."""

    name: str  # Detection title/name
    impact: str  # high, medium, low, warning, info
    confidence: str  # high, medium, low
    detection_type: str  # e.g., "vulnerability", "gas-optimization", "best-practice"
    description: str  # Main detection description
    source: Optional[str] = None  # Workflow/detector that found this issue
    location: Optional[Location] = None
    recommendation: Optional[str] = None
    exploit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {
            "name": self.name,
            "impact": self.impact,
            "confidence": self.confidence,
            "detection_type": self.detection_type,
            "description": self.description,
        }

        if self.source:
            data["source"] = self.source

        if self.location:
            data["location"] = self.location.to_dict()
        if self.recommendation:
            data["recommendation"] = self.recommendation
        if self.exploit:
            data["exploit"] = self.exploit

        return data


class AuditResult(AIResult):
    """Detection result specifically for security audit workflows."""

    def __init__(self, detections: List[AuditDetection], working_dir: Path, metadata: Optional[Dict[str, Any]] = None):
        self.detections = detections
        self.working_dir = working_dir
        self.metadata = metadata or {}

    @classmethod
    def from_working_dir(cls, working_dir: Path, raw_results: Dict[str, Any]) -> "AuditResult":
        """Parse audit workflow results from the working directory.

        Looks for the standard audit output structure and parses YAML/AsciiDoc files.
        """
        # Create instance first
        instance = cls([], working_dir)
        # Then parse detections using instance method
        instance.detections = instance.parse_audit_results(working_dir)
        # Parse metadata from audit artifacts
        instance.metadata = instance.parse_audit_metadata(working_dir)
        return instance

    def parse_audit_results(self, working_dir: Path) -> List[AuditDetection]:
        """Parse audit workflow results into AuditDetection format.

        Args:
            working_dir: Path to the workflow working directory

        Returns:
            List of AuditDetection objects
        """
        results = []

        # Look for issues directory directly in working_dir
        issues_dir = working_dir / "issues"
        if not issues_dir.exists():
            return results

        # Parse each YAML issue file
        for issue_file in issues_dir.glob("*.yaml"):
            try:
                # Load the YAML file
                with open(issue_file, 'r') as f:
                    issue_data = yaml.safe_load(f)

                if not isinstance(issue_data, dict):
                    continue

                # Extract basic fields
                name = issue_data.get('name', issue_file.stem)
                impact = issue_data.get('impact', 'medium')
                confidence = issue_data.get('confidence', 'medium')
                detection_type = issue_data.get('detection_type', 'N/A')

                # Parse location
                location = None
                if 'location' in issue_data and isinstance(issue_data['location'], dict):
                    loc = issue_data['location']
                    location = Location(
                        target=loc.get('target', 'Unknown'),
                        file_path=Path(loc['file']) if 'file' in loc else None,
                        start_line=loc.get('start_line'),
                        end_line=loc.get('end_line'),
                        source_snippet=loc.get('code_snippet')
                    )

                # Get content fields (with markdown/asciidoc content)
                description_text = issue_data.get('description', 'No description provided')
                recommendation = issue_data.get('recommendation', '')
                exploit = issue_data.get('exploit', '')

                # Create the audit detection
                detection = AuditDetection(
                    name=name,
                    impact=impact,
                    confidence=confidence,
                    detection_type=detection_type,
                    source="audit",  # Automatically set to workflow name
                    location=location,
                    description=description_text,
                    recommendation=recommendation,
                    exploit=exploit
                )

                results.append(detection)

            except yaml.YAMLError as e:
                # Skip files that can't be parsed
                print(f"Error parsing YAML file {issue_file}: {e}")
                continue
            except Exception as e:
                # Skip other errors
                print(f"Error processing issue file {issue_file}: {e}")
                continue

        return results

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

    def parse_audit_metadata(self, working_dir: Path) -> Dict[str, Any]:
        """Parse audit metadata from workflow artifacts.

        Collects:
        - Executive summary
        - Project overview
        - Other relevant audit metadata
        """
        metadata = {}

        # Parse executive summary
        executive_summary_file = working_dir / "executive-summary.md"
        if executive_summary_file.exists():
            metadata["executive_summary"] = executive_summary_file.read_text()

        # Parse project overview
        overview_file = working_dir / "overview.md"
        if overview_file.exists():
            metadata["project_overview"] = overview_file.read_text()

        # Skip parsing audit plan - not needed in exported metadata

        # Note: impact_confidence_summary is calculated in pretty_print for display only

        return metadata

    def pretty_print(self, console: "Console") -> None:
        """Print audit results in a formatted manner."""
        from rich.table import Table
        from rich import box

        # Print summary
        console.print("\n[bold cyan]Audit Results Summary[/bold cyan]")
        console.print(f"Total findings: {len(self.detections)}")

        # Print findings
        if self.detections:
            console.print("\n[bold]Findings:[/bold]")
            for detection in self.detections:
                impact_color = {
                    "high": "bright_red",
                    "medium": "yellow",
                    "low": "bright_yellow",
                    "warning": "magenta",
                    "info": "blue"
                }.get(detection.impact.lower(), "white")

                confidence_label = {
                    "high": "●●●",
                    "medium": "●●○",
                    "low": "●○○"
                }.get(detection.confidence.lower(), "●○○")

                console.print(f"\n[{impact_color}][{detection.impact.upper()}][/{impact_color}] {confidence_label} {detection.name}")
                if detection.location:
                    console.print(f"  Location: {detection.location.target}")
                console.print(f"  {detection.description}")

        console.print(f"\n[green]Full results saved to: {self.working_dir}[/green]")

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit results to dictionary for JSON export."""
        return {
            "status": "completed",
            "findings": [
                {
                    "source": detection.source,
                    "name": detection.name,
                    "impact": detection.impact,
                    "confidence": detection.confidence,
                    "type": detection.detection_type,
                    "location": {
                        "target": detection.location.target if detection.location else None,
                        "file": str(detection.location.file_path) if detection.location and detection.location.file_path else None,
                        "start_line": detection.location.start_line if detection.location else None,
                        "end_line": detection.location.end_line if detection.location else None
                    } if detection.location else None,
                    "description": detection.description,
                    "recommendation": detection.recommendation,
                    "exploit": detection.exploit
                }
                for detection in self.detections
            ],
            "metadata": self.metadata
        }