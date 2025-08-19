"""Claude Code CLI wrapper for Python integration."""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, AsyncIterator
from dataclasses import dataclass
from wake_ai.utils.logging import get_debug

from claude_code_sdk import (ClaudeCodeOptions, AssistantMessage, ResultMessage, ToolUseBlock, TextBlock, query, SystemMessage, ToolResultBlock, UserMessage, CLINotFoundError, ProcessError, CLIJSONDecodeError)

# Set up logging
logger = logging.getLogger(__name__)


def format_todo_list(todos: List[Dict[str, Any]]) -> None:
    """Format and print a todo list with icons and colors."""
    if not todos:
        return

    print(f"\033[94m  📋 Todo List:\033[0m")
    for todo in todos:
        status = todo.get("status", "pending")
        content = todo.get("content", "")
        todo_id = todo.get("id", "")

        # Choose icon and color based on status
        if status == "completed":
            icon, color = "✅", "\033[92m"  # Green
        elif status == "in_progress":
            icon, color = "🔄", "\033[93m"  # Yellow
        else:  # pending
            icon, color = "⏳", "\033[90m"  # Gray

        print(f"    {color}{icon} [{todo_id}] {content}\033[0m")


def format_tool_use(block: ToolUseBlock) -> None:
    """Format and print tool usage information."""
    print(f"\033[90m[Using tool: {block.name}]\033[0m", flush=True)

    # Special formatting for TodoWrite
    if block.name == "TodoWrite" and "todos" in block.input:
        format_todo_list(block.input.get("todos", []))
    else:
        # Default formatting for other tools
        for key, value in block.input.items():
            print(f"  \033[90m[Tool input: {key}: {value}]\033[0m", flush=True)

def format_tool_result(block: ToolResultBlock) -> None:
    """Format and print tool result information."""
    color = "\033[91m" if block.is_error else "\033[90m"
    import json

    if isinstance(block.content, str):
        # Try to parse as JSON for pretty printing
        # string result
        try:
            parsed = json.loads(block.content)
            print(f"{color}[Tool Result (JSON)]:\033[0m", flush=True)
            # Pretty print with indentation
            formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
            for line in formatted.split('\n'):
                print(f"{color}  {line}\033[0m", flush=True)
        except (json.JSONDecodeError, ValueError) as e:
            # Not JSON, show as regular string with preview
            print(f"{color}[Tool Result]\033[0m", flush=True)
            print(f"{color}{block.content}\033[0m", flush=True)
    elif isinstance(block.content, list):
        #  list[dict[str, Any]] result.
        for item in block.content:
            # Try to get text field if it exists
            text_content = item.get('text') if hasattr(item, 'get') else None

            try:
                if text_content:
                    # Try to parse as JSON
                    parsed = json.loads(text_content)
                    print(f"{color}[Tool Result (JSON)]:\033[0m", flush=True)
                    formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
                    for line in formatted.split('\n'):
                        print(f"{color}  {line}\033[0m", flush=True)
                else:
                    # No text field or not a dict, show as-is
                    print(f"{color}[Tool Result]\033[0m", flush=True)
                    print(f"{color}{item}\033[0m", flush=True)
            except json.JSONDecodeError:
                # Text exists but isn't valid JSON, show as plain text
                print(f"{color}[Tool Result]\033[0m", flush=True)
                print(f"{color}{text_content}\033[0m", flush=True)
            except Exception:
                # Any other error, show the item as-is
                print(f"{color}[Tool Result]\033[0m", flush=True)
                print(f"{color}{item}\033[0m", flush=True)


    else: # None
        print(f"{color}[Tool Result: Without any result]\033[0m", flush=True)


@dataclass
class ClaudeCodeResponse:
    """Parsed response from Claude Code CLI."""

    content: str
    tool_calls: List[Dict[str, Any]]
    success: bool
    cost: float = 0.0
    duration: float = 0.0
    num_turns: int = 0
    session_id: str = ""
    is_finished: bool = True


