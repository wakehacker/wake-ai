Please analyse the project and perform an audit (manual) of the codebase: $ARGUMENTS
If an audit scope is provided, focus on the scope. Otherwise choose relevant core files to audit.

Follow these steps:
1. Search the codebase for relevant files (include all files from the scope, if provided).
2. Understand the codebase.
3. Create an (available) output folder for the audit results (e.g. `audit/`).
4. Create a summary of the analysed codebase for future reference. Include architecture overview, quick description of key components (contracts) and their relationships, and potential actors in the system. Only include relevant information, stay consice and to the point. Output results in `audit/overview.md`.
5. Create a checklist (plan) of potential vulnerabilities and attack vectors to check for in a manual review. Think of the relevant issues based on the current codebase. Output results in `audit/plan.md`.
6. Run `wake detect` command to run the static analysis on the codebase. Parse the static analysis results (filter, group, sort, etc. if needed) and output results in `audit/static_analysis.md`.
7. Update the manual review plan  (`audit/plan.md`) according to static analysis results.
8. Based on your now indepth understanding of the codebase, ultrathink about possible high level attack vectors and add them to the manual review plan (`audit/plan.md`).
9. Proceed to the manual review of the codebase. Follow the plan (`audit/plan.md`) sequentially to find vulnerabilities. Audit the checklist items one by one. Keep strong emphasis on flagging only true positives. If an issue is found, doublecheck its validity by reading the codebase again. After checking each issue, update the plan (`audit/plan.md`) to reflect the progress (e.g. add a checkmark to the item reflecting its status, true/false positive, if it is really required add a comment). If you are not sure about the validity of the issue, add a comment to the item. If you determine that the issue is valid, create a file with the issue description under the `audit/issues/` folder. Add a link to the issue in the plan (`audit/plan.md`).
10. After the manual review is done, go over all issues in `audit/issues/` and check again if they are valid. If an issue is found to be invalid, remove the file and update its status in the plan (`audit/plan.md`).
11. After the manual review is done and all issues are checked, create a summary of the manual review results based on the issues found. Output results in `audit/summary.md`.