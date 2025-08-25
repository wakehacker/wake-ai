"""Claude Code CLI wrapper for Python integration."""

import asyncio
import json
import logging
import subprocess
import signal
import sys
import atexit
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, AsyncIterator
from dataclasses import dataclass
from wake_ai.utils.logging import get_debug

from rich.console import Console

from claude_code_sdk import (ClaudeCodeOptions, AssistantMessage, ResultMessage, ToolUseBlock, TextBlock, query, SystemMessage, ToolResultBlock, UserMessage, CLINotFoundError, ProcessError, CLIJSONDecodeError, Message)

# Set up logging
logger = logging.getLogger(__name__)


## VERBOSE MODE CONFIGURATIONS ###
MAX_TOOL_RESULT_LINES: int = 10
SHOW_FULL_TOOL_RESULT: bool = False
COLORS = {
    "todo_header": "bold blue",
    "todo_complete": "bold green",
    "todo_progress": "yellow",
    "todo_pending": "dim white",
    "tool_use": "bright_magenta",
    "tool_input": "magenta",
    "tool_result": "bright_cyan",
    "tool_result_json": "cyan",
    "tool_error": "bold red",
    "system_msg": "purple",
    "thinking": "dim white",
    "unknown": "dim red",
    "truncation": "dim italic yellow"
}

@dataclass
class ClaudeCodeResponse:
    """Parsed response from Claude Code CLI."""

    content: str
    tool_calls: List[Dict[str, Any]]
    success: bool # THIS Does not matter with the result. fail of claude, by default, always true.
    cost: float = 0.0
    duration: float = 0.0
    num_turns: int = 0
    session_id: str = ""
    is_finished: bool = True # THIS INDICATES subtype == "success"


