# Generate Executive Summary

Create a comprehensive executive summary of the audit findings.

## Steps:

1. **Gather information**
   - Read `audit/overview.md` for codebase understanding
   - Read `audit/plan.md` for all reviewed items
   - Read all files in `audit/issues/` for true positive findings

2. **Create executive summary** (`audit/executive-summary.md`)
   Structure:
   ```markdown
   # Executive Summary

   ## Audit Overview
   - **Audit Date**: [Date]
   - **Auditor**: [Name]
   - **Scope**: [List of audited contracts]
   - **Commit Hash**: [If available]

   ## Summary of Findings

   | Severity | Count |
   |----------|-------|
   | High     | X     |
   | Medium   | X     |
   | Low      | X     |
   | Info     | X     |
   | **Total**| **X** |

   ## Key Findings

   ### High Severity
   1. **[Issue Title]** ([Contract])
      - Brief description of the issue and its impact
      - Risk: [Specific risk to the protocol]

   ### Medium Severity
   [Similar format]

   ### Low Severity
   [Similar format]

   ## Audit Methodology
   - Manual code review
   - Static analysis using Wake
   - [Any other methods used]

   ## Recommendations
   1. **Immediate Actions** (High severity)
      - [Specific actions for critical issues]

   2. **Short-term Improvements** (Medium severity)
      - [Actions for medium priority issues]

   3. **Long-term Considerations** (Low severity)
      - [Suggestions for code quality and minor issues]

   ## Conclusion
   [Overall assessment of the codebase security posture]
   [Key strengths observed]
   [Main areas of concern]
   ```

3. **Cross-reference**
   - Ensure all issues from `audit/issues/` are included
   - Verify severity counts match actual findings
   - Check that recommendations align with found issues

4. **Professional tone**
   - Use clear, technical language
   - Avoid speculation beyond findings
   - Focus on actionable insights