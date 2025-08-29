# Execute Manual Review

<task>
Perform systematic manual review of the codebase following the audit plan with rigorous validation
</task>

<context>
Plan: `{{working_dir}}/plan.yaml`
</context>

<working_dir>
Work in the assigned directory `{{working_dir}}` where the audit plan and results will be stored.
</working_dir>

<steps>

1. **Load and validate audit plan**

    - Read `{{working_dir}}/plan.yaml`
    - Verify all planned issues are technically sound and codebase-specific
    - Remove any generic findings that slipped through initial analysis

2. **Systematic issue validation**

    - Work through each contract and issue sequentially
    - For each issue, perform deep technical validation:
        - Navigate to exact file location and line numbers
        - Read full function context and surrounding code
        - Trace complete data flow and state changes
        - Identify all function callers and callees
        - Verify exploitability with concrete attack scenarios
        - Check for mitigating factors or protective mechanisms

3. **Update plan with validation results** (`{{working_dir}}/plan.yaml`)
    - Modify the YAML structure to include validation status
    - Update each issue with the `status` field, adding a `comment` field to explain the validation results
    - Consider updating the `impact` and `confidence` fields based on the validation results if the issue is not a false positive
    ```yaml
    contracts:
        - name: ContractA
          issues:
              - title: Reentrancy vulnerability in withdraw function
                status: true_positive # pending -> true_positive/false_positive
                location:
                    file: src/Vault.sol
                    lines: "45-52"
                    function: withdraw
                description: Function calls external contract before updating user balance, enabling reentrancy
                impact: high # info/warning/low/medium/high
                confidence: high # low/medium/high
                comment: "Confirmed: balance updated after external call on line 48, user.balance check on line 46 can be bypassed"
    ```
