"""Reentrancy vulnerability detector using Wake's built-in detection capabilities."""

from wake_ai.templates import MarkdownDetector


class ReentrancyDetector(MarkdownDetector):
    """Enhanced reentrancy detector that leverages Wake's static analysis."""
    
    name = "reentrancy"
    
    def get_detector_prompt(self) -> str:
        """Define the reentrancy detection workflow."""
        return """# Reentrancy Vulnerability Analysis

<task>
Perform comprehensive reentrancy vulnerability analysis by combining Wake's static analysis with manual verification
</task>

<context>
This detector focuses on identifying reentrancy vulnerabilities using Wake's built-in detection capabilities as a starting point, then performing deeper analysis to eliminate false positives and identify complex patterns.
</context>

<working_dir>
Work in the assigned directory `{working_dir}` to store analysis results.
</working_dir>

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

</validation_requirements>

<output_format>
Create results.yaml with findings structured as:

```yaml
detections:
  - title: "Reentrancy in withdraw() allows draining contract"
    severity: "critical"
    type: "vulnerability"
    description: |
      The withdraw() function updates user balance after transferring ETH,
      allowing an attacker to re-enter and withdraw multiple times.
      
      Wake detector initially flagged this on line 45. Manual analysis confirmed
      the vulnerability with the following attack flow:
      1. Attacker calls withdraw() with malicious contract
      2. Contract receives ETH and its fallback function executes
      3. Fallback function calls withdraw() again before balance update
      4. Process repeats until contract is drained
    
    location:
      target: "Vault.withdraw"
      file: "contracts/Vault.sol"
      start_line: 43
      end_line: 48
      snippet: |
        function withdraw(uint256 amount) external {
            require(balances[msg.sender] >= amount, "Insufficient balance");
            
            (bool success, ) = msg.sender.call{value: amount}(""); // External call
            require(success, "Transfer failed");
            
            balances[msg.sender] -= amount; // State update after call - VULNERABLE!
        }
    
    recommendation: |
      Apply the Checks-Effects-Interactions pattern:
      
      ```solidity
      function withdraw(uint256 amount) external {
          require(balances[msg.sender] >= amount, "Insufficient balance");
          
          balances[msg.sender] -= amount; // Update state first
          
          (bool success, ) = msg.sender.call{value: amount}("");
          require(success, "Transfer failed");
      }
      ```
      
      Alternatively, use OpenZeppelin's ReentrancyGuard modifier.
    
    metadata:
      wake_detected: true
      wake_confidence: "high"
      pattern_type: "classic_reentrancy"
```
</output_format>"""


# Example usage
if __name__ == "__main__":
    detector = ReentrancyDetector()
    results = detector.execute()
    
    formatted_results = detector.format_results(results)
    formatted_results.pretty_print(console=None)