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
    AIDetection,
    AILocation,
    Severity,
    print_ai_detection,
    export_ai_detections_json,
    AIDetectionResult,
)

# Runner imports
from .runner import run_ai_workflow

# Utils imports
from .utils import (
    load_workflow_from_file,
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
    "AIDetection",
    "AILocation",
    "Severity",
    "print_ai_detection",
    "export_ai_detections_json",
    "AIDetectionResult",
    # Runner
    "run_ai_workflow",
    # Utils
    "load_workflow_from_file",
    "validate_claude_cli",
    "query_with_cost",
    # Version
    "__version__",
]