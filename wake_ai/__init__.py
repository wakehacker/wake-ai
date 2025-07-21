"""Wake AI - AI-powered smart contract security analysis framework."""

# Framework imports
from .core import (
    ClaudeCodeResponse,
    ClaudeCodeSession,
    AIWorkflow,
    WorkflowStep,
    ClaudeNotAvailableError,
    WorkflowExecutionError,
)

# Result imports
from .results import (
    AIResult,
    SimpleResult,
    MessageResult,
)

# Detection imports
from .detections import (
    Detection,
    Location,
    Severity,
)
from .utils.formatters import (
    print_detection,
    export_detections_json,
)
from .utils.audit import (
    AuditResult,
)

# Runner imports
from .runner import run_ai_workflow

# Utils imports
from .utils.workflow import (
    load_workflow_from_file,
)

# Template imports
from .templates import (
    MarkdownDetector,
    MarkdownDetectorResult,
)


__version__ = "0.1.0"

__all__ = [
    # Framework
    "ClaudeCodeResponse",
    "ClaudeCodeSession",
    "AIWorkflow",
    "WorkflowStep",
    "ClaudeNotAvailableError",
    "WorkflowExecutionError",
    # Results
    "AIResult",
    "SimpleResult",
    "MessageResult",
    # Detections
    "Detection",
    "Location",
    "Severity",
    "print_detection",
    "export_detections_json",
    "AuditResult",
    # Runner
    "run_ai_workflow",
    # Utils
    "load_workflow_from_file",
    "validate_claude_cli",
    "query_with_cost",
    # Templates
    "MarkdownDetector",
    "MarkdownDetectorResult",
    # Version
    "__version__",
]