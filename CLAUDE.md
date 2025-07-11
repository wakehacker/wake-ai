# AI Integration Architecture

## Dual Execution Paths
- **CLI**: `wake ai -f audit` - Standalone AI workflow execution
- **Detector**: `wake detect ai-audit` - AI workflow as Wake detector

## Key Design Decisions
1. **Prompts Location**: Keep in `wake/ai/prompts/` (not detector directory)
2. **Session Management**: Workflows should create their own ClaudeCodeSession
3. **No DetectorResultConverter**: Direct result handling in detector
4. **Shared Workflows**: Both paths use same `AuditWorkflow` class
5. **Temporary Dual Support**: Will consolidate to single approach based on usage

## Implementation Status
- ✅ AI module with workflows, runner, and CLI
- ✅ Detector wrapper for AI workflows
- ✅ Cost-limited execution with `query_with_cost()`
- ✅ Comprehensive logging throughout
- 🔄 Prompts currently duplicated (detector has copies)

## Next Steps
1. Make `AuditWorkflow` accept `prompts_dir` parameter
2. Remove `DetectorAuditWorkflow` duplicate
3. Simplify detector to use `run_ai_workflow()`
4. Move CLI validation to session init only
5. Add custom exceptions for better error handling

## Technical Details
- `ClaudeCodeSession` validates CLI on init using `validate_claude_cli()` from utils
- `query_with_cost()` implements cost-limited execution with session resumption
- Workflow state persists to disk for resume capability
- Context keys filter what data reaches prompt templates

## Working Directory Feature
Each AI workflow session now has a dedicated working directory:
- **Default Path**: `.wake/ai/<session-id>/`
- **Session ID Format**: `YYYYMMDD_HHMMSS_random` (e.g., `20250111_152030_abc123`)
- **Purpose**: Provides isolated workspace for AI to create files, store analysis results, etc.
- **Context Variable**: Available in prompts as `{working_dir}`. Results from previous steps are saved into `{step_name}_output` variables.
- **Directory Structure**:
  ```
  .wake/ai/<session-id>/
  ├── results/     # Output files from the audit
  └── state/       # Workflow state for resume capability
  ```

### Implementation Notes
- Session ID is generated at workflow initialization (not from Claude's session)
- Working directory is created automatically and passed to ClaudeCodeSession
- The path is displayed in console output for transparency
- AI can use this directory for temporary files, analysis artifacts, etc.
- Each workflow step has access to `working_dir` in its context

### Why Not Use Claude's Session ID?
We generate our own session ID instead of using Claude's for the following reasons:
1. **Timing Issue**: Claude's session ID is only available after the first API call returns
2. **Directory Creation**: We need the working directory path before starting any queries
3. **Context Availability**: The working directory must be in the initial context for all steps
4. **Workflow Design**: The workflow needs to pass the working_dir to ClaudeCodeSession constructor

The workflow execution order is:
1. Create workflow with session ID → generates working directory
2. Add working_dir to initial context
3. Create ClaudeCodeSession with working_dir parameter
4. Execute first query → Claude returns its session ID (too late)

This design ensures the AI has a consistent workspace from the very first prompt.

## State Management
**working_dir**: User-facing workspace for AI-generated files
  - Path: .wake/ai/<session-id>/
  - Available to AI via {working_dir} context variable in prompts
  - Where AI creates analysis results, reports, or temporary files
  - Provides isolated workspace for each workflow session