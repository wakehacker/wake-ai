"""Claude Code CLI wrapper for Python integration."""

import json
import subprocess
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import tempfile
import os


@dataclass
class ClaudeCodeResponse:
    """Parsed response from Claude Code CLI."""

    content: str
    raw_output: str
    tool_calls: List[Dict[str, Any]]
    success: bool
    error: Optional[str] = None

    @classmethod
    def from_json(cls, json_str: str) -> "ClaudeCodeResponse":
        """Parse JSON output from Claude Code."""
        try:
            data = json.loads(json_str)
            return cls(
                content=data.get("content", ""),
                raw_output=json_str,
                tool_calls=data.get("tool_calls", []),
                success=True,
                error=None
            )
        except json.JSONDecodeError as e:
            return cls(
                content="",
                raw_output=json_str,
                tool_calls=[],
                success=False,
                error=f"Failed to parse JSON: {e}"
            )

    @classmethod
    def from_text(cls, text: str) -> "ClaudeCodeResponse":
        """Create response from plain text output."""
        return cls(
            content=text,
            raw_output=text,
            tool_calls=[],
            success=True,
            error=None
        )


class ClaudeCodeSession:
    """Wrapper for Claude Code CLI interactions."""

    def __init__(
        self,
        model: str = "sonnet",
        allowed_tools: Optional[List[str]] = None,
        disallowed_tools: Optional[List[str]] = None,
        working_dir: Optional[Union[str, Path]] = None,
        verbose: bool = False
    ):
        """Initialize Claude Code session.

        Args:
            model: Model to use (sonnet, opus, or full model name)
            allowed_tools: List of allowed tools
            disallowed_tools: List of disallowed tools
            working_dir: Working directory for Claude Code
            verbose: Enable verbose output
        """
        self.model = model
        self.allowed_tools = allowed_tools or []
        self.disallowed_tools = disallowed_tools or []
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.verbose = verbose
        self._check_claude_available()

    def _check_claude_available(self):
        """Check if Claude Code CLI is available."""
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                raise RuntimeError("Claude Code CLI not found. Please install it first.")
        except FileNotFoundError:
            raise RuntimeError("Claude Code CLI not found. Please install it first.")

    def _build_command(
        self,
        prompt: Optional[str] = None,
        non_interactive: bool = True,
        output_format: str = "json",
        max_turns: Optional[int] = None,
        resume_session: Optional[str] = None,
        continue_last: bool = False
    ) -> List[str]:
        """Build Claude Code CLI command."""
        cmd = ["claude"]

        # Model selection
        cmd.extend(["--model", self.model])

        # Tool configuration
        if self.allowed_tools:
            cmd.extend(["--allowedTools", ",".join(self.allowed_tools)])
        if self.disallowed_tools:
            cmd.extend(["--disallowedTools", ",".join(self.disallowed_tools)])

        # Output configuration
        cmd.extend(["-p", prompt])
        cmd.extend(["--output-format", output_format])
        if max_turns:
            cmd.extend(["--max-turns", str(max_turns)])

        # Session management
        if resume_session:
            cmd.extend(["--resume", resume_session])
        elif continue_last:
            cmd.append("--continue")

        # Verbose mode
        if self.verbose:
            cmd.append("--verbose")

        return cmd

    def query(
        self,
        prompt: str,
        output_format: str = "json",
        max_turns: Optional[int] = None,
        input_data: Optional[str] = None
    ) -> ClaudeCodeResponse:
        """Execute a query with Claude Code.

        Args:
            prompt: The prompt to send
            non_interactive: Use non-interactive mode
            output_format: Output format (json, text, stream-json)
            max_turns: Maximum number of turns for agentic mode
            input_data: Optional input data to pipe to Claude

        Returns:
            ClaudeCodeResponse with the result
        """
        cmd = self._build_command(
            prompt=prompt,
            output_format=output_format,
            max_turns=max_turns
        )

        try:
            # Prepare input
            stdin_input = input_data.encode() if input_data else None

            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                input=stdin_input.decode() if stdin_input else None,
                cwd=self.working_dir,
                check=False
            )

            if result.returncode != 0:
                return ClaudeCodeResponse(
                    content="",
                    raw_output=result.stderr,
                    tool_calls=[],
                    success=False,
                    error=f"Command failed: {result.stderr}"
                )

            # Parse response based on format
            if output_format == "json":
                return ClaudeCodeResponse.from_json(result.stdout)
            else:
                return ClaudeCodeResponse.from_text(result.stdout)

        except Exception as e:
            return ClaudeCodeResponse(
                content="",
                raw_output=str(e),
                tool_calls=[],
                success=False,
                error=str(e)
            )

    def query_with_context(
        self,
        prompt: str,
        context_files: Optional[List[Union[str, Path]]] = None,
        context_content: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ClaudeCodeResponse:
        """Query with additional context files or content.

        Args:
            prompt: The main prompt
            context_files: List of files to include as context
            context_content: Dictionary of filename -> content to include
            **kwargs: Additional arguments for query()

        Returns:
            ClaudeCodeResponse
        """
        # Build context prompt
        context_parts = []

        # Add file contents
        if context_files:
            for file_path in context_files:
                path = Path(file_path)
                if path.exists():
                    context_parts.append(f"File: {path.name}\n```\n{path.read_text()}\n```")

        # Add provided content
        if context_content:
            for filename, content in context_content.items():
                context_parts.append(f"File: {filename}\n```\n{content}\n```")

        # Combine with main prompt
        if context_parts:
            full_prompt = "\n\n".join(context_parts) + "\n\n" + prompt
        else:
            full_prompt = prompt

        return self.query(full_prompt, **kwargs)

    def save_session_state(self, session_id: str, state_file: Union[str, Path]):
        """Save session state for later resumption.

        Args:
            session_id: The session ID to save
            state_file: Path to save the state
        """
        state = {
            "session_id": session_id,
            "model": self.model,
            "allowed_tools": self.allowed_tools,
            "disallowed_tools": self.disallowed_tools,
            "working_dir": str(self.working_dir)
        }

        state_path = Path(state_file)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2))

    @classmethod
    def load_session_state(cls, state_file: Union[str, Path]) -> tuple["ClaudeCodeSession", str]:
        """Load a saved session state.

        Args:
            state_file: Path to the state file

        Returns:
            Tuple of (ClaudeCodeSession, session_id)
        """
        state_path = Path(state_file)
        state = json.loads(state_path.read_text())

        session = cls(
            model=state["model"],
            allowed_tools=state.get("allowed_tools", []),
            disallowed_tools=state.get("disallowed_tools", []),
            working_dir=state.get("working_dir")
        )

        return session, state["session_id"]