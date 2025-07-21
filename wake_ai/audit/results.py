"""Audit-specific result types that implement the DetectionTask base class."""

from pathlib import Path
from typing import List, Tuple

from wake.ai.tasks import DetectionTask
from wake.ai.detections import AIDetection, AuditResultParser


class AuditDetectionResults(DetectionTask):
    """Audit task results for security vulnerability detection."""
    
    def get_task_type(self) -> str:
        """Return the task type identifier."""
        return "security-audit"
    
    def get_no_detections_message(self) -> str:
        """Return the message to display when no detections are found."""
        return "No security issues detected."
    
    @classmethod
    def parse_results(cls, working_dir: Path) -> List[Tuple[str, AIDetection]]:
        """Parse audit workflow results into AIDetection format.
        
        Args:
            working_dir: Path to the workflow working directory
            
        Returns:
            List of (detector_name, AIDetection) tuples
        """
        # Delegate to the AuditResultParser to avoid code duplication
        return AuditResultParser.parse_audit_results(working_dir)