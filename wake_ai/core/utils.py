"""Framework utility functions."""

import subprocess
from .exceptions import ClaudeNotAvailableError


def validate_claude_cli():
    """Check if Claude Code CLI is available and properly configured.

    Raises:
        ClaudeNotAvailableError: If Claude CLI is not available
    """
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            raise ClaudeNotAvailableError()

    except FileNotFoundError:
        raise ClaudeNotAvailableError()