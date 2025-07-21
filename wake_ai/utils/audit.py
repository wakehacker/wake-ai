"""Audit workflow specific detection result parsing."""

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
import yaml

from ..detections import Detection, Location, Severity


class AuditResult:
    """Detection result specifically for security audit workflows."""

    def __init__(self, detections: List[Tuple[str, Detection]], working_dir: Path):
        self.detections = detections
        self.working_dir = working_dir

    @classmethod
    def from_working_dir(cls, working_dir: Path, raw_results: Dict[str, Any]) -> "AuditResult":
        """Parse audit workflow results from the working directory.

        Looks for the standard audit output structure and parses YAML/AsciiDoc files.
        """
        # Create instance first
        instance = cls([], working_dir)
        # Then parse detections using instance method
        instance.detections = instance.parse_audit_results(working_dir)
        return instance

    def parse_audit_results(self, working_dir: Path) -> List[Tuple[str, Detection]]:
        """Parse audit workflow results into Detection format.

        Args:
            working_dir: Path to the workflow working directory

        Returns:
            List of (detector_name, AIDetection) tuples
        """
        results = []
        
        # Look for issues directory directly in working_dir
        issues_dir = working_dir / "issues"
        if not issues_dir.exists():
            return results

        # Parse each issue file
        for issue_file in issues_dir.glob("*.adoc"):
            try:
                # Parse the AsciiDoc file
                sections = self._parse_adoc_file(issue_file)
                
                # Extract metadata from the file content
                content = issue_file.read_text()
                
                # Extract title from first line (= Title)
                title_match = re.search(r'^=\s+(.+)$', content, re.MULTILINE)
                title = title_match.group(1) if title_match else issue_file.stem
                
                # Extract metadata section if present
                metadata = {}
                severity = Severity.MEDIUM  # default
                contract_name = "Unknown"
                location = None
                
                # Look for metadata in the file (could be in comments or a dedicated section)
                if 'Metadata' in sections:
                    metadata_text = sections['Metadata']
                    # Parse YAML-like metadata
                    try:
                        metadata_dict = yaml.safe_load(metadata_text)
                        if isinstance(metadata_dict, dict):
                            severity = self._parse_severity(metadata_dict.get('severity', 'medium'))
                            contract_name = metadata_dict.get('contract', 'Unknown')
                            
                            # Parse location if present
                            if 'location' in metadata_dict:
                                loc_data = metadata_dict['location']
                                location = Location(
                                    target=f"{contract_name}.{loc_data.get('function', 'contract')}",
                                    file_path=Path(loc_data['file']) if 'file' in loc_data else None,
                                    start_line=loc_data.get('start_line'),
                                    end_line=loc_data.get('end_line'),
                                    source_snippet=loc_data.get('code_snippet')
                                )
                    except:
                        pass
                
                # Alternative: Try to extract severity from the title or content
                if not location:
                    # Look for severity indicators in the content
                    severity_match = re.search(r'\b(CRITICAL|HIGH|MEDIUM|LOW|INFO|WARNING)\b', content, re.IGNORECASE)
                    if severity_match:
                        severity = self._parse_severity(severity_match.group(1))
                    
                    # Try to extract contract name from title or content
                    contract_match = re.search(r'\b([A-Z][a-zA-Z0-9]+)\s*[:.\-]', title)
                    if contract_match:
                        contract_name = contract_match.group(1)
                
                # Get the main content sections
                detection_text = sections.get('Description', '')
                recommendation = sections.get('Recommendation', '')
                exploit = sections.get('Proof of Concept', sections.get('Exploit Scenario', ''))
                
                # Create the detection
                detection = Detection(
                    name=title,
                    severity=severity,
                    detection_type="vulnerability",
                    location=location,
                    detection=detection_text,
                    recommendation=recommendation,
                    exploit=exploit,
                    metadata=metadata
                )
                
                results.append(("ai-audit", detection))
                
            except Exception as e:
                # Skip files that can't be parsed
                continue

        return results
    
    def _parse_severity(self, severity_str: str) -> Severity:
        """Parse severity string to Severity enum."""
        severity_map = {
            'critical': Severity.CRITICAL,
            'high': Severity.HIGH,
            'medium': Severity.MEDIUM,
            'low': Severity.LOW,
            'info': Severity.INFO,
            'warning': Severity.WARNING
        }
        return severity_map.get(severity_str.lower(), Severity.MEDIUM)

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