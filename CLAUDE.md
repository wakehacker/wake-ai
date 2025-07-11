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
- `ClaudeCodeSession._check_claude_available()` validates CLI on init
- `query_with_cost()` implements cost-limited execution with session resumption
- Workflow state persists to disk for resume capability
- Context keys filter what data reaches prompt templates