class ClaudeCodeSession:
    """Wrapper for Claude Code CLI interactions."""

    def __init__(
        self,
        model: str = "sonnet",
        allowed_tools: Optional[List[str]] = None,
        disallowed_tools: Optional[List[str]] = None,
        working_dir: Optional[Union[str, Path]] = None,
        execution_dir: Optional[Union[str, Path]] = None,
        session_id: Optional[str] = None
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


    def handle_verbose_message(self, message) -> None:
        """Handle verbose message formatting."""
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    # general tool result.
                    format_tool_result(block)
                elif isinstance(block, TextBlock):
                    # general thinking text.
                    print(f"\033[90m{block.text}\033[0m", flush=True)
                elif isinstance(block, ToolUseBlock):
                    format_tool_use(block)
                else:
                    print(f"\033[90mUnknown block: {block}\033[0m", flush=True)

        elif isinstance(message, SystemMessage):
            if message.subtype == "init":
                print(f"\033[38;5;95m[System message: {message.subtype}]\033[0m", flush=True)
                print(f"    \033[38;5;95m[CWD: {message.data['cwd']}]\033[0m", flush=True)
                print(f"    \033[38;5;95m[Session ID: {message.data['session_id']}]\033[0m", flush=True)
            else:
                print(f"\033[38;5;95m[System message: {message.subtype}]\033[0m", flush=True)
                print(f"    \033[38;5;95m[System message: {message.data}]\033[0m", flush=True)

        elif isinstance(message, UserMessage):
            for content in message.content:
                if isinstance(content, ToolResultBlock):
                    # special tool result. like mcp server.
                    format_tool_result(content)
                else:
                    print(f"\033[91m[UnknownUser message: {content}]\033[0m", flush=True)
        else:
            print(f"\033[38;5;95munknown message: {message}\033[0m")
            print(f"\033[38;5;95m[Unknown message: {message}]\033[0m", flush=True)

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
                if isinstance(message, ResultMessage):
                    result = message
                else:
                    if self.verbose:
                        self.handle_verbose_message(message)
        # official excpetion branch.
        # https://github.com/anthropics/claude-code-sdk-python

        except CLINotFoundError:
            logger.error("Claude Code CLI not found. Please install it.")
            return ClaudeCodeResponse(
                content="Claude Code CLI not found. Please install it.",
                tool_calls=[],
                success=False,
            )
        except ProcessError as e:
            logger.error(f"Claude Code process failed with exit code: {e.exit_code}")
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
                content=f"Command failed",
                tool_calls=[],
                success=False,
            )

        return ClaudeCodeResponse(
                content=result.result if result.result else "",
                tool_calls=[result.usage] if result.usage else [],
                success=result.subtype == "success",
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
        #     logger.debug(f"Continuing session: {resume_session_id}")

        # Use asyncio.run to call the async version
        return asyncio.run(self.query_async(
            prompt=prompt,
            max_turns=max_turns,
            continue_session=continue_session
        ))


    def query_with_cost(self, prompt: str, cost_limit: float, turn_step: int = 50, continue_session: bool = False) -> ClaudeCodeResponse:
        """Query with cost tracking.

        Args:
            prompt: The prompt to send
            cost_limit: The cost limit in USD
            turn_step: Maximum turns per query iteration
            continue_session: Continue the stored session if available

        Note:
            The cost limit is not strictly enforced.
            Instead, the querying runs in a loop, each time querying with `turn_step` turns.
            After each query, the cost is checked and the loop continues until the cost limit is reached.
            After that, if the task has still not been finished, the AI is prompted to promptly finish the task.

        Returns:
            ClaudeCodeResponse with the result
        """
        logger.debug(f"Starting cost-limited query (limit=${cost_limit:.2f}, turn_step={turn_step}, continue_session={continue_session})")

        total_cost = 0.0
        last_response = None
        iteration = 0

        # First query with the initial prompt
        logger.debug(f"Iteration {iteration}: Initial query")


        response = asyncio.run(self.query_async(
            prompt=prompt,
            max_turns=turn_step,
            continue_session=continue_session # this will continue true for always.
        ))

        session_id = response.session_id

        if not response.success:
            return response

        last_response = response

        # Update total cost and session info from response
        total_cost = response.cost
        # Use the response session_id if we didn't have one already
        if response.session_id:
            session_id = response.session_id
        logger.debug(f"Iteration {iteration} complete: total_cost=${total_cost:.4f}, session_id={session_id}")

        # Check if task is already finished
        if response.is_finished:
            logger.debug(f"Task finished in initial query. Total cost: ${total_cost:.4f}")
            return response

        # Continue querying while under cost limit
        while total_cost < cost_limit and session_id:
            iteration += 1
            logger.debug(f"Iteration {iteration}: Continuing session (current_cost=${total_cost:.4f}, limit=${cost_limit:.2f})")

            try:
                ## TODO: the result of response.is_finished is not progress but it might also showing help. it might good to rerun same prompt with different session.
                # Use asyncio.run to call the async version
                response = asyncio.run(self.query_async(
                    prompt="continue",
                    max_turns=turn_step,
                    resume_session=session_id # this will continue true for always.
                ))

                last_response = response

                total_cost += response.cost
                logger.debug(f"Iteration {iteration} complete: iteration_cost=${response.cost:.4f}, total_cost=${total_cost:.4f}")

                # Check if task is finished
                if response.is_finished:
                    logger.debug(f"Task finished after {iteration} iterations. Total cost: ${total_cost:.4f}")
                    return response

                # If we've exceeded the cost limit and task isn't finished
                if total_cost >= cost_limit:
                    logger.warning(f"Cost limit reached: ${total_cost:.4f} >= ${cost_limit:.2f}")
                    break

            except Exception as e:
                logger.error(f"Exception in iteration {iteration}: {e}")
                return ClaudeCodeResponse(
                    content=str(e),
                    tool_calls=[],
                    success=False,
                )

        # If the task is not finished, we need to prompt the AI to finish it
        if not last_response.is_finished:
            logger.warning("Task not finished after reaching cost limit. Attempting to finish...")

        finish_tries = 0
        max_finish_tries = 3
        while finish_tries < max_finish_tries and not last_response.is_finished:
            logger.debug(f"Finish attempt {finish_tries + 1}/{max_finish_tries}")

            try:
                prompt = f"you are running out of time, please finish the task as quickly as possible. this is the {finish_tries}/{max_finish_tries} try (after {max_finish_tries}th warning, the task will be aborted)"

                response = asyncio.run(self.query_async(
                    prompt=prompt,
                    max_turns=turn_step,
                    resume_session=session_id # this will continue true for always.
                ))

                last_response = response

                total_cost += response.cost
                logger.debug(f"Finish attempt {finish_tries + 1} complete: cost=${response.cost:.4f}, total=${total_cost:.4f}")

                # Check if task is finished
                if response.is_finished:
                    logger.debug(f"Task finished after {finish_tries + 1} finish attempts. Total cost: ${total_cost:.4f}")
                    return response

                finish_tries += 1
            except Exception as e:
                logger.error(f"Exception in finish attempt {finish_tries + 1}: {e}")
                return ClaudeCodeResponse(
                    content=str(e),
                    tool_calls=[],
                    success=False,
                )

        if not last_response.is_finished:
            logger.warning(f"Task still not finished after {max_finish_tries} attempts. Returning last response.")

        logger.debug(f"Returning final response. Total cost: ${total_cost:.4f}")
        return last_response

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
    def load_session_state(cls, state_file: Union[str, Path]) -> tuple["ClaudeCodeSession", str]:
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
                session_id=last_session_id
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