4. **Create detailed issue files** (only for true positives)

    - Create `{{working_dir}}/issues/` directory if needed
    - File naming: `[impact]-[contract]-[brief-description].yaml`
    - Each issue file must be a valid YAML file with markdown/asciidoc content embedded
    - Example structure:

    ````yaml
    name: Reentrancy Vulnerability in Withdraw Function
    impact: high
    confidence: high
    detection_type: Reentrancy  # Valid types: Data validation, Code quality, Logic error, Standards violation, Gas optimization, Logging, Trust model, Arithmetics, Access control, Unused code, Storage clashes, Denial of service, Front-running, Replay attack, Reentrancy, Function visibility, Overflow/Underflow, Configuration, Reinitialization, Griefing, N/A (Ensure correct spelling and capitalization)
    location:
        target: Vault.withdraw
        file: src/Vault.sol
        start_line: 45
        end_line: 52
        function: withdraw
        code_snippet: |
            function withdraw(uint256 amount) public {
                require(balances[msg.sender] >= amount);
                (bool success, ) = msg.sender.call{value: amount}("");
                require(success);
                balances[msg.sender] -= amount;  // State updated after external call
            }

    description: |
        The withdraw function in the Vault contract is vulnerable to reentrancy attacks. The function sends ETH to the caller before updating the sender's balance, allowing a malicious contract to recursively call withdraw() and drain the contract.

        The vulnerability occurs because:
        - Line 48: External call is made with `msg.sender.call{value: amount}("")`
        - Line 50: Balance is updated after the external call
        - This violates the checks-effects-interactions pattern

        ```solidity
        function withdraw(uint256 amount) public {
            require(balances[msg.sender] >= amount);
            (bool success, ) = msg.sender.call{value: amount}("");  // External call
            require(success);
            balances[msg.sender] -= amount;  // State update AFTER call
        }
    ````

    exploit: |
    An attacker can exploit this vulnerability:

    1. Deploy a malicious contract with a fallback function that calls Vault.withdraw()
    2. Deposit some ETH to get a positive balance
    3. Call withdraw() which will trigger the fallback
    4. The fallback re-enters withdraw() before balance is updated
    5. Repeat until the Vault is drained

    ```solidity
    contract Attacker {
        Vault vault;

        fallback() external payable {
            if (address(vault).balance >= 1 ether) {
                vault.withdraw(1 ether);
            }
        }

        function attack() external payable {
            vault.deposit{value: msg.value}();
            vault.withdraw(1 ether);
        }
    }
    ```

    recommendation: |
    Apply the checks-effects-interactions pattern by updating state before external calls:

    ```solidity
    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount);
        balances[msg.sender] -= amount;  // Update state first
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success);
    }
    ```

    Additionally, consider using OpenZeppelin's ReentrancyGuard modifier for extra protection:

    ```solidity
    import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

    contract Vault is ReentrancyGuard {
        function withdraw(uint256 amount) public nonReentrant {
            // ... function logic
        }
    }
    ```

    ```

    ```

5. **Double validation and quality control**
    - Re-examine every true positive for accuracy
    - Verify exploitability claims with technical evidence
    - Ensure impact and confidence ratings match actual exploitability and likelihood
    - Confirm all recommendations are specific and actionable
    - Cross-check that no generic findings were included

</steps>

<tools>
Use these tools for thorough code analysis during validation:
- `wake print storage-layout <file>` for state variable analysis
- `wake print modifiers <file>` for access control validation
- `wake print state-changes <file>` for state manipulation tracing
- `wake print call-graph <file>` for function interaction analysis
</tools>

<validation_practices>
**MANDATORY VALIDATION REQUIREMENTS**:

**Technical Evidence Standard**: Every true positive MUST include:

-   Exact file path, function name, and line numbers
-   Technical explanation of why the code creates vulnerability
-   Concrete attack scenario with step-by-step exploitation
-   Evidence that protective mechanisms are absent or insufficient

**Exploitability Verification**: For each potential issue, prove:

-   Attack vector is technically feasible given the code implementation
-   Economic incentive exists for exploitation
-   No existing mitigations prevent the attack
-   Real-world impact justifies the impact rating

**Impact Classification Guidelines**:

-   **High**: Code that activates the issue will lead to undefined or catastrophic consequences for the system
-   **Medium**: Code that activates the issue will result in consequences of serious substance
-   **Low**: Code that activates the issue will have outcomes on the system that are either recoverable or don't jeopardize its regular functioning
-   **Warning**: The issue represents a potential security concern in the code structure or logic that could become problematic with code modifications
-   **Info**: The issue relates to code quality practices that may affect security (e.g., insufficient logging for critical operations or inconsistent error handling patterns)

**Confidence Classification Guidelines**:

-   **High**: The analysis has identified a pattern that strongly indicates the presence of the issue
-   **Medium**: Evidence suggests the issue exists, but manual verification is recommended
-   **Low**: Potential indicators of the issue have been detected, but there is a significant possibility of false positives

**False Positive Elimination**: Mark as false positive if:

-   Issue relies on theoretical scenarios without concrete exploitation path
-   Existing code protections prevent the attack
-   Required conditions for exploitation are unrealistic
-   Impact assessment was overestimated

**Documentation Standard**: Issue files must be technically detailed:

-   Include relevant code snippets with exact line references
-   Explain underlying technical mechanisms causing vulnerability
-   Provide specific remediation code examples
-   Demonstrate understanding of business logic context
    </validation_practices>

<audit_focus>
Validate issues that stem from this project's unique business logic, implementation details, and protocol-specific attack vectors. The issues should already be pre-filtered to exclude generic copy-paste audit findings.

Every reported vulnerability MUST demonstrate a clear attack vector with specific technical evidence from the analyzed codebase. Before marking any issue as true positive, you must be able to point to exact lines of code, explain the precise technical mechanism that makes it exploitable, and describe the specific attack vector an adversary would use. If you cannot provide concrete codebase evidence and technical reasoning, mark as false positive.
</audit_focus>
