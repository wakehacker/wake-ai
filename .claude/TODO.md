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

- [ ] Debug Mode
  - Implement `--debug` CLI flag
  - Save step prompts/responses to debug folder
  - Force preserve working directories

- [ ] Workflow Base Classes & Mixins
  - Create DetectorWorkflow base class with auto-extraction
  - Add WakeAnalysisMixin for Wake integration
  - Add SecurityAuditMixin for security tools

- [ ] Testing
  - Test dynamic step insertion and resume
  - Test JSON extraction formats
  - Test validation retry logic

- [ ] Documentation
  - Update prompt-writing.md with new examples
  - Document new CLI flags and APIs

- [x] Consolidate workflow enhancement design documents (2025-07-23)
  - Cleaned up .claude/thoughts/ folder
  - Created single wake-ai-enhancements.md file

- [x] Conditional Steps
  - Add `condition` parameter to steps
  - Skip steps when condition evaluates to False