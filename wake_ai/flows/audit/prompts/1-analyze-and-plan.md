# Analyze Codebase and Generate Audit Plan

<task>
Analyze the project and create an initial audit plan
</task>

<context>
Scope: {{scope_files}}
Context: {{context_docs}}
Focus: {{focus_areas}}
</context>

<working_dir>
You have access to the whole codebase, but have assigned a working directory to work in `{{working_dir}}`.
</working_dir>

<steps>

1. **Search and understand the codebase**
   - If scope is provided in arguments, focus exclusively on those files
   - Otherwise, identify core contracsts (main business logic, not libraries/interfaces)
   - Read key files to understand architecture and relationships

2. **Generate codebase overview** (`{{working_dir}}/overview.md`)
   Structure:
   ```markdown
   # Codebase Overview

   ## Architecture
   - High-level system design and contract interactions
   - Data flow between components
   - Access control

   ## Key Components
   ### ContractName
   - Purpose: [specific functionality]
   - Key functions: [list critical functions]
   - Dependencies: [other contracts it interacts with]

   ## Actors
   - Actor Name: [permissions and interactions]
   ```

3. **Create vulnerability checklist** (`{{working_dir}}/plan.yaml`)
   - Split the plan by contracts
   - For each contract, create a list of issues to check for
   - For each issue, add the following fields:
     - title: the title of the issue
     - status: `pending`, as the issue will be validated later by another agent
     - location: the location of the issue
     - description: the description of the issue
     - impact: the impact of the issue
     - confidence: the confidence in the issue
   - Follow the structure below:
   Structure:
   ```yaml
   contracts:
     - name: ContractA
       issues:
         - title: Reentrancy vulnerability
           status: pending
           location:
             lines: "45-52"
             function: withdraw
           description: Function allows reentrant call before state update
           impact: high | medium | low | info | warning
           confidence: high | medium | low
         - title: Reentrancy vulnerability
           status: pending
           location:
             lines: "45-52"
             function: mint
           description: Function allows minting tokens without proper validation
           impact: high | medium | low | info | warning
           confidence: high | medium | low

     - name: ContractB
       issues:
         - title: Unchecked return value
           status: pending
           location:
             lines: "88"
             function: transferTokens
           description: ERC20 transfer return value not checked
           impact: high | medium | low | info | warning
           confidence: high | medium | low
   ```

</steps>

<tools>
Consider using the following tools when analyzing the codebase and working on the plan:
- `wake print lsp-public-functions <file>` to get the list of public functions in a file
- `wake print storage-layout <file>` to get the storage layout of contracts
- `wake print modifiers <file>` to get modifiers and their usage
- `wake print state-changes <file>` to get state changes performed by a function/modifier and subsequent calls
</tools>

<audit_focus>
Focus on project-specific vulnerabilities based on the actual code patterns you observe. Examples:
- State variable manipulation vulnerabilities in specific functions
- Access control issues in identified admin functions
- Reentrancy in functions that make external calls (consider if the call is to a trusted contract)
- Integer overflow/underflow in mathematical operations (only in `unchecked` blocks or older solidity versions)
- Business logic flaws specific to the protocol's design
- Upgradability issues (unprotected initialize functions)
- Logic errors and arithmetic issues
- Standars violations against existing EIPs
- Frontrunning, replay attacks or griefing
- Gas optimization, Missing or incorrect logging, etc.

Do not focus on issues such as:
- Generic copy-paste audit findings that apply to any smart contract (e.g., "use SafeMath", "add input validation", "check for reentrancy") without identifying specific vulnerable code paths in this codebase
- Development practices and operational security recommendations (e.g., "use specific compiler version", "add comprehensive test coverage", "consider multi-signature wallet") that are not code vulnerabilities
- Intentional design choices presented as security flaws (e.g., role centralization where admin controls are part of the protocol design, "add input validation" for zero addresses when zero might be valid)

Focus exclusively on vulnerabilities that stem from this project's unique business logic, implementation details, and protocol-specific attack vectors. For example: "The `calculateReward()` function in RewardPool.sol line 45 allows users to claim rewards multiple times in the same block because `lastClaimBlock[user]` is updated after the external call to `token.transfer()`, enabling reentrancy to drain the reward pool" - this demonstrates a concrete vulnerability specific to this codebase's reward mechanism implementation.

**CRITICAL**:
Every reported vulnerability MUST demonstrate a clear attack vector with specific technical evidence from the analyzed codebase. Do NOT provide generic security suggestions like "check for reentrancy" without precise file locations, function names, and technical reasoning explaining why that specific code implementation creates an exploitable vulnerability. Before reporting any issue, you must be able to point to exact lines of code, explain the precise technical mechanism that makes it exploitable, and describe the specific attack vector an adversary would use. If you cannot provide concrete codebase evidence and technical reasoning, do not report the issue.
</audit_focus>