# Analyze Codebase and Generate Audit Plan

Analyze the project and create an initial audit plan: $ARGUMENTS

## Steps:

1. **Search and understand the codebase**
   - If scope is provided in arguments, focus exclusively on those files
   - Otherwise, identify core contracts (main business logic, not libraries/interfaces)
   - Read key files to understand architecture and relationships

2. **Generate codebase overview** (`audit/overview.md`)
   Structure:
   ```markdown
   # Codebase Overview

   ## Architecture
   - High-level system design and contract interactions
   - Data flow between components

   ## Key Components
   ### ContractName
   - Purpose: [specific functionality]
   - Key functions: [list critical functions]
        - Utilize the `wake print lsp-public-functions <file>` command to get the list of public functions in a file
   - Dependencies: [other contracts it interacts with]

   ## Actors
   - Actor Name: [permissions and interactions]
   ```

3. **Create vulnerability checklist** (`audit/plan.md`)
   Structure:
   ```markdown
   # Vulnerability Checklist

   ## [ContractName]

   ### 1. [Specific Issue Name]
   - Utilize the `wake print lsp-public-functions <file>` command to get the list of public functions in a file
   - [ ] Status: Pending
   - Location: Line X-Y, function `functionName()`
   - Description: [Specific concern about this code]
   - Severity: [High/Medium/Low]

   ### 2. [Another Issue]
   ...
   ```

Focus on project-specific vulnerabilities based on the actual code patterns you observe. Examples:
- State variable manipulation vulnerabilities in specific functions
- Access control issues in identified admin functions
- Reentrancy in functions that make external calls (consider if the call is to a trusted contract)
- Integer overflow/underflow in mathematical operations (only in `unchecked` blocks or older solidity versions)
- Business logic flaws specific to the protocol's design
- Upgradability issues (unprotected initialize functions)

Focus on data validation, code quality, logic errors, standards violations, gas optimization, logging, trust model, arithmetics, access control, unused code, storage clashes, denial of service, front-running, replay attack, reentrancy, function visibility, overflow/underflow, configuration, reinitialization, griefing etc.
- Code quality
- Logic error
- Standards violation
- Gas optimization
- Logging
- Trust model
- Arithmetics
- Access control
- Unused code
- Storage clashes
- Denial of service