class ClaudeCodeSession:
    """Wrapper for Claude Code CLI interactions."""

    def __init__(
        self,
        console: Console,
        model: str = "sonnet",
        allowed_tools: Optional[List[str]] = None,
        disallowed_tools: Optional[List[str]] = None,
        working_dir: Optional[Union[str, Path]] = None,
        execution_dir: Optional[Union[str, Path]] = None,
        session_id: Optional[str] = None,

    ):
        """Initialize Claude Code session.

        Args:
            model: Model to use (sonnet, opus, or full model name)
            allowed_tools: List of allowed tools
            disallowed_tools: List of disallowed tools
            working_dir: Scratch space directory for AI to create files
            execution_dir: Directory where Claude CLI is executed (cwd)
            session_id: Optional session ID to continue a previous conversation
        """
        self.model = model
        self.allowed_tools = allowed_tools or []
        self.disallowed_tools = disallowed_tools or []
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.execution_dir = Path(execution_dir) if execution_dir else Path.cwd()
        self.verbose = get_debug()
        self.last_session_id = session_id
        self.session_history: List[str] = []  # Track all session IDs
        self.console = console

        if session_id:
            self.session_history.append(session_id)

        logger.debug(f"Initializing ClaudeCodeSession: model={model}, working_dir={self.working_dir}, execution_dir={self.execution_dir}")
        if session_id:
            logger.debug(f"Session ID provided: {session_id}")
        logger.debug(f"Allowed tools: {self.allowed_tools}")
        logger.debug(f"Disallowed tools: {self.disallowed_tools}")

        # Validate Claude CLI is available
        from .utils import validate_claude_cli
        validate_claude_cli()


    def format_todo_list(self, todos: List[Dict[str, Any]]) -> None:
        """Format and print a todo list with Rich colors."""

        # Use console.print with no_wrap to work with progress bars
        self.console.print(f"  📋 [{COLORS['todo_header']}]Todo List:[/{COLORS['todo_header']}]", highlight=False)
        for todo in todos:
            status = todo.get("status", "pending")
            content = todo.get("content", "")
            todo_id = todo.get("id", "")

            # Choose icon and style based on status
            if status == "completed":
                icon = "✅"
                style = COLORS['todo_complete']
            elif status == "in_progress":
                icon = "🔄"
                style = COLORS['todo_progress']
            else:  # pending
                icon = "⏳"
                style = COLORS['todo_pending']

            self.console.print(f"    {icon} [[{style}]{todo_id}[/{style}]] {content}", highlight=False)

    def print_top_and_bottom(self, content: Any, style: str) -> None:
        """Print content with truncation using Rich."""

        if style is None:
            style = COLORS['tool_result']

        string_content = str(content)
        lines = string_content.split('\n')

        if SHOW_FULL_TOOL_RESULT or len(lines) <= MAX_TOOL_RESULT_LINES * 2:
            # Show all content
            for line in lines:
                self.console.print(line, style=style, highlight=False)
        else:
            # Show truncated content
            # First lines
            for line in lines[:MAX_TOOL_RESULT_LINES]:
                self.console.print(line, style=style, highlight=False)

            # Omission message
            omitted = len(lines) - MAX_TOOL_RESULT_LINES * 2
            self.console.print(
                f"[{COLORS['truncation']}]... ({omitted} lines omitted by wake-ai) ...[/{COLORS['truncation']}]",
                highlight=False
            )

            # Last lines
            for line in lines[-MAX_TOOL_RESULT_LINES:]:
                self.console.print(line, style=style, highlight=False)


    def format_tool_use(self, block: ToolUseBlock) -> None:
        """Format and print tool usage with Rich."""

        # Special formatting for TodoWrite
        if block.name == "TodoWrite" and "todos" in block.input:
            self.console.print(f"[{COLORS['tool_use']}]Using tool: {block.name}[/{COLORS['tool_use']}]")
            self.format_todo_list(block.input.get("todos", []))
        else:
            self.console.print(f"[{COLORS['tool_use']}]Using tool: {block.name}[/{COLORS['tool_use']}]")
            # Default formatting for other tools
            for key, value in block.input.items():
                self.console.print(f"[{COLORS['tool_input']}]Tool input: {key}[/{COLORS['tool_input']}]")
                self.print_top_and_bottom(value, style=COLORS['tool_input'])



    def format_tool_result(self, block: ToolResultBlock) -> None:
        """Format and print tool results with Rich."""

        # Choose style based on error state
        if block.is_error:
            header_style = COLORS['tool_error']
            content_style = "red"
        else:
            header_style = COLORS['tool_result']
            content_style = COLORS['tool_result_json']

        if isinstance(block.content, str):
            # Try to parse as JSON for pretty printing
            try:
                parsed = json.loads(block.content)
                self.console.print(f"[{header_style}]Tool Result (JSON):[/{header_style}]")
                # Use Rich's built-in JSON formatter with log
                from rich.json import JSON
                self.console.print(JSON(json.dumps(parsed), indent=2))
            except (json.JSONDecodeError, ValueError):
                # Not JSON, show as regular text
                self.console.print(f"[{header_style}]Tool Result:[/{header_style}]")
                self.print_top_and_bottom(block.content, style=content_style)
        elif isinstance(block.content, list):
            # Handle list results
            for item in block.content:
                text_content = item.get('text') if hasattr(item, 'get') else None

                try:
                    if text_content:
                        parsed = json.loads(text_content)
                        self.console.print(f"[{header_style}]Tool Result (JSON):[/{header_style}]")
                        self.console.print_json(json.dumps(parsed), indent=2)
                    else:
                        self.console.print(f"[{header_style}]Tool Result:[/{header_style}]")
                        self.print_top_and_bottom(item, style=content_style)
                except json.JSONDecodeError:
                    self.console.print(f"[{header_style}]Tool Result:[/{header_style}]")
                    self.print_top_and_bottom(text_content, style=content_style)
                except Exception:
                    self.console.print(f"[{header_style}]Tool Result:[/{header_style}]")
                    self.print_top_and_bottom(item, style=content_style)
        else:
            # None or other type
            self.console.print(f"[{header_style}]Tool Result: No content[/{header_style}]")


    def handle_verbose_message(self, message: Message) -> None:
        """Handle verbose message formatting with Rich."""
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    # general tool result.
                    self.format_tool_result(block)
                elif isinstance(block, TextBlock):
                    # general thinking text.
                    self.console.print(block.text, style=COLORS['thinking'])
                elif isinstance(block, ToolUseBlock):
                    self.format_tool_use(block)
                else:
                    self.console.print(f"[{COLORS['unknown']}]Unknown block: {block}[/{COLORS['unknown']}]")

        elif isinstance(message, SystemMessage):
            if message.subtype == "init":
                self.console.print(f"[{COLORS['system_msg']}]System: {message.subtype}[/{COLORS['system_msg']}]")
                self.console.print(f"    [{COLORS['system_msg']}]CWD: {message.data.get('cwd', 'N/A')}[/{COLORS['system_msg']}]")
                self.console.print(f"    [{COLORS['system_msg']}]Session: {message.data.get('session_id', 'N/A')}[/{COLORS['system_msg']}]")
            else:
                self.console.print(f"[{COLORS['system_msg']}]System: {message.subtype}[/{COLORS['system_msg']}]")
                self.console.print(f"    [{COLORS['system_msg']}]{message.data}[/{COLORS['system_msg']}]")

        elif isinstance(message, UserMessage):
            for content in message.content:
                if isinstance(content, ToolResultBlock):
                    # special tool result. like mcp server.
                    self.format_tool_result(content)
                else:
                    self.console.print(f"[{COLORS['unknown']}]Unknown user content: {content}[/{COLORS['unknown']}]")
        else:
            self.console.print(f"[{COLORS['unknown']}]Unknown message: {message}[/{COLORS['unknown']}]")




    async def query_async(
        self,
        prompt: str,
        max_turns: Optional[int] = None,
        resume_session: Optional[str] = None, # put sesision id when continue or reusme the sesison.
        continue_session: bool = False, # always show the continuation by resume session id.
    ) -> ClaudeCodeResponse:
        """Execute a query with Claude Code asynchronously."""

        if resume_session and continue_session:
            raise ValueError("resume_session and continue_session cannot be used together")

        # # Determine if we should resume a session
        resume_session_id = None
        if resume_session:
            resume_session_id = resume_session
            logger.debug(f"Resuming session: {resume_session_id}") # in current session.

        options = ClaudeCodeOptions(
            allowed_tools=self.allowed_tools,
            disallowed_tools=self.disallowed_tools,
            max_turns=max_turns,
            resume=resume_session_id,
            continue_conversation=continue_session, # always show the continuation by resume session id.
            model=self.model,
            cwd=str(self.execution_dir),  # Use working_dir for SDK since it's the scratch space
            permission_mode="default",
            # mcp_servers = # custom mcp server. Here assume already installed as project or user.
            # max_thinking_tokens=
            # mcp_tools=
            # settings=
            # add_dirs=
            # append_system_prompt !!!!!
        )

        result: ResultMessage | None = None

        try:
            async for message in query(prompt=prompt, options=options):
                # ResultMessage indicates the response is complete.
                if isinstance(message, ResultMessage):
                    result = message
                else:
                    if self.verbose:
                        self.handle_verbose_message(message)
        # official excpetion branch.
        # https://github.com/anthropics/claude-code-sdk-python

        # TODO: COULD BE GOOD TO RAISE

        except CLINotFoundError:
            logger.error("Claude Code CLI not found. Please install it.")
            return ClaudeCodeResponse(
                content="Claude Code CLI not found. Please install it.",
                tool_calls=[],
                success=False,
            )
        except ProcessError as e:
            logger.error(f"Claude Code process failed with exit code: {e.exit_code}")
            if result is not None:
                return ClaudeCodeResponse(
                    content=result.result if result.result else "",
                    tool_calls=[result.usage] if result.usage else [],
                    success=not result.is_error,
                    cost=result.total_cost_usd or 0.0,
                    duration=result.duration_ms,
                    num_turns=result.num_turns,
                    session_id=result.session_id,
                    is_finished=result.subtype == "success"
                )
            else:
                return ClaudeCodeResponse(
                    content=f"Process failed with exit code: {e.exit_code} \n {e}",
                    tool_calls=[],
                    success=False,
                )
        except CLIJSONDecodeError as e:
            logger.error(f"Failed to parse Claude Code response: {e}")
            return ClaudeCodeResponse(
                content=f"Failed to parse response: {e}",
                tool_calls=[],
                success=False,
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return ClaudeCodeResponse(
                content=f"Unexpected error: {e}",
                tool_calls=[],
                success=False,
            )

        if result is None:
            # Should never happen, but just in case
            return ClaudeCodeResponse(
                content=f"Claude Code did not return a ResultMessage",
                tool_calls=[],
                success=False,
            )

        return ClaudeCodeResponse(
            content=result.result if result.result else "",
            tool_calls=[result.usage] if result.usage else [],
            success=not result.is_error, # does not matter subtype == success or not .
            cost=result.total_cost_usd or 0.0,
            duration=result.duration_ms,
            num_turns=result.num_turns,
            session_id=result.session_id,
            is_finished=result.subtype == "success"
        )

    def query(
        self,
        prompt: str,
        max_turns: Optional[int] = None,
        continue_session: bool = False,
    ) -> ClaudeCodeResponse:
        """Execute a query with Claude Code.

        Args:
            prompt: The prompt to send
            output_format: Output format (json, text, stream-json)
            max_turns: Maximum number of turns for agentic mode
            input_data: Optional input data to pipe to Claude
            continue_session: Continue the stored session if available

        Returns:
            ClaudeCodeResponse with the result
        """

        # resume_session_id = None
        # if continue_session and self.last_session_id:
        #     resume_session_id = self.last_session_id

        if continue_session:
            logger.debug(f"Continuing session: {continue_session}")

        response = asyncio.run(self.query_async(
            prompt=prompt,
            max_turns=max_turns,
            continue_session=continue_session
        ))

        if not response.success and response.content == "Prompt is too long":
            logger.info(f"Prompt is too long: Auto compacting...")
            response = asyncio.run(self.query_async(
                prompt="/compact",
                max_turns=max_turns,
                resume_session=response.session_id # only happen continue session is true, compacting this continueing session.
            ))

            # runnning again as compacted.
            response = asyncio.run(self.query_async(
                prompt=prompt,
                max_turns=max_turns,
                resume_session=response.session_id  # Running session with compacted.
            ))

        # Use asyncio.run to call the async version
        return response


    def save_session_state(self, session_id: str, state_file: Union[str, Path]):
        """Save session state for later resumption.

        Args:
            session_id: The session ID to save (optional, uses last_session_id if not provided)
            state_file: Path to save the state
        """
        # Add the session_id to history if provided
        if session_id and session_id not in self.session_history:
            self.session_history.append(session_id)

        state = {
            "sessions": self.session_history,  # Save all session IDs
            "last_session_id": self.last_session_id,  # Track the most recent
            "model": self.model,
            "allowed_tools": self.allowed_tools,
            "disallowed_tools": self.disallowed_tools,
            "working_dir": str(self.working_dir),
            "execution_dir": str(self.execution_dir)
        }

        state_path = Path(state_file)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2))
        logger.debug(f"Saved session state to {state_path} (sessions={len(self.session_history)}, last={self.last_session_id})")

    @classmethod
    def load_session_state(cls, state_file: Union[str, Path], console: Console) -> tuple["ClaudeCodeSession", str]:
        """Load a saved session state.

        Args:
            state_file: Path to the state file

        Returns:
            Tuple of (ClaudeCodeSession, last_session_id)
        """
        state_path = Path(state_file)
        logger.debug(f"Loading session state from {state_path}")

        try:
            state = json.loads(state_path.read_text())

            sessions = state["sessions"]
            last_session_id = state.get("last_session_id")

            logger.debug(f"Loaded state: model={state['model']}, sessions={len(sessions)}, last_session_id={last_session_id}")

            session = cls(
                model=state["model"],
                allowed_tools=state.get("allowed_tools", []),
                disallowed_tools=state.get("disallowed_tools", []),
                working_dir=state.get("working_dir"),
                execution_dir=state.get("execution_dir"),
                session_id=last_session_id,
                console=console
            )

            # Restore the full session history
            session.session_history = sessions

            return session, last_session_id

        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load session state: {e}")
            raise ValueError(f"Invalid or outdated session state file: {e}")

    def get_session_id(self) -> Optional[str]:
        """Get the current session ID.

        Returns:
            The current session ID, or None if no session has been started.
        """
        return self.last_session_id

    def reset_session(self):
        """Reset the session ID, forcing a new conversation on the next query."""
        self.last_session_id = None
        logger.debug("Session ID reset")

    def get_session_history(self) -> List[str]:
        """Get the full history of session IDs.

        Returns:
            List of all session IDs used in this instance.
        """
        return self.session_history.copy()