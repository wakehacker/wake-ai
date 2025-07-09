# Run Static Analysis

Execute static analysis on the codebase and integrate findings into the audit plan.

## Steps:

1. **Run Wake static analyzer**
   ```bash
   wake detect
   ```

2. **Parse and organize results**
   - Group findings by contract
   - Sort by severity (Critical → High → Medium → Low → Informational)
   - Filter out false positives from libraries/test files if not in scope

3. **Create static analysis report** (`audit/static_analysis.md`)
   Structure:
   ```markdown
   # Static Analysis Results

   ## Summary
   - Total findings: X
   - Critical: X, High: X, Medium: X, Low: X, Info: X

   ## Findings by Contract

   ### [ContractName.sol]

   #### [SEVERITY] Finding Title
   - **Detector**: [detector-name]
   - **Location**: Line X-Y
   - **Description**: [What the detector found]
   - **Code**:
   ```solidity
   [relevant code snippet]
   ```

   ### [NextContract.sol]
   ...
   ```

4. **Update audit plan**
   - If `audit/plan.md` exists, append new items from static analysis
   - If not, create new plan following the structure from command 1
   - For each static analysis finding, add to the relevant contract section:
   ```markdown
   #### X. [Finding from Static Analysis]
   - [ ] Status: Pending (SA)
   - Location: Line X-Y
   - Description: [Static analyzer description]
   - Severity: [As reported by analyzer]
   - Source: Wake detector [detector-name]
   ```

5. **Deduplicate**
   - If a static analysis finding overlaps with an existing manual item, merge them
   - Keep the more specific description
   - Note both manual identification and SA confirmation