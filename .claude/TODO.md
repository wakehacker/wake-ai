## Todo

- [x] Dynamic Steps Implementation (2025-07-23)
  - Added `add_dynamic_steps()` method to generate steps at runtime
  - Implemented step factory pattern with generator functions
  - Added `after_step` parameter to both `add_step()` and `add_dynamic_steps()`
  - Dynamic steps are inserted after execution of trigger step
  - Created example workflow demonstrating dynamic step generation

- [x] Extraction Steps Implementation (2025-07-23)
  - Added `add_extraction_step()` for structured data extraction
  - Created JSON extraction utility and schema validators
  - Integrated Pydantic models for type-safe parsing
  - Extraction parsing happens in execute() for proper retry support
  - No hasattr checks - using proper instance variables

- [ ] Step Execution Controls
  - Add `max_turns` parameter to limit Claude interactions
  - Add `timeout` parameter for time-based limits
  - Pass these to ClaudeCodeSession

- [ ] Test resuming of workflows

- [ ] Consider Workflow Base Classes & Mixins
  - Add WakeAnalysisMixin for Wake integration
  - Add SecurityAuditMixin for security tools

- [x] Consolidate workflow enhancement design documents (2025-07-23)
  - Cleaned up .claude/thoughts/ folder
  - Created single wake-ai-enhancements.md file

- [x] Conditional Steps
  - Add `condition` parameter to steps
  - Skip steps when condition evaluates to False

- [ ] Implement custom permissions MCP for more granular tool permissions
  - Allow writing/editing only within working_dir by default
  - See https://docs.anthropic.com/en/docs/claude-code/sdk#custom-permission-prompt-tool

- [ ] Simplify workflow discovery in CLI
  - Do not rely on importing workflows in cli.py