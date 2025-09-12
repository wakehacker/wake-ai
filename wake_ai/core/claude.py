"""Claude Code CLI wrapper for Python integration.

Provides a high-level Python interface to Claude Code CLI with session management,
cost tracking, and enhanced output formatting for AI workflow integration.
"""

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
from wake_ai.utils.logging import get_verbose_level

from rich.console import Console

from claude_code_sdk import (
    ClaudeCodeOptions,
    AssistantMessage,
    ResultMessage,
    ToolUseBlock,
    TextBlock,
    query,
    SystemMessage,
    ToolResultBlock,
    UserMessage,
    CLINotFoundError,
    ProcessError,
    CLIJSONDecodeError,
    Message,
)

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class Write:
    file_path: str
    content: str

@dataclass
class Read:
    file_path: str
    limit: int | None = None
    offset: int | None = None

@dataclass
class Bash:
    command: str
    description: str

@dataclass
class TodoItem:
    content: str
    status: str
    activeForm: str

@dataclass
class TodoWrite:
    todos: list[TodoItem]

    @classmethod
    def from_dict(cls, data: dict) -> 'TodoWrite':
        """Factory method to create TodoWrite from raw dictionary data."""
        todo_items = [TodoItem(**todo_dict) for todo_dict in data.get('todos', [])]
        return cls(todos=todo_items)

@dataclass
class Edit:
    file_path: str
    old_string: str
    new_string: str


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
    "truncation": "dim italic yellow",
}
# Prompt used for session compaction when context becomes too long
COMPACT_PROMPT = (
    "Preserve original task that triggered this session, summarize current state "
    "(completed steps, pending work, active files), capture key findings "
    "(decisions, discoveries, issues), and include essential context "
    "(relevant code/configs/variables) with distilled reasoning and plans "
    "for seamless continuation."
)


@dataclass
class ClaudeCodeResponse:
    """Structured response data from Claude Code CLI execution.

    Contains the response content, tool usage information, execution metadata,
    and success status for a single Claude Code interaction.
    """

    content: str
    tool_calls: List[Dict[str, Any]]
    success: bool # THIS Does not matter with the result. fail of claude, by default, always true.
    cost: float = 0.0
    duration: float = 0.0
    num_turns: int = 0
    session_id: str = ""
    is_finished: bool = True # THIS INDICATES subtype == "success"


