"""Claude Code CLI wrapper for Python integration."""

import json
import logging
import subprocess
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import tempfile
import os

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class ClaudeCodeResponse:
    """Parsed response from Claude Code CLI."""

    content: str
    raw_output: str
    tool_calls: List[Dict[str, Any]]
    success: bool
    error: Optional[str] = None
    cost: float = 0.0
    duration: float = 0.0
    num_turns: int = 0
    session_id: str = ""
    is_finished: bool = True

    @classmethod
    def from_json(cls, json_str: str) -> "ClaudeCodeResponse":
        """Parse JSON output from Claude Code.

        Emitted as the last message
        {
            type: "result";
            subtype: "success";
            duration_ms: float;
            duration_api_ms: float;
            is_error: boolean;
            num_turns: int;
            result: string;
            session_id: string;
            total_cost_usd: float;
        }

        Emitted as the last message, when we've reached the maximum number of turns
        {
            type: "result";
            subtype: "error_max_turns" | "error_during_execution";
            duration_ms: float;
            duration_api_ms: float;
            is_error: boolean;
            num_turns: int;
            session_id: string;
            total_cost_usd: float;
        }
        """
        try:
            data = json.loads(json_str)
            logger.debug(f"Parsed JSON response: type={data.get('type')}, subtype={data.get('subtype')}, cost=${data.get('total_cost_usd', 0):.4f}")

            return cls(
                content=data.get("result", ""),
                raw_output=json_str,
                tool_calls=[],
                success=not data.get("is_error", False),
                error=None if not data.get("is_error", False) else "Error occurred",
                cost=data.get("total_cost_usd", 0.0),
                duration=data.get("duration_ms", 0),
                num_turns=data.get("num_turns", 0),
                session_id=data.get("session_id", ""),
                is_finished=data.get("subtype", "success") == "success"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return cls(
                content="",
                raw_output=json_str,
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
            error=None,
            cost=0.0,
            duration=0.0,
            num_turns=0,
            session_id="",
            is_finished=True
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

        logger.info(f"Initializing ClaudeCodeSession: model={model}, working_dir={self.working_dir}")
        logger.debug(f"Allowed tools: {self.allowed_tools}")
        logger.debug(f"Disallowed tools: {self.disallowed_tools}")

        # Validate Claude CLI is available
        from .utils import validate_claude_cli
        validate_claude_cli()


    def _build_command(
        self,
        prompt: Optional[str] = None,
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

        cmd.append(prompt)

        logger.debug(f"Built command: {' '.join(cmd[:10])}..." if len(' '.join(cmd)) > 100 else f"Built command: {' '.join(cmd)}")
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
        logger.info(f"Executing query (format={output_format}, max_turns={max_turns}, prompt={prompt[:100]}...)")
        logger.debug(f"Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"Prompt: {prompt}")

        cmd = self._build_command(
            prompt=prompt,
            output_format=output_format,
            max_turns=max_turns
        )

        try:
            # Prepare input
            stdin_input = input_data.encode() if input_data else None

            # Execute command
            logger.debug("Executing subprocess...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                input=stdin_input.decode() if stdin_input else None,
                cwd=self.working_dir,
                check=False
            )

            if result.returncode != 0:
                logger.error(f"Command failed with return code {result.returncode}")
                logger.error(f"stderr: {result.stderr}")
                return ClaudeCodeResponse(
                    content="",
                    raw_output=result.stderr,
                    tool_calls=[],
                    success=False,
                    error=f"Command failed: {result.stderr}"
                )

            # Parse response based on format
            if output_format == "json":
                response = ClaudeCodeResponse.from_json(result.stdout)
                logger.info(f"Query completed: cost=${response.cost:.4f}, turns={response.num_turns}, finished={response.is_finished}")
                return response
            else:
                logger.debug("Query completed (text format)")
                return ClaudeCodeResponse.from_text(result.stdout)

        except Exception as e:
            logger.error(f"Exception during query execution: {e}")
            return ClaudeCodeResponse(
                content="",
                raw_output=str(e),
                tool_calls=[],
                success=False,
                error=str(e)
            )

    def query_with_cost(self, prompt: str, cost_limit: float, turn_step: int = 50) -> ClaudeCodeResponse:
        """Query with cost tracking.

        Args:
            prompt: The prompt to send
            cost_limit: The cost limit in USD
            turn_step: Maximum turns per query iteration

        Note:
            The cost limit is not strictly enforced.
            Instead, the querying runs in a loop, each time querying with `turn_step` turns.
            After each query, the cost is checked and the loop continues until the cost limit is reached.
            After that, if the task has still not been finished, the AI is prompted to promptly finish the task.

        Returns:
            ClaudeCodeResponse with the result
        """
        logger.info(f"Starting cost-limited query (limit=${cost_limit:.2f}, turn_step={turn_step})")

        total_cost = 0.0
        session_id = None
        last_response = None
        iteration = 0

        # First query with the initial prompt
        logger.info(f"Iteration {iteration}: Initial query")
        response = self.query(
            prompt=prompt,
            output_format="json",
            max_turns=turn_step
        )

        if not response.success:
            return response

        last_response = response

        # Update total cost and session info from response
        total_cost = response.cost
        session_id = response.session_id
        logger.debug(f"Iteration {iteration} complete: total_cost=${total_cost:.4f}, session_id={session_id}")

        # Check if task is already finished
        if response.is_finished:
            logger.info(f"Task finished in initial query. Total cost: ${total_cost:.4f}")
            return response

        # Continue querying while under cost limit
        while total_cost < cost_limit and session_id:
            iteration += 1
            logger.debug(f"Iteration {iteration}: Continuing session (current_cost=${total_cost:.4f}, limit=${cost_limit:.2f})")

            # Build command to resume the session
            cmd = self._build_command(
                prompt="continue",
                output_format="json",
                max_turns=turn_step,
                resume_session=session_id
            )

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.working_dir,
                    check=False
                )

                if result.returncode != 0:
                    logger.error(f"Iteration {iteration} failed: {result.stderr}")
                    return ClaudeCodeResponse(
                        content="",
                        raw_output=result.stderr,
                        tool_calls=[],
                        success=False,
                        error=f"Command failed: {result.stderr}"
                    )

                response = ClaudeCodeResponse.from_json(result.stdout)
                last_response = response

                total_cost += response.cost
                logger.debug(f"Iteration {iteration} complete: iteration_cost=${response.cost:.4f}, total_cost=${total_cost:.4f}")

                # Check if task is finished
                if response.is_finished:
                    logger.info(f"Task finished after {iteration} iterations. Total cost: ${total_cost:.4f}")
                    return response

                # If we've exceeded the cost limit and task isn't finished
                if total_cost >= cost_limit:
                    logger.warning(f"Cost limit reached: ${total_cost:.4f} >= ${cost_limit:.2f}")
                    break

            except Exception as e:
                logger.error(f"Exception in iteration {iteration}: {e}")
                return ClaudeCodeResponse(
                    content="",
                    raw_output=str(e),
                    tool_calls=[],
                    success=False,
                    error=str(e)
                )

        # If the task is not finished, we need to prompt the AI to finish it
        if not last_response.is_finished:
            logger.warning("Task not finished after reaching cost limit. Attempting to finish...")

        finish_tries = 0
        max_finish_tries = 3
        while finish_tries < max_finish_tries and not last_response.is_finished:
            logger.debug(f"Finish attempt {finish_tries + 1}/{max_finish_tries}")

            # Build command to resume the session
            cmd = self._build_command(
                prompt=f"you are running out of time, please finish the task as quickly as possible. this is the {finish_tries}/{max_finish_tries} try (after {max_finish_tries}th warning, the task will be aborted)",
                output_format="json",
                max_turns=turn_step,
                resume_session=session_id
            )

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.working_dir,
                    check=False
                )

                if result.returncode != 0:
                    logger.error(f"Finish attempt {finish_tries + 1} failed: {result.stderr}")
                    return ClaudeCodeResponse(
                        content="",
                        raw_output=result.stderr,
                        tool_calls=[],
                        success=False,
                        error=f"Command failed: {result.stderr}"
                    )

                response = ClaudeCodeResponse.from_json(result.stdout)
                last_response = response

                total_cost += response.cost
                logger.debug(f"Finish attempt {finish_tries + 1} complete: cost=${response.cost:.4f}, total=${total_cost:.4f}")

                # Check if task is finished
                if response.is_finished:
                    logger.info(f"Task finished after {finish_tries + 1} finish attempts. Total cost: ${total_cost:.4f}")
                    return response

                finish_tries += 1
            except Exception as e:
                logger.error(f"Exception in finish attempt {finish_tries + 1}: {e}")
                return ClaudeCodeResponse(
                    content="",
                    raw_output=str(e),
                    tool_calls=[],
                    success=False,
                    error=str(e)
                )

        if not last_response.is_finished:
            logger.warning(f"Task still not finished after {max_finish_tries} attempts. Returning last response.")

        logger.info(f"Returning final response. Total cost: ${total_cost:.4f}")
        return last_response

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
        logger.debug(f"Saved session state to {state_path} (session_id={session_id})")

    @classmethod
    def load_session_state(cls, state_file: Union[str, Path]) -> tuple["ClaudeCodeSession", str]:
        """Load a saved session state.

        Args:
            state_file: Path to the state file

        Returns:
            Tuple of (ClaudeCodeSession, session_id)
        """
        state_path = Path(state_file)
        logger.debug(f"Loading session state from {state_path}")

        state = json.loads(state_path.read_text())
        session_id = state["session_id"]

        logger.debug(f"Loaded state: model={state['model']}, session_id={session_id}")

        session = cls(
            model=state["model"],
            allowed_tools=state.get("allowed_tools", []),
            disallowed_tools=state.get("disallowed_tools", []),
            working_dir=state.get("working_dir")
        )

        return session, session_id