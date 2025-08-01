"""Wake AI - AI-powered smart contract security analysis framework."""

from .cli import main as workflow

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

# Utils imports
from .utils.workflow import (
    load_workflow_from_file,
)

# Template imports
from .templates import (
    SimpleDetector,
    SimpleDetectorResult,
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
    # Utils
    "load_workflow_from_file",
    # Templates
    "SimpleDetector",
    "SimpleDetectorResult",
    # Version
    "__version__",
]