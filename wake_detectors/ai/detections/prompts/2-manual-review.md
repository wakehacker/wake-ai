# Execute Manual Review

<task>
Perform systematic manual review of the codebase following the audit plan and generate detector-compatible findings
</task>

<context>
Plan: `{working_dir}/plan.yaml`
</context>

<working_dir>
Work in the assigned directory `{working_dir}` where the audit plan and results will be stored.
</working_dir>

<steps>

1. **Load and validate audit plan**
   - Read `{working_dir}/plan.yaml`
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

3. **Create findings directory**
   - Create `{working_dir}/findings/` directory for validated issues
   - Only create findings for TRUE POSITIVE issues

4. **Generate detector findings** (only for true positives)
   - For each validated issue, create a YAML file: `{working_dir}/findings/finding-001.yaml`, `finding-002.yaml`, etc.
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

5. **Determine impact and confidence levels**
   - **Impact classification**:
     - `high`: Direct loss of funds, complete access control bypass, protocol-breaking bugs
     - `medium`: Indirect financial loss, partial control bypass, griefing attacks
     - `low`: Minor issues with limited impact, edge cases
     - `warning`: Best practice violations, potential future issues
     - `info`: Code quality observations, gas optimizations
   
   - **Confidence classification**:
     - `high`: Clear vulnerability with proven exploit path
     - `medium`: Likely issue but requires specific conditions
     - `low`: Possible issue but uncertain or very specific edge case

6. **Quality control for findings**
   - Ensure each finding has exact line numbers from actual code
   - Message should be concise but descriptive (aim for 10-20 words)
   - Verify contract names match exactly as defined in the code
   - Double-check impact/confidence ratings are justified
   - Remove any findings that cannot be precisely located in code

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

**Technical Evidence Standard**: Every finding MUST include:
- Exact contract name and line numbers from the actual code
- Clear, concise vulnerability message for detector output
- Appropriate impact and confidence ratings based on exploitability
- Subdetections for multi-step vulnerabilities (optional)

**Finding Creation Rules**:
- Only create YAML files for TRUE POSITIVE vulnerabilities
- Each finding must reference actual code locations
- Contract names must match exactly as defined in source files
- Line numbers must correspond to the actual vulnerability location
- Messages should be brief but descriptive (10-20 words ideal)

**False Positive Elimination**: Do NOT create findings for:
- Issues that rely on unrealistic assumptions
- Vulnerabilities already mitigated by existing code
- Generic audit findings not specific to this codebase
- Issues without clear exploit paths

**Quality Requirements**:
- Every finding must be traceable to specific code
- Impact/confidence must align with actual exploitability
- Subdetections should highlight the attack flow
- No duplicate findings for the same issue
</validation_practices>

<audit_focus>
Validate issues that stem from this project's unique business logic, implementation details, and protocol-specific attack vectors. The issues should already be pre-filtered to exclude generic copy-paste audit findings.

Every reported vulnerability MUST demonstrate a clear attack vector with specific technical evidence from the analyzed codebase. Before marking any issue as true positive, you must be able to point to exact lines of code, explain the precise technical mechanism that makes it exploitable, and describe the specific attack vector an adversary would use. If you cannot provide concrete codebase evidence and technical reasoning, mark as false positive.
</audit_focus>