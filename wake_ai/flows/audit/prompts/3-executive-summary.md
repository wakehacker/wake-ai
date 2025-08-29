# Generate Executive Summary

<task>
Create a comprehensive executive summary of the audit findings based on validated results
</task>

<context>
Scope: {{scope_files}}
Context: {{context_docs}}
Focus: {{focus_areas}}
Overview: `{{working_dir}}/overview.md`
Validated Plan: `{{working_dir}}/plan.yaml`
Issues Directory: `{{working_dir}}/issues/`
</context>

<working_dir>
Work in the assigned directory `{{working_dir}}` where all audit artifacts are stored.
</working_dir>

<steps>

1. **Gather validated audit results**
   - Read `{{working_dir}}/overview.md` for codebase architecture understanding
   - Read `{{working_dir}}/plan.yaml` for complete validation results and status
   - Read all issue files in `{{working_dir}}/issues/` for detailed true positive findings
   - Extract impact and confidence counts and key technical details from validated issues

2. **Create comprehensive executive summary** (`{{working_dir}}/executive-summary.md`)
   Structure:
   ```markdown
   # Executive Summary

   ## Audit Overview
   - **Scope**: [List of audited contracts from scope]
   - **Total Issues Identified**: [Count from validated plan]
   - Include a report overview summary of the audit, including the scope, the total issues identified, and the key findings.
   - Consider the security posture of the codebase, and the key findings.
   - Talk about an overall assessment of the codebase security.

   ## Summary of Findings

   | Impact   | High Confidence | Medium Confidence | Low Confidence | Total |
   |----------|----------------|-------------------|----------------|-------|
   | High     | X              | X                 | X              | X     |
   | Medium   | X              | X                 | X              | X     |
   | Low      | X              | X                 | X              | X     |
   | Warning  | X              | X                 | X              | X     |
   | Info     | X              | X                 | X              | X     |
   | **Total**| **X**          | **X**             | **X**          | **X** |

   ## Key Technical Findings
   - Short description of the most important findings
   ```

3. **Technical accuracy validation**
   - Cross-reference all findings with issue files to ensure accuracy
   - Verify impact and confidence classifications match validation results
   - Confirm technical details and locations are precise
   - Ensure recommendations are specific and actionable

4. **Professional reporting standards**
   - Use precise technical language with specific code references
   - Focus on concrete findings rather than theoretical risks
   - Maintain clear impact rationale based on exploitability
   - Be technical and not speculative.
   - Report should be consice and to the point, without extra verbosity.
</steps>

<reporting_standards>
**Professional Quality**: The summary must demonstrate:
- Deep understanding of the project's technical architecture
- Clear communication of complex technical issues
- Balanced assessment of both risks and strengths
- Evidence-based conclusions from thorough validation
</reporting_standards>