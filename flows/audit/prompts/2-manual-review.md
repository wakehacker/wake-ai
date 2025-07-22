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
   - Consider updating the `severity` field based on the validation results if the issue is not a false positive
   ```yaml
   contracts:
     - name: ContractA
       issues:
         - title: Reentrancy vulnerability in withdraw function
           status: true_positive  # pending -> true_positive/false_positive
           location:
             file: src/Vault.sol
             lines: "45-52"
             function: withdraw
           description: Function calls external contract before updating user balance, enabling reentrancy
           severity: high  # info/warning/low/medium/high
           comment: "Confirmed: balance updated after external call on line 48, user.balance check on line 46 can be bypassed"
   ```
4. **Create detailed issue files** (only for true positives)
   - Create `{{working_dir}}/issues/` directory if needed
   - File naming: `[severity]-[contract]-[brief-description].adoc`
   - Each issue file must contain:
     - Exact vulnerable code location with line numbers
     - Technical explanation of the vulnerability mechanism
     - Step-by-step exploitation scenario
     - Concrete proof-of-concept where possible
     - Specific remediation recommendations with code examples
   - Follow this structure:
   ```adoc
   {% set title      = "Finding" %}
   {% set id         = 'finding-id' %}
   {% set severity   = 'Info' %} {#  Critical | High | Medium | Low | Warning | Info  #}
   {% set target     = 'Contract.sol' %} {#  File, files or scope  #}
   {% set type       = 'Code quality' %} {#  Data validation | Code quality | Logic error | Standards violation | Gas optimization | Logging | Trust model | Arithmetics | Access control | Unused code | Storage clashes | Denial of service | Front-running | Replay attack | Reentrancy | Function visibility | Overflow/underflow | Configuration | Reinitialization | Griefing  #}

   {% block description %}
   - Description of the finding.
   - If needed, include a code excerpt from the source code.
   [source, solidity, linenums]
   ----
   function foo() public {
       // ...
   }
   ----
   {% endblock %}

   {% block exploit %}
   - If needed, include an exploit scenario.
   {% endblock %}

   {% block recommendation %}
   Remove the ...
   {% endblock %}
   ```

5. **Double validation and quality control**
   - Re-examine every true positive for accuracy
   - Verify exploitability claims with technical evidence
   - Ensure severity ratings match actual impact and likelihood
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
- Exact file path, function name, and line numbers
- Technical explanation of why the code creates vulnerability
- Concrete attack scenario with step-by-step exploitation
- Evidence that protective mechanisms are absent or insufficient

**Exploitability Verification**: For each potential issue, prove:
- Attack vector is technically feasible given the code implementation
- Economic incentive exists for exploitation
- No existing mitigations prevent the attack
- Real-world impact justifies the severity rating

**Severity Classification Guidelines**:
- **High**: Loss of funds, access control exploits, protocol-breaking vulnerabilities
- **Medium**: Exploitable issues with limited financial impact, partial accounting errors
- **Low**: Minor accounting issues, edge cases that don't lead to severe consequences
- **Warning**: Non-exploitable issues that could cause problems under specific conditions
- **Info**: Code quality observations, best practice recommendations (rarely used in security audits)

**False Positive Elimination**: Mark as false positive if:
- Issue relies on theoretical scenarios without concrete exploitation path
- Existing code protections prevent the attack
- Required conditions for exploitation are unrealistic
- Impact assessment was overestimated

**Documentation Standard**: Issue files must be technically detailed:
- Include relevant code snippets with exact line references
- Explain underlying technical mechanisms causing vulnerability
- Provide specific remediation code examples
- Demonstrate understanding of business logic context
</validation_practices>

<audit_focus>
Validate issues that stem from this project's unique business logic, implementation details, and protocol-specific attack vectors. The issues should already be pre-filtered to exclude generic copy-paste audit findings.

Every reported vulnerability MUST demonstrate a clear attack vector with specific technical evidence from the analyzed codebase. Before marking any issue as true positive, you must be able to point to exact lines of code, explain the precise technical mechanism that makes it exploitable, and describe the specific attack vector an adversary would use. If you cannot provide concrete codebase evidence and technical reasoning, mark as false positive.
</audit_focus>