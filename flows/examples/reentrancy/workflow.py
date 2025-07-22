"""Reentrancy vulnerability detector using Wake's built-in detection capabilities."""

from wake_ai.templates import MarkdownDetector


class ReentrancyDetector(MarkdownDetector):
    """Enhanced reentrancy detector that leverages Wake's static analysis."""

    name = "reentrancy"

    def __init__(self, **kwargs):
        """Initialize the reentrancy detector."""
        super().__init__(name=self.name, **kwargs)

    def get_detector_prompt(self) -> str:
        """Define the reentrancy detection workflow."""
        return """# Reentrancy Vulnerability Analysis

<task>
Perform comprehensive reentrancy vulnerability analysis by combining Wake's static analysis with manual verification
</task>

<context>
This detector focuses on identifying reentrancy vulnerabilities using Wake's built-in detection capabilities as a starting point, then performing deeper analysis to eliminate false positives and identify complex patterns.
</context>

<steps>

1. **Initialize Wake and run built-in reentrancy detection**
   - First, ensure Wake is initialized in the codebase:
     ```bash
     wake init
     ```
   - Run Wake's reentrancy detector to get baseline results:
     ```bash
     wake detect reentrancy
     ```
   - Capture and analyze the output for initial findings

2. **Parse Wake detector results**
   - Extract all reentrancy warnings from Wake's output
   - For each finding, note:
     - Contract and function names
     - Line numbers and file paths
     - Wake's confidence level
     - Suggested severity

3. **Manual verification of each finding**
   For each potential reentrancy issue identified by Wake:

   a) **Analyze the complete function context**
      - Read the entire function implementation
      - Identify all external calls (call, delegatecall, transfer, send)
      - Map all state changes before and after external calls
      - Check for reentrancy guards (nonReentrant modifiers)

   b) **Trace the call flow**
      - Identify what contracts/addresses are being called
      - Determine if calls are to trusted or untrusted contracts
      - Check if the called contract can callback into the vulnerable function
      - Analyze whether msg.sender checks would prevent exploitation

   c) **Verify exploitability**
      - Can an attacker control the external call target?
      - Are there state changes after the external call that can be exploited?
      - What would be the impact of a successful reentrancy attack?
      - Are there any mitigating factors (e.g., limited gas, access controls)?

4. **Identify additional reentrancy patterns**
   Look for complex reentrancy vulnerabilities that Wake might miss:

   - **Cross-function reentrancy**: State shared between multiple functions
   - **Read-only reentrancy**: View functions called during state transitions
   - **Cross-contract reentrancy**: Reentrancy through multiple contract interactions
   - **ERC777/1155 hooks**: Token callbacks that could enable reentrancy

5. **Classify and document findings**
   For each confirmed reentrancy vulnerability:

   - **Severity assessment**:
     - Critical: Direct loss of funds possible
     - High: Significant protocol manipulation or accounting errors
     - Medium: Limited impact or requires specific conditions
     - Low: Minimal impact or highly unlikely exploitation

   - **Required documentation**:
     - Exact vulnerable code with line numbers
     - Step-by-step attack scenario
     - Proof of concept if straightforward
     - Specific remediation (e.g., CEI pattern, reentrancy guard)

</steps>

<validation_requirements>

**Technical Evidence Standard**:
- Every finding must include the exact sequence of calls that enables reentrancy
- Identify specific state variables that can be manipulated
- Provide concrete attack scenarios, not theoretical possibilities

**False Positive Elimination**:
- Verify that external calls can actually callback (not just any external call)
- Check if reentrancy guards or other protections are already in place
- Confirm that state changes after external calls are actually exploitable

**Wake Integration Notes**:
- Use Wake's findings as a starting point, not the final answer
- Wake may flag safe patterns (e.g., transfers to EOAs) - verify each one
- Look for patterns Wake might miss in complex multi-contract systems

</validation_requirements>"""