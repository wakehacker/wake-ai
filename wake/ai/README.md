# Wake AI - Smart Contract Security Auditing

## Quick Start

```bash
# Audit entire codebase
wake ai

# Audit specific files
wake ai -s contracts/Token.sol -s contracts/Vault.sol

# Add context and focus areas
wake ai -c docs/whitepaper.pdf -f reentrancy -f "access control"

# Resume interrupted audit
wake ai --resume
```

## How It Works

Wake AI runs a standardized 4-step security audit process:

1. **Analysis & Planning** - Understands your codebase and creates a vulnerability checklist
2. **Static Analysis** - Runs Wake's detectors and integrates findings
3. **Manual Review** - Deep-dives into potential vulnerabilities
4. **Executive Summary** - Produces professional audit report

## Output Structure

```
audit/
├── overview.md          # Codebase architecture analysis
├── plan.md             # Vulnerability checklist
├── static_analysis.md  # Wake detector results
├── issues/            # Detailed vulnerability reports
│   ├── HIGH-001-reentrancy.adoc
│   ├── MED-001-access-control.adoc
│   └── ...
└── executive_summary.md # Professional summary
```

## Options

- `--scope/-s`: Limit audit to specific files/directories
- `--context/-c`: Provide additional documentation
- `--focus/-f`: Focus on specific vulnerability types or ERCs
- `--model/-m`: Choose Claude model (default: sonnet)
- `--output/-o`: Output directory (default: audit/)
- `--resume`: Continue from previous session

## Best Practices

1. **Provide Context**: Include specs, docs, and previous audits with `-c`
2. **Set Scope**: For large codebases, focus on critical contracts with `-s`
3. **Specify Focus**: If you suspect specific issues, use `-f` to prioritize
4. **Review Output**: Always manually verify AI findings before reporting

## Common Focus Areas

- `reentrancy`: Check for reentrancy vulnerabilities
- `access-control`: Review permission systems
- `integer-overflow`: Despite Solidity 0.8+, check for edge cases
- `frontrunning`: MEV and transaction ordering issues
- `gas-optimization`: Identify gas inefficiencies
- `ERC20`, `ERC721`, `ERC1155`: Standard compliance checks

## Future Workflows

Currently defaults to security audit. Future versions will support:
- `--flow gas-optimization`: Gas usage analysis
- `--flow documentation`: Auto-generate documentation
- `--flow test-generation`: Create comprehensive test suites

## Requirements

- Claude Code CLI must be installed
- Wake must be properly configured
- Python 3.8+

## Troubleshooting

**"Claude Code CLI not found"**
- Install from: https://github.com/anthropics/claude-code

**"Audit interrupted"**
- Use `wake ai --resume` to continue

**"Large codebase timeout"**
- Use `--scope` to limit files
- Consider using `--model opus` for complex codebases