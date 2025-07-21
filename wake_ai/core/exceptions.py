"""Custom exceptions for AI module."""


from typing import Optional


class ClaudeNotAvailableError(RuntimeError):
    """Raised when Claude Code CLI is not available."""

    def __init__(self, message: Optional[str] = None):
        if message is None:
            message = (
                "Claude Code CLI not found. Please install it first.\n"
                "Install from: https://github.com/anthropics/claude-code"
            )
        super().__init__(message)


class WorkflowExecutionError(Exception):
    """Raised when a workflow fails to execute."""

    def __init__(self, workflow_name: str, message: str, original_error: Optional[Exception] = None):
        self.workflow_name = workflow_name
        self.original_error = original_error
        super().__init__(f"Workflow '{workflow_name}' failed: {message}")