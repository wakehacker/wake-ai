"""Abstract base class for markdown-based detector workflows."""

import logging
from abc import abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
import yaml

from ..core.flow import AIWorkflow, ClaudeCodeResponse
from ..detections import AIDetection, AIDetectionResult, AILocation, Severity

logger = logging.getLogger(__name__)


class MarkdownDetectorResult(AIDetectionResult):
    """Result class for markdown detector workflows that reuses AIDetectionResult."""
    
    @classmethod
    def from_working_dir(cls, working_dir: Path, raw_results: Dict[str, Any]) -> "MarkdownDetectorResult":
        """Parse detector results from the simplified results.yaml format."""
        # Create instance first with empty detections
        instance = cls([], working_dir)
        
        # Parse results.yaml directly
        results_file = working_dir / "results.yaml"
        detections = []
        
        if results_file.exists():
            try:
                with open(results_file, 'r') as f:
                    data = yaml.safe_load(f)
                
                detector_name = raw_results.get('workflow', 'markdown-detector')
                
                for detection_data in data.get('detections', []):
                    # Parse location if present
                    location = None
                    if 'location' in detection_data:
                        loc = detection_data['location']
                        location = AILocation(
                            target=loc.get('target', 'Unknown'),
                            file_path=Path(loc['file']) if 'file' in loc else None,
                            start_line=loc.get('start_line'),
                            end_line=loc.get('end_line'),
                            source_snippet=loc.get('snippet')
                        )
                    
                    # Map severity
                    severity_str = detection_data.get('severity', 'medium').lower()
                    severity_map = {
                        'info': Severity.INFO,
                        'warning': Severity.WARNING,
                        'low': Severity.LOW,
                        'medium': Severity.MEDIUM,
                        'high': Severity.HIGH,
                        'critical': Severity.CRITICAL
                    }
                    severity = severity_map.get(severity_str, Severity.MEDIUM)
                    
                    detection = AIDetection(
                        name=detection_data.get('title', 'Unnamed Detection'),
                        severity=severity,
                        detection_type=detection_data.get('type', 'vulnerability'),
                        location=location,
                        detection=detection_data.get('description', ''),
                        recommendation=detection_data.get('recommendation'),
                        exploit=detection_data.get('exploit'),
                        metadata=detection_data.get('metadata', {})
                    )
                    detections.append((detector_name, detection))
                    
            except Exception as e:
                logger.error(f"Failed to parse results.yaml: {e}")
        
        # Set the parsed detections
        instance.detections = detections
        return instance
    
    def pretty_print(self, console):
        """Pretty print the detections to console."""
        from ..detections import print_ai_detection
        
        if not self.detections:
            console.print("[yellow]No detections found.[/yellow]")
            return
        
        console.print(f"\n[bold]Found {len(self.detections)} detection(s):[/bold]")
        
        for detector_name, detection in self.detections:
            print_ai_detection(
                detector_name=detector_name,
                detection=detection,
                console=console
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert detections to dictionary format."""
        return {
            "detections": [
                {
                    "detector": detector_name,
                    **detection.to_dict()
                }
                for detector_name, detection in self.detections
            ],
            "working_directory": str(self.working_dir),
            "total_detections": len(self.detections)
        }
    
    def export_json(self, output_path: Path):
        """Export detections to JSON using the standard format."""
        from ..detections import export_ai_detections_json
        export_ai_detections_json(self.detections, output_path)


class MarkdownDetector(AIWorkflow):
    """Abstract base class for markdown-based detector workflows.
    
    This class simplifies creating custom detectors by:
    1. Providing a single abstract method to implement (get_detector_prompt)
    2. Handling the workflow setup and validation automatically
    3. Parsing results into standardized AIDetection format
    """
    
    # Default tools for detector workflows
    allowed_tools = ["Read", "Write", "Grep", "Glob", "LS", "Task", "TodoWrite"]
    
    def __init__(
        self,
        name: str,
        session: Optional[Any] = None,
        model: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
        execution_dir: Optional[Union[str, Path]] = None,
        **kwargs
    ):
        """Initialize markdown detector workflow."""
        super().__init__(
            name=name,
            result_class=MarkdownDetectorResult,
            session=session,
            model=model,
            working_dir=working_dir,
            execution_dir=execution_dir,
            **kwargs
        )
    
    @abstractmethod
    def get_detector_prompt(self) -> str:
        """Get the detector-specific prompt.
        
        This should return a markdown prompt that describes:
        1. What vulnerabilities/issues to look for
        2. Any specific patterns or code smells
        3. Context about the protocol/system being analyzed
        
        The prompt will be wrapped with instructions to output to results.yaml.
        """
        pass
    
    def _setup_steps(self):
        """Setup the detector workflow with a single analysis step."""
        # Get the detector-specific prompt
        detector_prompt = self.get_detector_prompt()
        
        # Wrap it with instructions for structured output
        full_prompt = self._build_analysis_prompt(detector_prompt)
        
        # Add single analysis step
        self.add_step(
            name="analyze",
            prompt_template=full_prompt,
            tools=["Read", "Write", "Grep", "Glob", "LS", "Task", "TodoWrite"],
            max_cost=20.0,
            validator=self._validate_results,
            max_retries=3,
            max_retry_cost=10.0
        )
    
    def _build_analysis_prompt(self, detector_prompt: str) -> str:
        """Build the full analysis prompt with output instructions."""
        return f"""You are a security auditor analyzing a codebase for potential issues.

## Task

{detector_prompt}

## Output Format

You MUST output your findings to a file named `results.yaml` in the working directory ({{working_dir}}).

The file should have the following structure:

```yaml
detections:
  - title: "Issue Title"
    severity: "critical|high|medium|low|info|warning"
    type: "vulnerability|gas-optimization|best-practice|code-quality"
    description: |
      Detailed description of the issue.
      Can be multiple lines.
    recommendation: |
      How to fix or mitigate this issue.
    location:
      target: "ContractName.functionName"  # or "ContractName" or "global"
      file: "path/to/file.sol"
      start_line: 42
      end_line: 45
      snippet: |
        // The problematic code
        function vulnerable() public {{
          // ...
        }}
    exploit: |  # Optional
      Proof of concept or exploit scenario
    metadata:  # Optional
      custom_field: "custom_value"
```

## Instructions

1. First, analyze the codebase structure to understand the system
2. Search for the specific issues mentioned in the task
3. For each issue found:
   - Provide a clear, descriptive title
   - Accurately assess the severity
   - Include the exact location with code snippet
   - Explain why it's an issue
   - Provide actionable recommendations
4. Write all findings to `{{working_dir}}/results.yaml`
5. If no issues are found, create the file with an empty detections list

Remember to be thorough but avoid false positives. Focus on real security issues or the specific concerns mentioned in the task.
"""
    
    def _validate_results(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        """Validate that results.yaml was created with proper structure."""
        errors = []
        
        results_file = self.working_dir / "results.yaml"
        if not results_file.exists():
            errors.append(f"Results file not created at {results_file}")
            return (False, errors)
        
        try:
            with open(results_file, 'r') as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                errors.append("Results file should contain a dictionary")
                return (False, errors)
            
            if 'detections' not in data:
                errors.append("Results file missing 'detections' key")
                return (False, errors)
            
            if not isinstance(data['detections'], list):
                errors.append("'detections' should be a list")
                return (False, errors)
            
            # Validate each detection
            for i, detection in enumerate(data['detections']):
                if not isinstance(detection, dict):
                    errors.append(f"Detection {i} should be a dictionary")
                    continue
                
                # Required fields
                required_fields = ['title', 'severity', 'type', 'description']
                for field in required_fields:
                    if field not in detection:
                        errors.append(f"Detection {i} missing required field '{field}'")
                
                # Validate severity
                if 'severity' in detection:
                    valid_severities = ['critical', 'high', 'medium', 'low', 'info', 'warning']
                    if detection['severity'].lower() not in valid_severities:
                        errors.append(f"Detection {i} has invalid severity: {detection['severity']}")
                
                # Validate type
                if 'type' in detection:
                    valid_types = ['vulnerability', 'gas-optimization', 'best-practice', 'code-quality']
                    if detection['type'] not in valid_types:
                        errors.append(f"Detection {i} has invalid type: {detection['type']}")
                
                # Validate location if present
                if 'location' in detection:
                    loc = detection['location']
                    if not isinstance(loc, dict):
                        errors.append(f"Detection {i} location should be a dictionary")
                    elif 'target' not in loc:
                        errors.append(f"Detection {i} location missing 'target' field")
        
        except yaml.YAMLError as e:
            errors.append(f"Invalid YAML in results file: {e}")
        except Exception as e:
            errors.append(f"Error validating results file: {e}")
        
        return (len(errors) == 0, errors)