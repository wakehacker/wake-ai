# Analyze Codebase and Generate Audit Plan

Analyze the project and create an initial audit plan: $ARGUMENTS

## Steps:

1. **Search and understand the codebase**
   - If scope is provided in arguments, focus exclusively on those files
   - Otherwise, identify core contracts (main business logic, not libraries/interfaces)
   - Read key files to understand architecture and relationships

2. **Create output directory**
   - Create `audit/` folder if it doesn't exist

3. **Generate codebase overview** (`audit/overview.md`)
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
   - Dependencies: [other contracts it interacts with]

   ## Actors
   - Actor Name: [permissions and interactions]
   ```

4. **Create vulnerability checklist** (`audit/plan.md`)
   Structure:
   ```markdown
   # Audit Plan

   ## Scope
   [List files being audited]

   ## Vulnerability Checklist

   ### [ContractName.sol]

   #### 1. [Specific Issue Name]
   - [ ] Status: Pending
   - Location: Line X-Y, function `functionName()`
   - Description: [Specific concern about this code]
   - Severity: [High/Medium/Low]

   #### 2. [Another Issue]
   ...
   ```

Focus on project-specific vulnerabilities based on the actual code patterns you observe. Examples:
- State variable manipulation vulnerabilities in specific functions
- Access control issues in identified admin functions
- Reentrancy in functions that make external calls
- Integer overflow/underflow in mathematical operations
- Business logic flaws specific to the protocol's design

Do NOT include generic items like "Check for reentrancy" without specific locations and context.