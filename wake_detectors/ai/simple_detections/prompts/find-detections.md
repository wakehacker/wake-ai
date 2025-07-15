# Find Security Vulnerabilities

<task>
Analyze the smart contract codebase to identify specific security vulnerabilities and generate detector findings
</task>

<context>
Scope: {scope_files}
Context: {context_docs}
Focus: {focus_areas}
</context>

<working_dir>
Work in the assigned directory `{working_dir}` where you will save your findings.
</working_dir>

<steps>

1. **Analyze the codebase**
   - If scope is provided, focus exclusively on those files
   - Otherwise, identify and examine the main smart contracts (skip libraries and interfaces unless they have issues)
   - Look for common vulnerability patterns and project-specific security issues

2. **Identify vulnerabilities**
   Focus on finding these types of issues:
   - **Access control**: Missing or incorrect permission checks
   - **Reentrancy**: External calls before state updates
   - **Logic errors**: Incorrect business logic, calculation errors
   - **Input validation**: Missing checks on user inputs
   - **State management**: Incorrect state transitions
   - **Economic attacks**: MEV, sandwich attacks, price manipulation
   - **Integration issues**: Incorrect use of external protocols
   - **Upgrade safety**: Issues with proxy patterns or upgrades

3. **Create findings directory and generate YAML files**
   - Create `{working_dir}/findings/` directory
   - For each vulnerability found, create a YAML file: `{working_dir}/findings/finding-001.yaml`, `finding-002.yaml`, etc.
   - Start index from 001 and increment sequentially
   - Each finding MUST follow this exact structure:

   ```yaml
   contract_name: "ContractName"  # Just the contract name, not the file path
   start_line: 45  # Integer line number where issue starts
   end_line: 52    # Optional: end line (omit if same as start_line)
   message: "Brief vulnerability description for detector output"
   impact: "high"  # One of: info, warning, low, medium, high
   confidence: "high"  # One of: low, medium, high
   subdetections:  # Optional: related code locations
     - contract_name: "ContractName"
       start_line: 48
       message: "External call performed here"
     - contract_name: "ContractName"
       start_line: 50
       message: "State update after external call"
   ```

4. **Quality requirements for findings**
   - Only create findings for TRUE POSITIVE vulnerabilities
   - Each finding must reference exact line numbers from actual code
   - Contract names must match exactly as defined in source files
   - Messages should be concise but descriptive (10-20 words ideal)
   - Impact and confidence must align with actual exploitability

</steps>

<impact_guidelines>
**Impact Classification**:
- `high`: Direct loss of funds, complete access control bypass, protocol-breaking bugs
- `medium`: Indirect financial loss, partial control bypass, griefing attacks  
- `low`: Minor issues with limited impact, edge cases
- `warning`: Best practice violations, potential future issues
- `info`: Code quality observations, gas optimizations

**Confidence Classification**:
- `high`: Clear vulnerability with proven exploit path
- `medium`: Likely issue but requires specific conditions
- `low`: Possible issue but uncertain or very specific edge case
</impact_guidelines>

<validation_requirements>
**Before creating any finding**:
- Verify the vulnerability exists at the exact line numbers
- Ensure contract names match source code exactly
- Confirm the issue is exploitable in the current codebase
- Check that no existing mitigations prevent the attack
- Avoid generic findings - focus on code-specific issues

**Do NOT create findings for**:
- Issues that rely on unrealistic assumptions
- Vulnerabilities already mitigated by existing code
- Generic audit findings not specific to this codebase
- Issues without clear exploit paths
</validation_requirements>