class ClaudeCodeSession:
    """High-level wrapper for Claude Code CLI interactions.

    Manages Claude Code sessions with cost tracking, verbose output formatting,
    session persistence, and automatic prompt compaction when context limits
    are reached.
    """

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
            console: Rich console instance for formatted output
            model: Model to use (sonnet, opus, or full model name)
            allowed_tools: List of tools the AI is permitted to use
            disallowed_tools: List of tools the AI is forbidden from using
            working_dir: Directory for AI to create temporary files and outputs
            execution_dir: Working directory where Claude CLI commands are executed
            session_id: Optional session ID to resume a previous conversation
        """
        self.model = model
        self.allowed_tools = allowed_tools or []
        self.disallowed_tools = disallowed_tools or []
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.execution_dir = Path(
            execution_dir) if execution_dir else Path.cwd()
        self.verbose = get_verbose_level()
        self.last_session_id = session_id
        self.session_history: List[str] = []  # Track all session IDs
        self.console = console

        # distingish from tool Id to tool name
        self.tool_use_id_to_name: dict[str, str] = {}
        if session_id:
            self.session_history.append(session_id)

        logger.debug(
            f"Initializing ClaudeCodeSession: model={model}, working_dir={self.working_dir}, execution_dir={self.execution_dir}"
        )
        if session_id:
            logger.debug(f"Session ID provided: {session_id}")
        logger.debug(f"Allowed tools: {self.allowed_tools}")
        logger.debug(f"Disallowed tools: {self.disallowed_tools}")

        # Ensure Claude CLI is installed and accessible
        from .utils import validate_claude_cli
        validate_claude_cli()

    def format_todo_list(self, todo_write: TodoWrite) -> None:
        """Display a formatted todo list with color-coded status indicators.

        Uses Rich styling to show todo items with appropriate icons and colors
        based on their completion status (pending, in_progress, completed).
        """

        # Print header without text wrapping to maintain formatting
        self.console.print(
            f"📋 [{COLORS['todo_header']}]Todo List:[/{COLORS['todo_header']}]",
            highlight=False,
        )
        for todo in todo_write.todos:
            status = todo.status
            content = todo.content

            # Select appropriate visual indicators for each status type
            if status == "completed":
                icon = "✅"
                style = COLORS["todo_complete"]
            elif status == "in_progress":
                icon = "🔄"
                style = COLORS["todo_progress"]
            else:  # pending
                icon = "⏳"
                style = COLORS["todo_pending"]

            self.console.print(
                f"{icon} [{style}] {content} [/{style}] ", highlight=False
            )

    def print_top_and_bottom(self, content: Any, style: str) -> None:
        """Display content with smart truncation to manage long outputs.

        Shows the beginning and end of long content with a truncation indicator
        in the middle. This helps keep logs readable while preserving important
        information from both the start and end of the output.
        """

        if style is None:
            style = COLORS["tool_result"]

        string_content = str(content)
        lines = string_content.split("\n")

        max_tool_result_lines = 0
        if self.verbose == 1:
            max_tool_result_lines = 1
        elif self.verbose == 2:
            max_tool_result_lines = 4
        elif self.verbose == 3:
            max_tool_result_lines = 10

        if self.verbose >= 4 or len(lines) <= max_tool_result_lines * 2:
            # Content is short enough to display in full
            for line in lines:
                self.console.print(line, style=style, highlight=False)
        else:
            # Content is too long, show truncated version
            # Display first portion
            for line in lines[:max_tool_result_lines]:
                self.console.print(line, style=style, highlight=False)

            # Show truncation indicator with count of omitted lines
            omitted = len(lines) - max_tool_result_lines * 2
            self.console.print(
                f"[{COLORS['truncation']}]... ({omitted} lines omitted by wake-ai) ...[/{COLORS['truncation']}]",
                highlight=False,
            )

            # Display final portion
            for line in lines[-max_tool_result_lines:]:
                self.console.print(line, style=style, highlight=False)

    def format_tool_use(self, block: ToolUseBlock) -> None:
        """Display formatted tool usage information with syntax highlighting.

        Provides special formatting for TodoWrite tools to show structured
        todo lists, while using standard formatting for other tool types.
        """

        self.tool_use_id_to_name[block.id] = block.name

        # Check if this tool should be shown based on filters
        from wake_ai.utils.logging import should_show_tool
        if not should_show_tool(block.name):
            # print(f"filtering {block.name} tool use")
            return  # Skip this tool

        # TodoWrite gets custom formatting to display structured todo lists
        if block.name == "TodoWrite":
            todo_write_input = TodoWrite.from_dict(block.input)
            print_str = f"Using {block.name}: "

            completed_count = 0
            in_progress_count = 0
            pending_count = 0

            if self.verbose == 1:
                next_tasks_str = ""
                for todo in todo_write_input.todos:
                    if todo.status == "in_progress":
                        next_tasks_str += f"{todo.content}, "
                        in_progress_count += 1
                    elif todo.status == "completed":
                        completed_count += 1
                    else: # if todo.status == "pending"
                        pending_count += 1

                total_count = completed_count + in_progress_count + pending_count
                print_str += f"{completed_count}/{total_count} done."

                if next_tasks_str:
                    print_str += f" Next -> {next_tasks_str}"

                self.console.print(
                    f"[{COLORS['tool_use']}]{print_str}[/{COLORS['tool_use']}]"
                )
                return
            elif self.verbose >= 2:
                self.format_todo_list(todo_write_input)
            return

        elif block.name == "Bash":
            bash_input = Bash(**block.input)

            print_str = f"Using {block.name}: {bash_input.command}"

            if bash_input.description and self.verbose >= 2:
                print_str += f" # {bash_input.description}"

            self.console.print(
                f"[{COLORS['tool_use']}]{print_str}[/{COLORS['tool_use']}]"
            )
            return

        elif block.name == "Read":

            read_input = Read(**block.input)

            try:
                path = Path(read_input.file_path).relative_to(self.execution_dir)
            except:
                path = Path(read_input.file_path)

            print_str = f"Using {block.name}: {path}"

            if read_input.limit:
                print_str += f" limit: {read_input.limit}"

            if read_input.offset:
                print_str += f" offset: {read_input.offset}"

            self.console.print(
                f"[{COLORS['tool_use']}]{print_str}[/{COLORS['tool_use']}]"
            )
            return

        elif block.name == "Write":
            write_input = Write(**block.input)

            if self.verbose == 1:
                try:
                    path = Path(write_input.file_path).relative_to(self.execution_dir)
                except:
                    path = Path(write_input.file_path)
                print_str = f"Using Write: {path}: {len(write_input.content.split('\n'))} lines"
                self.console.print(
                    f"[{COLORS['tool_use']}]{print_str}[/{COLORS['tool_use']}]"
                )
            return

        elif block.name == "Edit":
            edit_input = Edit(**block.input)
            if self.verbose == 1:

                try:
                    path = Path(edit_input.file_path).relative_to(self.execution_dir)
                except:
                    path = Path(edit_input.file_path)

                print_str = f"Using Edit: {path}"

                if edit_input.old_string:
                    print_str += f" old_string_lines_length: {len(edit_input.old_string.split('\n'))}"

                if edit_input.new_string:
                    print_str += f" new_string_lines_length: {len(edit_input.new_string.split('\n'))}"

                self.console.print(
                    f"[{COLORS['tool_use']}]{print_str}[/{COLORS['tool_use']}]"
                )
            return

        elif "mcp__" in block.name:
            # Format MCP tool calls nicely
            print_str = f"Using {block.name}("

            # Format parameters
            params = []
            for key, value in block.input.items():
                # I do not think this is good idea. but .... TODO
                if key == 'file_path' and isinstance(value, str):
                    # Try to make file path relative
                    try:
                        relative_path = Path(value).relative_to(self.execution_dir)
                        params.append(f"{key}={relative_path}")
                    except (ValueError, TypeError):
                        params.append(f"{key}={value}")
                else:
                    params.append(f"{key}={value}")

            print_str += ", ".join(params) + ")"

            self.console.print(
                f"[{COLORS['tool_use']}]{print_str}[/{COLORS['tool_use']}]"
            )
            return
        elif block.name == "Grep":
            print_str = f"Using Grep("
            params = []
            for key, value in block.input.items():
                # I do not think this is good idea. but .... TODO
                if key == 'file_path' and isinstance(value, str):
                    # Try to make file path relative
                    try:
                        relative_path = Path(value).relative_to(self.execution_dir)
                        params.append(f"{key}={relative_path}")
                    except (ValueError, TypeError):
                        params.append(f"{key}={value}")
                else:
                    params.append(f"{key}={value}")

            print_str += ", ".join(params) + ")"

            self.console.print(
                f"[{COLORS['tool_use']}]{print_str}[/{COLORS['tool_use']}]"
            )
            return

        elif block.name == "Glob":
            print_str = f"Using Glob("
            params = []
            for key, value in block.input.items():
                params.append(f"{key}={value}")
            print_str += ", ".join(params) + ")"
            self.console.print(f"[{COLORS['tool_use']}]{print_str}[/{COLORS['tool_use']}]")
            return
        elif block.name == "LS":
            print_str = f"Using LS("
            params = []
            for key, value in block.input.items():
                params.append(f"{key}={value}")
            print_str += ", ".join(params) + ")"
            self.console.print(f"[{COLORS['tool_use']}]{print_str}[/{COLORS['tool_use']}]")
            return

        # print(block)

        self.console.print(
            f"[{COLORS['tool_use']}]Using tool: {block.name}[/{COLORS['tool_use']}]"
        )

        if self.verbose >= 2:
            # Standard tool display format for all other tool types
            for key, value in block.input.items():
                self.console.print(
                    f"[{COLORS['tool_input']}]Tool input: {key}[/{COLORS['tool_input']}]"
                )
                self.print_top_and_bottom(value, style=COLORS["tool_input"])

    def format_tool_result(self, block: ToolResultBlock) -> None:
        """Display formatted tool execution results with error handling.

        Automatically detects JSON content for pretty-printing, handles both
        string and list result types, and applies appropriate styling based
        on success/error status.
        """

        tool_name = self.tool_use_id_to_name.get(block.tool_use_id)

        if tool_name is None:
            raise ValueError(f"Tool name not found for tool use id: {block.tool_use_id}")

        from wake_ai.utils.logging import should_show_tool
        if not should_show_tool(tool_name):
            # print(f"filtering {tool_name} tool result")
            return

        # Apply error styling for failed operations, normal styling otherwise
        if block.is_error:
            header_style = COLORS["tool_error"]
            content_style = "red"
        else:
            block.is_error = False
            header_style = COLORS["tool_result"]
            content_style = COLORS["tool_result_json"]

        if tool_name == "TodoWrite" and (block.is_error == False) and self.verbose <= 1: # TodoWrite Result is not interesting usually
            return

        elif tool_name == "Bash" and (block.is_error == False): # Bash Result is not interesting usually
            # bash result should not be json.

            if self.verbose == 1:
                print_str = f"Bash Result:"
                if isinstance(block.content, str): # shoud be
                    print_str += f" {len(block.content.split('\n'))} lines"
                else:
                    # return list but shold not happen.
                    print_str += f" {len(block.content or [])} items"
                self.console.print(f"[{header_style}]{print_str}[/{header_style}]")
                return

            elif self.verbose == 2:
                # 5 lines from top to bottom, handled below
                pass
            elif self.verbose == 3:
                # full print, handled below
                pass

        elif tool_name == "Read" and (block.is_error == False):
            # read result should not be json.
            print_str = f"Read Result:"

            if isinstance(block.content, str): # shoud be
            # just print number of lines
                print_str += f" {len(block.content.split('\n'))} lines"
            else:
                # return list but shold not happen.
                print_str += f" {len(block.content or [])} items"

            self.console.print(f"[{header_style}]{print_str}[/{header_style}]")
            return

        elif tool_name == "Edit" and (block.is_error == False):
            if self.verbose == 1:
                print_str = f"Edit Result: success"
                self.console.print(f"[{header_style}]{print_str}[/{header_style}]")
                return

        elif "mcp__" in tool_name and (block.is_error == False):
            if self.verbose == 1:
                print_str = f"{tool_name} Result:"
                if isinstance(block.content, str):
                    print_str += f" {len(block.content.split('\n'))} lines"
                else:
                    # return list but shold not happen.
                    print_str += f" {len(block.content or [])} items"
                self.console.print(f"[{header_style}]{print_str}[/{header_style}]")
                return

        elif tool_name == "Write" and (block.is_error == False):
            if self.verbose == 1:
                print_str = f"Write Result: success"
                self.console.print(f"[{header_style}]{print_str}[/{header_style}]")
                return

        elif tool_name == "Grep" and (block.is_error == False):
            if self.verbose == 1:
                print_str = f"Grep Result:"
                if isinstance(block.content, str):
                    print_str += f" {len(block.content.split('\n'))} lines"
                else:
                    # return list but shold not happen.
                    print_str += f" {len(block.content or [])} items"

                self.console.print(f"[{header_style}]{print_str}[/{header_style}]")
                return
        elif tool_name == "Glob" and (block.is_error == False):
            if self.verbose == 1:
                print_str = f"Glob Result:"
                if isinstance(block.content, str):
                    print_str += f" {len(block.content.split('\n'))} lines"
                else:
                    # return list but shold not happen.
                    print_str += f" {len(block.content or [])} items"
                self.console.print(f"[{header_style}]{print_str}[/{header_style}]")
                return

        elif tool_name == "LS" and (block.is_error == False):
            if self.verbose == 1:
                print_str = f"LS Result:"
                if isinstance(block.content, str):
                    print_str += f" {len(block.content.split('\n'))} lines"
                else:
                    # return list but shold not happen.
                    print_str += f" {len(block.content or [])} items"
                self.console.print(f"[{header_style}]{print_str}[/{header_style}]")
                return

        elif block.is_error == True and isinstance(block.content, str):
            print_str = f"{tool_name} Error: {block.content}"
            self.console.print(f"[{header_style}][/{header_style}]")
            return
        elif block.is_error == True and isinstance(block.content, list):
            print_str = f"{tool_name} Error: {block.content}"
            self.console.print(f"[{header_style}]{print_str}[/{header_style}]")
            return

        # print(block)
        if isinstance(block.content, str):
            # Attempt JSON parsing for structured display
            try:
                parsed = json.loads(block.content)
                self.console.print(
                    f"[{header_style}]Tool Result (JSON):[/{header_style}]"
                )
                # Use Rich's JSON formatter for syntax highlighting
                from rich.json import JSON

                self.console.print(JSON(json.dumps(parsed), indent=2))
            except (json.JSONDecodeError, ValueError):
                # Fall back to plain text display
                self.console.print(
                    f"[{header_style}]Tool Result:[/{header_style}]")
                self.print_top_and_bottom(block.content, style=content_style)
        elif isinstance(block.content, list):
            # Process list-type results (multiple items)

            # print only the first and last item if the list is more than 2 items.
            content_list = block.content
            if self.verbose == 1:
                if len(content_list) > 2:
                    # Show first item
                    self._print_list_item(content_list[0], header_style, content_style)

                    # Show truncation indicator
                    omitted_count = len(content_list) - 1
                    self.console.print(
                        f"[{COLORS['truncation']}]... ({omitted_count} items omitted by wake-ai) ...[/{COLORS['truncation']}]",
                        highlight=False,
                    )

            elif self.verbose == 2:
                if len(content_list) > 2:
                    # Show first item
                    self._print_list_item(content_list[0], header_style, content_style)

                    # Show truncation indicator
                    omitted_count = len(content_list) - 2
                    self.console.print(
                        f"[{COLORS['truncation']}]... ({omitted_count} items omitted by wake-ai) ...[/{COLORS['truncation']}]",
                        highlight=False,
                    )

                    # Show last item
                    self._print_list_item(content_list[-1], header_style, content_style)
                else:
                    # Show all items for short lists
                    for item in content_list:
                        self._print_list_item(item, header_style, content_style)

            elif(self.verbose == 3):
                # Show all items for short lists
                for item in content_list:
                    self._print_list_item(item, header_style, content_style)

    def _print_list_item(self, item: Any, header_style: str, content_style: str) -> None:
        """Helper method to print a single list item with proper formatting."""
        text_content = item.get("text") if hasattr(item, "get") else None

        try:
            if text_content:
                parsed = json.loads(text_content)
                self.console.print(
                    f"[{header_style}]Tool Result (JSON):[/{header_style}]"
                )
                self.console.print_json(json.dumps(parsed), indent=2)
            else:
                self.console.print(
                    f"[{header_style}]Tool Result:[/{header_style}]"
                )
                self.print_top_and_bottom(item, style=content_style)
        except json.JSONDecodeError:
            self.console.print(
                f"[{header_style}]Tool Result:[/{header_style}]")
            self.print_top_and_bottom(
                text_content, style=content_style)
        except Exception:
            self.console.print(
                f"[{header_style}]Tool Result:[/{header_style}]")
            self.print_top_and_bottom(item, style=content_style)
        else:
            # Handle empty or unsupported result types
            self.console.print(
                f"[{header_style}]Tool Result: No content[/{header_style}]"
            )

    def handle_verbose_message(self, message: Message) -> None:
        """Process and display messages with appropriate formatting.

        Handles different message types (Assistant, System, User) and applies
        specialized formatting based on content type and message source.
        """
        if isinstance(message, AssistantMessage):
            for block in message.content:

                if isinstance(block, ToolResultBlock):
                    # Standard tool execution result
                    ## change according to verbose level
                    self.format_tool_result(block)
                elif isinstance(block, TextBlock):
                    # AI reasoning and explanation text
                    self.console.print(block.text, style=COLORS["thinking"])
                elif isinstance(block, ToolUseBlock):
                    ## change according to verbose level
                    self.format_tool_use(block)
                else:
                    self.console.print(
                        f"[{COLORS['unknown']}]Unknown block: {block}[/{COLORS['unknown']}]"
                    )

        elif isinstance(message, SystemMessage):

            if message.subtype == "init":
                if self.verbose <= 2:
                    self.console.print(
                        f"[{COLORS['system_msg']}]System init: cwd: {message.data.get('cwd', 'N/A')} session: {message.data.get('session_id', 'N/A')}[/{COLORS['system_msg']}]"
                    )
                else:
                    self.console.print(
                        f"[{COLORS['system_msg']}]System: {message.subtype}[/{COLORS['system_msg']}]"
                    )
                    try:
                        print_str = json.dumps(message.data)
                    except:
                        print_str = str(message.data)

                    self.console.print(
                        f"[{COLORS['system_msg']}]{print_str}[/{COLORS['system_msg']}]"
                    )
            else:
                self.console.print(
                    f"[{COLORS['system_msg']}]System: {message.subtype}[/{COLORS['system_msg']}]"
                )
                self.console.print(
                    f"[{COLORS['system_msg']}]{message.data}[/{COLORS['system_msg']}]"
                )

        elif isinstance(message, UserMessage):
            for content in message.content:
                if isinstance(content, ToolResultBlock):
                    # Specialized tool result (e.g., from MCP server)
                    self.format_tool_result(content)
                elif isinstance(content, TextBlock):
                    if self.verbose == 1:
                        # just print 1 line by content.text.split('\n')[0]
                        texts = content.text.split('\n')
                        print_str = "User Text:"
                        print_str += texts[0]
                        if len(texts) > 1:
                            print_str += f"... with ({len(texts) - 1} lines omitted)"
                        self.console.print(print_str, style=COLORS["thinking"])
                    else:
                        self.console.print(content.text, style=COLORS["thinking"])
                else:
                    self.console.print(
                        f"[{COLORS['unknown']}]Unknown user content: {content}[/{COLORS['unknown']}]"
                    )
        else:
            self.console.print(
                f"[{COLORS['unknown']}]Unknown message: {message}[/{COLORS['unknown']}]"
            )

    async def _handle_result_with_auto_compact(
        self,
        result: ResultMessage,
        prompt: str,
        max_turns: Optional[int],
        auto_compact: bool,
    ) -> ClaudeCodeResponse:
        """Process result and automatically compact session if prompt becomes too long.

        When auto_compact is enabled and a "Prompt is too long" error occurs,
        this automatically triggers session compaction and retries the original
        prompt with the compacted context.
        """
        response = ClaudeCodeResponse(
            content=result.result if result.result else "",
            tool_calls=[result.usage] if result.usage else [],
            success=not result.is_error,
            cost=result.total_cost_usd or 0.0,
            duration=result.duration_ms,
            num_turns=result.num_turns,
            session_id=result.session_id,
            is_finished=result.subtype == "success",
        )

        # Handle prompt length limit exceeded by auto-compacting session
        if (
            auto_compact
            and not response.success
            and response.content == "Prompt is too long"
        ):
            logger.info("Prompt exceeded length limit, initiating auto-compaction")

            # Perform session compaction to reduce context size
            compact_prompt = f"/compact {COMPACT_PROMPT}"
            compact_response = await self.query_async(
                prompt=compact_prompt,
                max_turns=max_turns,
                resume_session=response.session_id,
                auto_compact=False,  # Prevent recursive compaction attempts
            )

            # Execute original request with the now-compacted session
            return await self.query_async(
                prompt=prompt,
                max_turns=max_turns,
                resume_session=compact_response.session_id,
                auto_compact=False,  # Session already compacted, no retry needed
            )

        return response

    async def query_async(
        self,
        prompt: str,
        max_turns: Optional[int] = None,
        resume_session: Optional[str] = None,  # Session ID to resume from
        continue_session: bool = False,  # Continue the stored session if available
        auto_compact: bool = True,  # Auto-compact on prompt-too-long error
    ) -> ClaudeCodeResponse:
        """Execute a query with Claude Code asynchronously.

        Args:
            prompt: The prompt to send to Claude
            max_turns: Maximum number of conversation turns allowed
            resume_session: Specific session ID to resume from
            continue_session: Whether to continue the last stored session
            auto_compact: Automatically compact session if prompt becomes too long

        Returns:
            ClaudeCodeResponse containing the execution result and metadata

        Raises:
            ValueError: If both resume_session and continue_session are specified
        """

        if resume_session and continue_session:
            raise ValueError(
                "resume_session and continue_session cannot be used together"
            )

        # Determine which session to resume (if any)
        resume_session_id = None
        if resume_session:
            resume_session_id = resume_session
            logger.debug(f"Resuming specified session: {resume_session_id}")

        options = ClaudeCodeOptions(
            allowed_tools=self.allowed_tools,
            disallowed_tools=self.disallowed_tools,
            max_turns=max_turns,
            resume=resume_session_id,
            # always show the continuation by resume session id.
            continue_conversation=continue_session,
            model=self.model,
            cwd=str(self.execution_dir),  # Set working directory for command execution
            permission_mode="default",
            # Future extension points:
            # mcp_servers=       # Custom MCP servers (assume already installed)
            # max_thinking_tokens=  # Limit reasoning tokens
            # mcp_tools=         # Specific MCP tools
            # settings=          # Additional Claude settings
            # add_dirs=          # Additional directories to include
            # append_system_prompt=  # Custom system prompt additions
        )

        result: ResultMessage | None = None

        try:
            async for message in query(prompt=prompt, options=options):
                # ResultMessage indicates the response is complete.
                if isinstance(message, ResultMessage):
                    result = message
                else:
                    if self.verbose:
                        try:
                            self.handle_verbose_message(message)
                        except Exception as e:
                            logger.error(f"Error during handling verbose message: {e}")
        # Handle official SDK exceptions as documented in:
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
                return await self._handle_result_with_auto_compact(
                    result, prompt, max_turns, auto_compact
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
            # Defensive check - should not occur in normal operation
            return ClaudeCodeResponse(
                content=f"Claude Code did not return a ResultMessage",
                tool_calls=[],
                success=False,
            )

        return await self._handle_result_with_auto_compact(
            result, prompt, max_turns, auto_compact
        )

    def query(
        self,
        prompt: str,
        max_turns: Optional[int] = None,
        continue_session: bool = False,
    ) -> ClaudeCodeResponse:
        """Execute a query with Claude Code (synchronous wrapper).

        Args:
            prompt: The prompt to send to Claude
            max_turns: Maximum number of conversation turns allowed
            continue_session: Whether to continue the last stored session

        Returns:
            ClaudeCodeResponse containing the execution result and metadata
        """

        # Note: Session resumption logic is handled in the async version

        if continue_session:
            logger.debug(f"Continuing session: {continue_session}")

        # Execute async version using asyncio event loop
        response = asyncio.run(
            self.query_async(
                prompt=prompt, max_turns=max_turns, continue_session=continue_session
            )
        )

        return response

    def save_session_state(self, session_id: str, state_file: Union[str, Path]):
        """Persist session state to disk for later resumption.

        Args:
            session_id: The session ID to save to state file
            state_file: File path where session state will be written
        """
        # Update session history with new session ID
        if session_id and session_id not in self.session_history:
            self.session_history.append(session_id)

        state = {
            "sessions": self.session_history,  # Complete session history
            "last_session_id": self.last_session_id,  # Most recently active session
            "model": self.model,
            "allowed_tools": self.allowed_tools,
            "disallowed_tools": self.disallowed_tools,
            "working_dir": str(self.working_dir),
            "execution_dir": str(self.execution_dir),
        }

        state_path = Path(state_file)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2))
        logger.debug(
            f"Saved session state to {state_path} (sessions={len(self.session_history)}, last={self.last_session_id})"
        )

    @classmethod
    def load_session_state(
        cls, state_file: Union[str, Path], console: Console
    ) -> tuple["ClaudeCodeSession", str]:
        """Restore session state from disk.

        Args:
            state_file: Path to the saved state file
            console: Rich console instance for output

        Returns:
            Tuple containing the restored session and its ID

        Raises:
            ValueError: If state file is invalid or cannot be parsed
        """
        state_path = Path(state_file)
        logger.debug(f"Loading session state from {state_path}")

        try:
            state = json.loads(state_path.read_text())

            sessions = state["sessions"]
            last_session_id = state.get("last_session_id")

            logger.debug(
                f"Loaded state: model={state['model']}, sessions={len(sessions)}, last_session_id={last_session_id}"
            )

            session = cls(
                model=state["model"],
                allowed_tools=state.get("allowed_tools", []),
                disallowed_tools=state.get("disallowed_tools", []),
                working_dir=state.get("working_dir"),
                execution_dir=state.get("execution_dir"),
                session_id=last_session_id,
                console=console,
            )

            # Restore complete session history from saved state
            session.session_history = sessions

            return session, last_session_id

        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load session state: {e}")
            raise ValueError(f"Invalid or outdated session state file: {e}")

    def get_session_id(self) -> Optional[str]:
        """Retrieve the current active session ID.

        Returns:
            Current session identifier, or None if no session is active
        """
        return self.last_session_id

    def reset_session(self):
        """Clear the current session, forcing a fresh conversation on next query."""
        self.last_session_id = None
        logger.debug("Session ID reset")

    def get_session_history(self) -> List[str]:
        """Retrieve complete history of all session IDs.

        Returns:
            Copy of the list containing all session IDs from this instance
        """
        return self.session_history.copy()
