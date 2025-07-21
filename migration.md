# Wake AI Module Migration Plan

This document outlines the comprehensive plan for separating the Wake AI module into a standalone package.

## Overview

The Wake AI module will be extracted into a standalone Python package called `wake_ai_core` that can be used independently or as a Wake plugin.

## Current Structure Analysis

### Minimal Dependencies
- Only one external dependency: `StrEnum` from `wake.utils`
- Clean abstract base classes (`AIResult`, `AIWorkflow`)
- Self-contained framework with its own exceptions and utilities

### File Inventory
- **Core AI Framework**: 10 Python files in `wake/ai/`
- **AI Workflows**: 12 files in `wake_ai/`
- **AI Detectors**: 23 files in `wake_detectors/ai/`
- **CLI Integration**: 2 files (`wake/cli/ai.py`, `wake/cli/detect.py`)
- **Total**: 57 AI-related files

## Files to KEEP for New Package

### Core Framework (from wake/ai/)
```
wake/ai/__init__.py
wake/ai/detections.py
wake/ai/results.py
wake/ai/runner.py
wake/ai/utils.py
wake/ai/core/__init__.py
wake/ai/core/claude.py
wake/ai/core/exceptions.py
wake/ai/core/flow.py
wake/ai/core/utils.py
```

### Workflows (from wake_ai/)
```
wake_ai/__init__.py
wake_ai/audit/__init__.py
wake_ai/audit/workflow.py
wake_ai/audit/prompts/*.md (4 files)
wake_ai/example/__init__.py
wake_ai/example/workflow.py
wake_ai/test/__init__.py
wake_ai/test/workflow.py
wake_ai/validation_test/__init__.py
wake_ai/validation_test/workflow.py
```

## Files to ADD

### Package Configuration
```
setup.py                    # Package setup
pyproject.toml             # Modern Python packaging
requirements.txt           # Dependencies
README.md                  # Package documentation
LICENSE                    # License file
.gitignore                # Git ignore patterns
```

### New Package Structure
```
wake_ai_core/              # New package name
├── __init__.py           # Package init
├── core/                 # Move wake/ai/core here
├── core/                 # Move wake/ai core files here
├── workflows/            # Move wake_ai workflows here
├── prompts/              # Consolidate all prompts
├── cli.py                # Standalone CLI entry point
├── plugin.py             # Wake plugin interface
└── utils.py              # Include StrEnum copy
```

### Tests Structure
```
tests/
├── __init__.py
├── test_core.py
├── test_workflows.py
└── test_integration.py
```

## Files to UPDATE

1. **Remove wake.utils import** from `wake/ai/detections.py`
   - Copy StrEnum implementation or require Python 3.11+

2. **Update all imports** to use new package structure:
   - Change `from wake.ai.*` to `from wake_ai_core.*`
   - Change `from wake_ai.*` to `from wake_ai_core.workflows.*`

3. **Create plugin interface** in `wake_ai_core/plugin.py`:
   - Define hooks for Wake CLI integration
   - Provide detector registration mechanism

4. **Update working directory configuration**:
   - Change hardcoded `.wake/ai/` to configurable path
   - Allow override via environment variable or config

## Files to REMOVE

### From Wake Core
- `wake/cli/ai.py` (functionality moved to plugin)
- AI-specific imports from `wake/cli/detect.py`
- All `__pycache__` directories

### Detector-Specific (Stay with Wake)
- Entire `wake_detectors/ai/` directory (23 files)
- These remain as Wake detector implementations using the new package

### Documentation
- `CLAUDE.md` (relevant parts moved to package README)

## Implementation Tasks

### Phase 1: Package Structure
- [ ] Create new package directory structure
- [ ] Copy core files
- [ ] Copy workflow implementations
- [ ] Consolidate duplicate prompts

### Phase 2: Remove Dependencies
- [ ] Copy StrEnum compatibility wrapper
- [ ] Update all import statements
- [ ] Remove wake-specific dependencies

### Phase 3: Plugin System
- [ ] Define plugin interface API
- [ ] Create Wake integration hooks
- [ ] Implement detector bridge pattern

### Phase 4: Standalone Features
- [ ] Create standalone CLI entry point
- [ ] Add configuration system
- [ ] Implement session management

### Phase 5: Testing & Documentation
- [ ] Write comprehensive tests
- [ ] Create API documentation
- [ ] Add usage examples
- [ ] Write migration guide

### Phase 6: Wake Integration
- [ ] Update Wake to use new package
- [ ] Modify CLI commands to use plugin
- [ ] Test detector functionality
- [ ] Update Wake documentation

## Migration Strategy

1. **Create new repository** for `wake_ai_core` package
2. **Maintain backward compatibility** during transition
3. **Use feature flags** to switch between old/new implementation
4. **Gradual rollout** with testing at each phase
5. **Deprecation period** for old structure
6. **Final removal** of duplicated code from Wake

## Benefits

- **Standalone Usage**: AI workflows can be used without Wake
- **Cleaner Architecture**: Clear separation of concerns
- **Easier Testing**: Isolated test suite
- **Better Versioning**: Independent release cycles
- **Reusability**: Other projects can use AI framework

## Risks & Mitigations

- **Risk**: Breaking existing Wake detectors
  - **Mitigation**: Maintain compatibility layer during transition

- **Risk**: User confusion during migration
  - **Mitigation**: Clear documentation and migration guides

- **Risk**: Duplicate maintenance burden
  - **Mitigation**: Quick transition timeline, automated testing

## Timeline Estimate

- Phase 1-2: 1 week
- Phase 3-4: 1 week  
- Phase 5: 1 week
- Phase 6: 1 week
- Buffer: 1 week

**Total**: 5 weeks for complete migration