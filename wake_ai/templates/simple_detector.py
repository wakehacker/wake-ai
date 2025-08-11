"""Abstract base class for simple detector workflows."""

from abc import abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Tuple
import yaml

from ..core.flow import AIWorkflow, ClaudeCodeResponse
from ..detections import Detection, Location, Severity
from ..results import AIResult
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SimpleDetectorResult(AIResult):
    """Result class for simple detector workflows."""

    def __init__(self, detections: List[Tuple[str, Detection]], working_dir: Path):
        """Initialize with detections and working directory."""
        self.detections = detections
        self.working_dir = working_dir

    @classmethod
    def from_working_dir(cls, working_dir: Path, raw_results: Dict[str, Any]) -> "SimpleDetectorResult":
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

                detector_name = raw_results.get('workflow', 'simple-detector')

                for detection_data in data.get('detections', []):
                    # Parse location if present
                    location = None
                    if 'location' in detection_data:
                        loc = detection_data['location']
                        location = Location(
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

                    detection = Detection(
                        name=detection_data.get('title', 'Unnamed Detection'),
                        severity=severity,
                        detection_type=detection_data.get('type', 'vulnerability'),
                        location=location,
                        description=detection_data.get('description', ''),
                        recommendation=detection_data.get('recommendation'),
                        exploit=detection_data.get('exploit')
                    )
                    detections.append((detector_name, detection))

            except Exception as e:
                logger.error(f"Failed to parse results.yaml: {e}")

        # Set the parsed detections
        instance.detections = detections
        return instance

    def pretty_print(self, console):
        """Pretty print the detections to console."""
        from ..utils.formatters import print_detection

        if not self.detections:
            console.print("[yellow]No detections found.[/yellow]")
            return

        console.print(f"\n[bold]Found {len(self.detections)} detection(s):[/bold]")

        for detector_name, detection in self.detections:
            print_detection(
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
        from ..utils.formatters import export_detections_json
        export_detections_json(self.detections, output_path)


class SimpleDetector(AIWorkflow):
    """Abstract base class for simple detector workflows.

    This class simplifies creating custom detectors by:
    1. Providing a single abstract method to implement (get_detector_prompt)
    2. Handling the workflow setup and validation automatically
    3. Parsing results into standardized AIDetection format
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, result_class=SimpleDetectorResult)

    @abstractmethod
    def get_detector_prompt(self) -> str:
        """Get the detector-specific prompt.

        This should return a prompt that describes:
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
        # Using None for allowed_tools to inherit the secure defaults from AIWorkflow
        self.add_step(
            name="analyze",
            prompt_template=full_prompt,
            allowed_tools=None,  # Use parent class defaults which include all necessary tools
            max_cost=20.0,
            validator=self._validate_results,
            max_retries=3,
            max_retry_cost=10.0
        )

    def _build_analysis_prompt(self, detector_prompt: str) -> str:
        """Build the full analysis prompt with output instructions."""
        return f"""<context>
You are a security auditor performing targeted vulnerability analysis. Your role is to identify real security issues with high confidence while avoiding false positives.

</context>

<task>
{detector_prompt}
</task>

<working_dir>
{{{{working_dir}}}}
</working_dir>

<steps>
## 1. **Discovery Phase**
   a. Map the codebase structure using `Glob` and `LS` tools
   b. Identify key contracts, interfaces, and dependencies
   c. Note architectural patterns and security-critical components
   d. Use Wake commands when helpful (e.g., `wake detect reentrancy`, `wake print`)

## 2. **Analysis Phase**
   a. Search for vulnerability patterns using `Grep` with regex patterns
   b. Read suspicious code sections with `Read` tool
   c. Trace data flows and state changes across contracts
   d. Validate each potential issue through:
      - Control flow analysis
      - State mutation tracking
      - External call examination
      - Access control verification

## 3. **Documentation Phase**
   a. For each confirmed vulnerability:
      - Extract exact code location and context
      - Determine accurate severity based on exploitability
      - Write clear, actionable recommendations
   b. Create `results.yaml` with all findings
   c. Include proof-of-concept scenarios where applicable
</steps>

<validation_requirements>
- **Technical Evidence**: Each detection MUST include specific code references
- **Severity Accuracy**:
  - CRITICAL: Direct fund loss, arbitrary code execution
  - HIGH: Indirect fund loss, major functionality compromise
  - MEDIUM: Limited impact, requires specific conditions
  - LOW: Best practice violations, minor inefficiencies
  - INFO/WARNING: Informational findings, no direct security impact
- **False Positive Elimination**: Verify exploitability before reporting
- **Location Precision**: Include exact file paths, line numbers, and code snippets
</validation_requirements>

<output_format>
Create `{{{{working_dir}}}}/results.yaml` with this structure:

```yaml
detections:
  - title: "Reentrancy in withdraw() allows draining contract funds"
    severity: "critical"
    type: "vulnerability"
    description: |
      The withdraw() function in Vault.sol performs an external call to msg.sender before updating the user's balance, allowing reentrancy attacks. An attacker can recursively call withdraw() to drain all funds from the contract.
    recommendation: |
      Apply the checks-effects-interactions pattern:
      1. Move the balance update before the external call
      2. Consider using ReentrancyGuard from OpenZeppelin
      3. Add a mutex lock to prevent concurrent withdrawals
    location:
      target: "Vault.withdraw"
      file: "contracts/Vault.sol"
      start_line: 45
      end_line: 52
      snippet: |
        function withdraw(uint256 amount) external {{
            require(balances[msg.sender] >= amount, "Insufficient balance");

            // Vulnerable: external call before state update
            (bool success, ) = msg.sender.call{{value: amount}}("");
            require(success, "Transfer failed");

            balances[msg.sender] -= amount;  // State updated after call
        }}
    exploit: |
        Consider the following exploit scenario:
        1. Alice deploys the ReentrancyAttack contract and calls attack() with 100 ETH.
      ```solidity
      contract ReentrancyAttack {{
          Vault public vault;
          uint256 public attackAmount;

          function attack() external payable {{
              attackAmount = msg.value;
              vault.deposit{{value: msg.value}}();
              vault.withdraw(attackAmount);
          }}

          receive() external payable {{
              if (address(vault).balance >= attackAmount) {{
                  vault.withdraw(attackAmount);
              }}
          }}
      }}
      ```
      2. Bob deposits 100 ETH into the Vault.

  # Additional detections follow the same structure...
```

**Field Requirements**:
- `title`: Concise, specific description of the vulnerability
- `severity`: One of [critical, high, medium, low, info, warning]
- `type`: One of [vulnerability, gas-optimization, best-practice, code-quality]
- `description`: Detailed explanation with technical context
- `recommendation`: Step-by-step remediation guidance
- `location`: Required fields: target, file; Optional: start_line, end_line, snippet
- `exploit`: (Optional, must be included if severity is higher or equal to low) Proof of concept code or attack scenario

If no vulnerabilities are found, create the file with:
```yaml
detections: []
```
</output_format>"""

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