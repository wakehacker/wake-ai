Please analyse the project and perform an audit (manual) of the codebase: $ARGUMENTS
If an audit scope is provided, focus on the scope. Otherwise choose relevant core files to audit.

Follow these steps:
1. Search the codebase for relevant files (include all files from the scope, if provided).
2. Understand the codebase.
3. Create an (available) output folder for the audit results (e.g. `audit/`).
4. Create a summary of the analysed codebase for future reference. Include architecture overview, quick description of key components (contracts) and their relationships, and potential actors in the system. Only include relevant information, stay consice and to the point. Output results in `audit/overview.md`.
5. Create a checklist (plan) of potential vulnerabilities and attack vectors to check for in a manual review. Think of the relevant issues based on the current codebase. Output results in `audit/plan.md`.
6. Run `wake detect` command to run the static analysis on the codebase. Parse the static analysis results (filter, group, sort, etc. if needed) and output results in `audit/static_analysis.md`.
7. Update the manual review plan according to static analysis results.
8. Ultrathink about possible high level attack vectors and add them to the manual review plan.

Remember to output the results in the `audit/` folder for future reference.