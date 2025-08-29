"""Reentrancy vulnerability detector using Wake's built-in detection capabilities."""

from wake_ai import workflow
from wake_ai.templates import SimpleDetector

@workflow.command(name="reentrancy")
def factory():
    """Run reentrancy detector."""
    return ReentrancyDetector()


class ReentrancyDetector(SimpleDetector):
    """Enhanced reentrancy detector that leverages Wake's static analysis."""

    def get_detector_prompt(self) -> str:
        """Define the reentrancy detection workflow."""
        return """# Reentrancy Vulnerability Analysis

## Task
Perform comprehensive reentrancy vulnerability analysis by combining Wake's static analysis with manual verification to identify exploitable vulnerabilities.

## Process
1. Run Wake's built-in detector (`wake detect reentrancy`)
2. Manually verify each finding (function context, call flows, state changes)
3. Identify additional patterns (cross-function, read-only, cross-contract reentrancy)
4. Check for ERC777/1155 hook-based vulnerabilities
5. Classify by severity (critical/high/medium/low) based on impact

## Documentation Requirements
- Exact code location with line numbers
- Step-by-step attack scenario
- Concrete proof of concept
- Recommended remediation (CEI pattern, reentrancy guards)

## Validation Criteria
- Verify callbacks are possible and state changes occur after external calls
- Eliminate false positives by confirming actual exploitability
- Provide specific attack vectors, not theoretical possibilities"""