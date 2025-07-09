# Audit-Focused Design Decisions

## Why This Approach Makes Sense

### 1. **Market Reality**
- Existing tools (Slither, Mythril, etc.) are complex to use
- SaaS audit tools are expensive and opaque
- Users want: "scan my code, find vulnerabilities"
- Speed to market matters more than flexibility right now

### 2. **Fixed Workflows Are Actually Better For Audits**
- Security audits NEED consistency and repeatability
- Junior auditors shouldn't be designing workflows
- Standardized process = standardized quality
- Easier to train and onboard users

### 3. **Context Injection Points**
The key insight is that you need flexibility in the INPUT, not the PROCESS:
- Scope files (what to audit)
- Context docs (specs, previous audits)
- Focus areas (specific vulnerabilities, ERCs)
- Model selection (speed vs thoroughness)

### 4. **Architecture That Scales**
```
wake ai --scope contracts/Token.sol --focus reentrancy   # Today: security audit
wake ai --flow gas-optimization --scope contracts/       # Tomorrow: gas audit
wake ai --flow documentation --scope src/                # Future: auto-docs
```

## Implementation Strategy

### Phase 1: MVP (What You Ship Now)
- Single command: `wake ai`
- Defaults to security audit workflow
- Fixed 4-step process from your markdown files
- Simple options: scope, context, focus

### Phase 2: Expansion (3-6 months)
- Add `--flow` option with more workflows:
  - `gas-optimization`
  - `access-control-review`
  - `upgrade-safety`
- Each workflow is still fixed/hardcoded

### Phase 3: Platform (6-12 months)
- Workflow marketplace?
- Custom workflow builder (GUI)?
- Integration with CI/CD

## Key Technical Decisions

### 1. **Prompts as Data, Not Code**
Your markdown files become the source of truth:
```
wake/ai/prompts/
├── security-audit/
│   ├── 1-analyze.md
│   ├── 2-static.md
│   ├── 3-manual.md
│   └── 4-summary.md
├── gas-optimization/
│   ├── 1-profile.md
│   └── 2-optimize.md
└── ...
```

### 2. **State Management Between Steps**
Critical for multi-step workflows:
- Step 1 creates vulnerability checklist
- Step 2 marks items found by static analysis
- Step 3 investigates remaining items
- Step 4 summarizes everything

### 3. **Output Structure**
Standardized output is key for tooling:
```
audit/
├── overview.md
├── plan.md
├── static_analysis.md
├── issues/
│   ├── HIGH-001-reentrancy.adoc
│   ├── MED-001-access-control.adoc
│   └── ...
└── executive_summary.md
```

### 4. **Error Recovery**
With fixed workflows, you can be smarter about errors:
- If static analysis fails, skip to manual review
- If a step times out, auto-resume
- Clear error messages for common issues

## Why Keep The Modular Architecture?

Even with fixed workflows, the modular design helps:

1. **Testing** - Test each step independently
2. **Monitoring** - Track success rates per step
3. **Optimization** - Improve individual steps without touching others
4. **Maintenance** - Update prompts without changing code

## Competitive Advantages

Your approach has several advantages over existing tools:

1. **Transparent Process** - Users see exactly what's happening
2. **Customizable Context** - Unlike SaaS, users control the input
3. **Local Execution** - No code leaves the user's machine
4. **Wake Integration** - Leverages Wake's powerful static analysis
5. **Iterative Improvement** - Can update prompts based on user feedback

## Next Steps

1. **Simplify the CLI** - One command, clear options
2. **Test the Workflow** - Run on known vulnerable contracts
3. **Optimize Prompts** - Based on real results
4. **Add Telemetry** - Understand what users need
5. **Build Community** - Share audit reports, gather feedback

This approach is pragmatic and will get you to market faster while keeping doors open for future expansion.