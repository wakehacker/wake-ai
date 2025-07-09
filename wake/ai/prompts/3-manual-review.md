# Execute Manual Review

Perform systematic manual review of the codebase following the audit plan.

## Process:

1. **Load audit plan**
   - Open `audit/plan.md`
   - Work through each item sequentially

2. **For each checklist item:**

   a) **Deep investigation**
      - Navigate to the specified location
      - Read surrounding code for full context
      - Trace data flow and state changes
      - Check all callers and callees
      - Verify against project documentation

   b) **Validation**
      - Construct proof-of-concept if possible
      - Check if issue can actually be exploited
      - Consider all mitigating factors
      - Verify severity assessment

   c) **Update plan status**
      ```markdown
      #### X. [Issue Name]
      - [x] Status: True Positive / False Positive
      - Location: Line X-Y, function `functionName()`
      - Description: [Original description]
      - Severity: [High/Medium/Low]
      - Comment: [Why it's valid/invalid, any additional context]
      ```

   d) **Create issue file** (only for true positives)
      - Create `audit/issues/` directory if it doesn't exist
      - File naming: `[severity]-[contract]-[issue-brief].adoc`
      - Example: `high-CSAccounting-reentrancy-drain.adoc`
      - Use the provided template exactly:

```asciidoc
{% extends 'core/fragments/finding.adoc' %}

{% set title      = "[Descriptive title of the vulnerability]" %}
{% set id         = '[unique-id-matching-filename]' %}

{% set impact     = '[High|Medium|Low|Warning|Info]' %}
{% set likelihood = '[High|Medium|Low|N/A]' %}
{% set target     = '[Contract.sol]' %}
{% set type       = '[Data validation|Code quality|Logic error|Access control|Reentrancy|...]' %}

{% set statuses   = ['Reported'] %}
{% set discoverer = '[Your Name]' %}

{% block description %}
[Detailed technical description of the vulnerability]

[Explanation of why this is an issue]

{{ code('src/path/to/Contract.sol', startLine, endLine, id='listing-1') }}

[Additional context or related code if needed]
{% endblock %}

{% block exploit %}
{{ super() }}

[Step-by-step exploit scenario]
1. Attacker calls function X with parameters Y
2. This causes state change Z
3. Attacker can then...

[Impact description]
{% endblock %}

{% block recommendation %}
[Specific fix recommendation with code example if applicable]

Consider implementing [specific mitigation].
{% endblock %}

{% block update_one %}
{{ super() }}
{% endblock %}
```

   e) **Link in plan**
      - Add link to issue file in the plan item
      - Format: `- Issue: [issues/filename.adoc](issues/filename.adoc)`

3. **Quality control**
   - After all items reviewed, re-read all true positive issues
   - Ensure consistency in severity ratings
   - Verify all issue files are properly formatted
   - Double-check no false positives were marked as true