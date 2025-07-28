"""Detection-specific classes and utilities for AI tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .utils.common import StrEnum


class Severity(StrEnum):
    """Severity levels for AI detector results."""

    INFO = "info"
    WARNING = "warning"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Location:
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
class Detection:
    """Detection result combining all detection information."""

    name: str  # Detection title/name
    severity: Severity
    detection_type: str  # e.g., "vulnerability", "gas-optimization", "best-practice"
    source: Optional[str] = None  # Workflow/detector that found this issue
    location: Optional[Location] = None
    description: Optional[str] = None  # Main detection description
    recommendation: Optional[str] = None
    exploit: Optional[str] = None
    uri: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {
            "name": self.name,
            "severity": self.severity.value,
            "detection_type": self.detection_type,
        }

        if self.source:
            data["source"] = self.source
        if self.location:
            data["location"] = self.location.to_dict()
        if self.description:
            data["description"] = self.description
        if self.recommendation:
            data["recommendation"] = self.recommendation
        if self.exploit:
            data["exploit"] = self.exploit
        if self.uri:
            data["uri"] = self.uri

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Detection:
        """Create Detection from dictionary."""
        # Parse location if present
        location = None
        if "location" in data:
            loc_data = data["location"]
            location = Location(
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
            source=data.get("source"),
            location=location,
            description=data.get("description"),
            recommendation=data.get("recommendation"),
            exploit=data.get("exploit"),
            uri=data.get("uri"),
        )