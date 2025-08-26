"""Base workflow infrastructure for AI workflows.

Available tools for Claude Code (from https://docs.anthropic.com/en/docs/claude-code/settings):

Tools requiring permission (must be explicitly allowed):
- Bash: Executes shell commands in your environment
  - Can be restricted to specific commands using syntax: "Bash(command *)"
  - Examples: "Bash(git *)", "Bash(npm install)", "Bash(wake *)"
- Edit: Makes targeted edits to specific files
- MultiEdit: Performs multiple edits on a single file atomically
- NotebookEdit: Modifies Jupyter notebook cells
- WebFetch: Fetches content from a specified URL
- WebSearch: Performs web searches with domain filtering
- Write: Creates or overwrites files

Tools not requiring permission (always available):
- Glob: Finds files based on pattern matching
- Grep: Searches for patterns in file contents
- LS: Lists files and directories
- NotebookRead: Reads and displays Jupyter notebook contents
- Read: Reads the contents of files
- Task: Runs a sub-agent to handle complex, multi-step tasks
- TodoWrite: Creates and manages structured task lists
"""

import json
import re
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from functools import wraps
from contextlib import contextmanager

import rich_click as click
from jinja2 import Environment, StrictUndefined, Template, meta
from pydantic import BaseModel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

from ..results import AIResult, MessageResult
from .claude import ClaudeCodeResponse, ClaudeCodeSession
from ..utils.logging import get_logger

# Set up logging
logger = get_logger(__name__)


def require_initialized(func):
    """Decorator to ensure __init__ was called on AIWorkflow instances."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if isinstance(self, AIWorkflow) and not getattr(self, '_init_called', False):
            raise RuntimeError(
                f"AIWorkflow.__init__() was not called. "
                f"Make sure to call super().__init__(...) in {self.__class__.__name__}.__init__()"
            )
        return func(self, *args, **kwargs)
    return wrapper


@dataclass
class WorkflowStep:
    """Definition of a single workflow step.

    Args:
        name: Step name
        prompt_template: Prompt template with {context_var} placeholders
        allowed_tools: List of allowed tools for this step (overrides session defaults)
                       Can restrict Bash to specific commands: ["Bash(git *)", "Bash(npm install)"]
        disallowed_tools: List of disallowed tools for this step (overrides session defaults)
        validator: Optional validation function returning (success, errors)
        max_cost: Maximum cost allowed for initial attempt
        max_retry_cost: Maximum cost for retry attempts (defaults to max_cost)
        max_retries: Maximum number of retries if validation fails
        continue_session: Whether to continue the Claude session from previous step (default: False)
        condition: Optional function that takes context and returns bool. Step is skipped if False.
        model: Optional model name to use for this step (must not be higher capability than workflow model)
        _post_hook: Internal post-processing function (not exposed to users)
    """

    name: str
    prompt_template: str
    allowed_tools: Optional[List[str]] = None
    disallowed_tools: Optional[List[str]] = None
    validator: Optional[Callable[[ClaudeCodeResponse], Tuple[bool, List[str]]]] = None
    max_cost: Optional[float] = None
    max_retry_cost: Optional[float] = None
    max_retries: int = 3
    continue_session: bool = False
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    model: Optional[str] = None
    _post_hook: Optional[Callable[['AIWorkflow', ClaudeCodeResponse], None]] = field(default=None, repr=False)

    def format_prompt(self, context: Dict[str, Any]) -> str:
        """Format the prompt template with context using Jinja2."""
        logger.debug(f"Formatting prompt for step '{self.name}' with context keys: {list(context.keys())}")

        # Create Jinja2 environment with strict undefined to catch missing variables
        env = Environment(undefined=StrictUndefined)

        # Parse the template to find all variables
        ast = env.parse(self.prompt_template)
        prompt_context_keys = meta.find_undeclared_variables(ast)

        # Warn if there are context keys that are not in the context
        for key in prompt_context_keys:
            if key not in context:
                logger.warning(f"Context key '{key}' used in step '{self.name}' not provided")

        # Render the template
        template = env.from_string(self.prompt_template)
        return template.render(**context)

    def validate_response(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        """Validate the response meets success criteria.

        Returns:
            Tuple of (success: bool, errors: List[str])
        """
        if not response.success:
            logger.debug(f"Step '{self.name}' Claude query failed: {response.content}")
            return (False, [response.content or "Claude query failed"])

        if self.validator:
            result = self.validator(response)
            logger.debug(f"Step '{self.name}' custom validator returned: {result}")
            return result

        # Default validation - just check if content exists
        if response.content:
            return (True, [])
        else:
            return (False, ["Response has no content"])


@dataclass
class StepExecutionInfo:
    """Information about a single step execution."""
    name: str
    turns: int
    cost: float
    duration: float  # in seconds
    retries: int
    status: str  # "completed", "skipped", "failed", "running"
    start_time: Optional[datetime] = None  # Track when step started


@dataclass
class WorkflowState:
    """State tracking for workflow execution."""

    current_step: int = 0
    completed_steps: List[str] = field(default_factory=list)
    skipped_steps: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    responses: Dict[str, ClaudeCodeResponse] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cumulative_cost: float = 0.0
    progress_percentage: float = 0.0
    step_info: Dict[int, StepExecutionInfo] = field(default_factory=dict)  # Key is step index


class AIWorkflow(ABC):
    """Base class for fixed AI workflows."""


    name: str
    result_class: Type[AIResult]
    cleanup_working_dir: bool
    working_dir: Path
    execution_dir: Path
    session: ClaudeCodeSession
    steps: List[WorkflowStep]
    state: WorkflowState
    _dynamic_generators: Dict[str, Callable[[ClaudeCodeResponse, Dict[str, Any]], List[WorkflowStep]]]
    _init_called: bool
    _console: Console

    def __init__(
        self,
        name: Optional[str] = None,
        result_class: Optional[Type[AIResult]] = None,
        session: Optional[ClaudeCodeSession] = None,
        model: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
        execution_dir: Optional[Union[str, Path]] = None,
        allowed_tools: Optional[List[str]] = None,
        disallowed_tools: Optional[List[str]] = None,
        cleanup_working_dir: Optional[bool] = None,
        show_progress: Optional[bool] = None,
        console: Optional[Console] = None
    ):
        """Initialize workflow.

        Args:
            name: Workflow name
            result_class: Result class to use for formatting output (default: MessageResult)
            session: Claude session to use (optional)
            model: Model name to create session with (ignored if session provided)
            working_dir: Directory for AI to work in (default: .wake/ai/<session-id>/)
            execution_dir: Directory where Claude CLI is executed (default: current directory)
            allowed_tools: Override default allowed tools
                          Can restrict Bash to specific commands: ["Bash(git *)", "Bash(wake *)"]
            disallowed_tools: Override default disallowed tools
            cleanup_working_dir: Whether to remove working_dir after completion (default: True)
            show_progress: Whether to show progress bar during execution (default: True)
            console: Rich Console instance for coordinated output (optional)
        """
        ctx = click.get_current_context(silent=True)
        if ctx is None:
            cli = {}
        else:
            ctx.ensure_object(dict)
            cli = ctx.obj

        if "name" not in cli and name is None:
            raise ValueError("Workflow name is required")

        self.name = cli.get("name", name)
        self.result_class = result_class or MessageResult

        if model is None:
            model = cli.get("model", None)
        if working_dir is None:
            working_dir = cli.get("working_dir", None)
        if execution_dir is None:
            execution_dir = cli.get("execution_dir", None)

        # Set cleanup behavior (use instance value if provided, else class default)
        self.cleanup_working_dir = cleanup_working_dir if cleanup_working_dir is not None else cli.get("cleanup_working_dir", True)

        # Set progress behavior (use instance value if provided, else CLI or default)
        self._show_progress = show_progress if show_progress is not None else cli.get("show_progress", True)

        # Set console for coordinated output
        if console is not None:
            self._console = console
        else:
            cli_console = cli.get("console")
            if cli_console is not None:
                self._console = cli_console
            else:
                from rich.console import Console
                self._console = Console()

        # Set up working directory
        if working_dir is not None:
            self.working_dir = Path(working_dir).resolve()
        else:
            # Generate session ID for working directory
            import random
            import string
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            session_id = f"{timestamp}_{suffix}"
            self.working_dir = Path.cwd() / ".wake" / "ai" / session_id

        # Create working directory
        self.working_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created working directory: {self.working_dir}")

        # Define default allowed tools if not provided
        # IMPORTANT: Claude Code's tool permissions have limitations:
        # - Write/Edit/MultiEdit cannot be restricted to specific paths
        # - Bash patterns only match command prefixes, not file paths
        # - The AI is restricted to the launch directory by default
        default_allowed_tools = [
            # Read-only tools (always safe)
            "Read", "Grep", "Glob", "LS", "Task", "TodoWrite",

            # Wake MCP
            "mcp__wake",

            # Write tools (needed for results - cannot be path-restricted)
            f"Write(/{self.working_dir}/**)", f"Edit(/{self.working_dir}/**)", f"MultiEdit(/{self.working_dir}/**)",

            # Essential bash commands for codebase analysis
            "Bash(wake:*)",      # Wake framework commands
            "Bash(cd:*)",        # Directory navigation
            "Bash(pwd)",         # Print working directory
            "Bash(ls:*)",        # List files (though LS tool is preferred)
            "Bash(find:*)",      # Find files by pattern
            "Bash(tree:*)",      # Directory structure visualization
            "Bash(diff:*)",      # Compare files
            "Bash(mkdir:*)",     # Create directories
            "Bash(mv:*)",        # Move/rename files
            "Bash(cp:*)",        # Copy files
        ]

        # Default disallowed tools (subclasses can override)
        default_disallowed_tools = []

        # Use provided tools or defaults
        tools_allowed = allowed_tools if allowed_tools is not None else default_allowed_tools
        tools_disallowed = disallowed_tools if disallowed_tools is not None else default_disallowed_tools

        # Set execution directory
        self.execution_dir = Path(execution_dir) if execution_dir else Path.cwd()

        # Handle session creation
        if session is not None:
            self.session = session
        elif model is not None:
            self.session = ClaudeCodeSession(
                model=model,
                working_dir=self.working_dir,
                execution_dir=self.execution_dir,
                allowed_tools=tools_allowed,
                disallowed_tools=tools_disallowed,
                console=self._console
            )
        else:
            # Default to creating a session with default model
            self.session = ClaudeCodeSession(
                working_dir=self.working_dir,
                execution_dir=self.execution_dir,
                allowed_tools=tools_allowed,
                disallowed_tools=tools_disallowed,
                console=self._console
            )

        self.steps: List[WorkflowStep] = []
        self.state = WorkflowState()
        self._dynamic_generators: Dict[str, Callable[[ClaudeCodeResponse, Dict[str, Any]], List[WorkflowStep]]] = {}

        # Progress tracking
        self._status_context = None  # console.status context manager
        self._current_step_name: Optional[str] = None
        self._progress_hook: Optional[Callable[[float, str], None]] = None

        # Mark that __init__ was called
        self._init_called = True

    @classmethod
    def _get_model_rank(cls, model: str) -> int:
        """Get the hierarchy rank of a model."""
        normalized = model.lower().strip()
        if "opus" in normalized:
            return 2
        elif "sonnet" in normalized:
            return 1
        else:
            return 2  # Unknown model - assume opus level

    @classmethod
    def _validate_model_downgrade(cls, workflow_model: str, step_model: str) -> bool:
        """Check if step model is allowed (only downgrades permitted)."""
        return cls._get_model_rank(step_model) <= cls._get_model_rank(workflow_model)


    @abstractmethod
    def _setup_steps(self):
        """Setup workflow steps. Must be implemented by subclasses."""
        pass

    @require_initialized
    def add_step(self, name: str, prompt_template: str, allowed_tools: Optional[List[str]] = None,
                 disallowed_tools: Optional[List[str]] = None,
                 max_cost: Optional[float] = None,
                 validator: Optional[Callable[[ClaudeCodeResponse], Tuple[bool, List[str]]]] = None,
                 max_retries: int = 3,
                 max_retry_cost: Optional[float] = None,
                 continue_session: bool = False,
                 condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
                 model: Optional[str] = None,
                 after_step: Optional[str] = None):
        """Add a step to the workflow.

        Args:
            name: Step name
            prompt_template: Prompt template with {{context_var}} placeholders
            allowed_tools: List of allowed tools for this step (overrides session defaults)
                       Can restrict Bash to specific commands: ["Bash(git *)", "Bash(npm install)"]
            disallowed_tools: List of disallowed tools for this step
            max_cost: Maximum cost allowed for initial attempt
            validator: Optional validation function returning (success, errors)
            max_retries: Maximum number of retries if validation fails
            max_retry_cost: Maximum cost for retry attempts (defaults to max_cost)
            continue_session: Whether to continue the Claude session from previous step (default: False)
            condition: Optional function that takes context and returns bool. Step is skipped if False.
            model: Optional model name to use for this step (must not be higher capability than workflow model)
            after_step: Optional step name after which to insert this step. If None, appends to end.
        """
        # Validate model if specified
        if model and hasattr(self.session, 'model') and self.session.model:
            if not self._validate_model_downgrade(self.session.model, model):
                logger.warning(f"Cannot upgrade from '{self.session.model}' to '{model}' - using workflow model instead")
                model = None

        step = WorkflowStep(
            name=name,
            prompt_template=prompt_template,
            allowed_tools=allowed_tools,
            disallowed_tools=disallowed_tools,
            max_cost=max_cost,
            validator=validator,
            max_retries=max_retries,
            max_retry_cost=max_retry_cost,
            continue_session=continue_session,
            condition=condition,
            model=model
        )

        if after_step is None:
            # Append to end (default behavior)
            self.steps.append(step)
        else:
            # Find the step and insert after it
            insert_pos = None
            for i, existing_step in enumerate(self.steps):
                if existing_step.name == after_step:
                    insert_pos = i + 1
                    break

            if insert_pos is None:
                raise ValueError(f"Step '{after_step}' not found in workflow")

            self.steps.insert(insert_pos, step)

        logger.debug(f"Added step '{name}' to workflow (allowed_tools: {allowed_tools}, max_cost: {max_cost}, after: {after_step})")

    @require_initialized
    def add_dynamic_steps(self, name: str, generator: Callable[[ClaudeCodeResponse, Dict[str, Any]], List[WorkflowStep]],
                         after_step: Optional[str] = None):
        """Add a dynamic step generator that creates new steps at runtime.

        The generator function will be called after the specified step executes,
        and should return a list of WorkflowStep objects to be inserted into the workflow.

        Args:
            name: Name identifier for this dynamic step generator
            generator: Function that takes (response, context) and returns list of WorkflowSteps
            after_step: Step name after which to generate new steps. If None, generates after the last step.
        """
        # If no after_step specified, use the last step in the current list
        if after_step is None and self.steps:
            after_step = self.steps[-1].name
        elif after_step is None and not self.steps:
            raise ValueError("Cannot add dynamic steps to empty workflow. Add at least one regular step first.")

        # Verify the after_step exists
        if after_step not in [s.name for s in self.steps]:
            raise ValueError(f"Step '{after_step}' not found in workflow")

        # Warn if this step already has a dynamic generator
        if after_step in self._dynamic_generators:
            logger.warning(
                f"Step '{after_step}' already has a dynamic generator registered. "
                f"The new generator '{name}' will override the previous one."
            )

        self._dynamic_generators[after_step] = generator
        logger.debug(f"Added dynamic step generator '{name}' after step '{after_step}'")

    @require_initialized
    def execute(self, context: Optional[Dict[str, Any]] = None, resume: bool = False) -> Tuple[Dict[str, Any], AIResult]:
        """Execute the workflow.

        Returns:
            Tuple of (raw results dict, formatted AIResult object)
        """
        self._setup_steps()
        logger.debug(f"Workflow '{self.name}' initialized with {len(self.steps)} steps")

        # Add working directory to context
        self.add_context("working_dir", str(self.working_dir))

        logger.debug(f"Starting workflow '{self.name}' execution (resume={resume})")

        # Use status display context manager for the entire execution
        with self._status_display():
            # Initialize progress tracking
            try:
                self.update_progress("Initializing workflow...")
            except Exception as e:
                logger.debug(f"Failed to update progress: {e}")

            if resume and (self.working_dir / f"{self.name}_state.json").exists():
                logger.info(f"Resuming workflow from saved state in: {self.working_dir / f'{self.name}_state.json'}")
                self._load_state()
            else:
                self.state = WorkflowState()
                self.state.context = context or {}
                # Add working directory to context
                self.state.context["working_dir"] = str(self.working_dir)
                self.state.started_at = datetime.now()
                if resume:
                    logger.info(f"No saved state found, starting fresh workflow execution")
                else:
                    logger.debug(f"Starting fresh workflow execution")

            # Execute steps
            while self.state.current_step < len(self.steps):
                step = self.steps[self.state.current_step]

                # Check if step should be skipped based on condition
                if step.condition is not None:
                    should_execute = step.condition(self.state.context)
                    if not should_execute:
                        logger.info(f"Skipping step {self.state.current_step + 1}/{len(self.steps)}: '{step.name}' (condition not met)")
                        self.state.skipped_steps.append(step.name)
                        # Record skipped step info
                        self.state.step_info[self.state.current_step] = StepExecutionInfo(
                            name=step.name,
                            cost=0.0,
                            turns=0,
                            duration=0.0,
                            retries=0,
                            status="skipped"
                        )
                        # Update status display with skipped step
                        self._update_status_display()
                        self.state.current_step += 1
                        self._save_state()
                        continue

                logger.info(f"Executing step {self.state.current_step + 1}/{len(self.steps)}: '{step.name}'")

                # Update progress message at step start (percentage based on completed steps)
                try:
                    step_msg = f"Starting '{step.name}' ({self.state.current_step + 1}/{len(self.steps)})"
                    self.update_progress(step_msg)
                except Exception as e:
                    logger.debug(f"Failed to update progress: {e}")

                try:
                    # Track step execution start time
                    step_start_time = datetime.now()

                    # Mark step as running and update display
                    self.state.step_info[self.state.current_step] = StepExecutionInfo(
                        name=step.name,
                        cost=0.0,
                        turns=0,
                        duration=0.0,
                        retries=0,
                        status="running",
                        start_time=step_start_time
                    )
                    self._update_status_display()

                    # Execute step with retry logic
                    retry_count = 0
                    validation_errors = []
                    response = None
                    step_total_cost = 0.0
                    step_total_turns = 0

                    # Save original tools and model
                    original_allowed = self.session.allowed_tools
                    original_disallowed = self.session.disallowed_tools
                    original_model = getattr(self.session, 'model', None)

                    # Change model for this step if specified
                    if step.model is not None and step.model != original_model:
                        logger.debug(f"Switching from model '{original_model}' to '{step.model}' for step '{step.name}'")
                        self.session.model = step.model

                    while retry_count <= step.max_retries:
                        # Set tools if specified (step overrides workflow defaults)
                        if step.allowed_tools is not None:
                            self.session.allowed_tools = step.allowed_tools
                            logger.debug(f"Set allowed tools for step '{step.name}': {step.allowed_tools}")

                        if step.disallowed_tools is not None:
                            self.session.disallowed_tools = step.disallowed_tools
                            logger.debug(f"Set disallowed tools for step '{step.name}': {step.disallowed_tools}")

                        # Execute query
                        if retry_count == 0:
                            # Call pre-step hook on first attempt only
                            self._pre_step_hook(step)

                            # First attempt - use original prompt
                            prompt = step.format_prompt(self.state.context)

                            # Continue session only if step explicitly requests it
                            should_continue = step.continue_session

                            if step.max_cost:
                                logger.debug(f"Querying with cost limit ${step.max_cost} for step '{step.name}' (continue_session={should_continue}, model={getattr(self.session, 'model', 'default')})")
                                response = self.query_with_cost(prompt, step.max_cost, continue_session=should_continue, step_info=self.state.step_info[self.state.current_step])
                            else:
                                logger.debug(f"Querying step '{step.name}' (continue_session={should_continue}, model={getattr(self.session, 'model', 'default')})")
                                response = self.session.query(prompt, continue_session=should_continue)
                        else:
                            # Retry attempt - add error correction prompt
                            error_prompt = "The following errors occurred, please fix them:\n"
                            for error in validation_errors:
                                error_prompt += f"- {error}\n"
                            prompt = error_prompt
                            logger.info(f"Retrying step '{step.name}' (attempt {retry_count}/{step.max_retries}) - previous attempt failed validation")

                            # Update progress message for retry (don't change percentage)
                            try:
                                retry_msg = f"Retrying '{step.name}' (attempt {retry_count}/{step.max_retries})"
                                self.update_progress_message(retry_msg)
                            except Exception as e:
                                logger.debug(f"Failed to update progress message: {e}")

                            # Always continue session for retries
                            if step.max_retry_cost:
                                logger.debug(f"Querying retry with cost limit ${step.max_retry_cost} for step '{step.name}' (model={getattr(self.session, 'model', 'default')})")
                                response = self.query_with_cost(prompt, step.max_retry_cost, continue_session=True, step_info=self.state.step_info[self.state.current_step])
                            else:
                                logger.debug(f"Querying retry for step '{step.name}' (model={getattr(self.session, 'model', 'default')})")
                                response = self.session.query(prompt, continue_session=True)

                        # Log session ID after first step's first query
                        if self.state.current_step == 0 and retry_count == 0 and response.session_id:
                            logger.debug(f"Claude session ID: {response.session_id}")

                        # Update progress message for validation (don't change percentage)
                        try:
                            if retry_count == 0:
                                validation_msg = f"Validating '{step.name}' output"
                            else:
                                validation_msg = f"Validating retry of '{step.name}' (attempt {retry_count}/{step.max_retries})"
                            self.update_progress_message(validation_msg)
                        except Exception as e:
                            logger.debug(f"Failed to update progress message: {e}")

                        # Update cumulative cost and step totals
                        self.state.cumulative_cost += response.cost
                        step_total_cost += response.cost
                        step_total_turns += response.num_turns

                        # Validate response
                        success, validation_errors = step.validate_response(response)

                        if success:
                            # Validation passed - log successful completion with total cost/turns
                            retry_msg = f" after {retry_count} retries" if retry_count > 0 else ""
                            logger.info(f"Step '{step.name}' completed{retry_msg} - cost: ${step_total_cost:.4f}, turns: {step_total_turns}")
                            logger.debug(f"Response: {response.content}")

                            # Calculate step duration
                            step_duration = (datetime.now() - step_start_time).total_seconds()

                            # Record step execution info
                            self.state.step_info[self.state.current_step] = StepExecutionInfo(
                                name=step.name,
                                cost=step_total_cost,
                                turns=step_total_turns,
                                duration=step_duration,
                                retries=retry_count,
                                status="completed"
                            )

                            # Update live display with completed step
                            self._update_status_display()

                            # Update workflow state
                            self.state.completed_steps.append(step.name)
                            self.state.responses[step.name] = response
                            self.state.context[f"{step.name}_output"] = response.content
                            self._custom_context_update(step.name, response)

                            # Call step-specific post-processing if defined (used internally)
                            if step._post_hook:
                                step._post_hook(self, response)

                            # Call workflow-level post-step hook
                            self._post_step_hook(step, response)

                            self.state.current_step += 1
                            self._save_state()

                            # Update progress after step completion
                            try:
                                step_msg = f"Completed step '{step.name}' ({len(self.state.completed_steps)}/{len(self.steps)})"
                                self.update_progress(step_msg)
                            except Exception as e:
                                logger.debug(f"Failed to update progress: {e}")

                            break
                        else:
                            # Validation failed - log query completion but note validation failure
                            attempt_msg = f"attempt {retry_count + 1}" if retry_count > 0 else "initial attempt"
                            logger.debug(f"Step '{step.name}' {attempt_msg} completed but validation failed - cost: ${response.cost:.4f}, turns: {response.num_turns}")
                            logger.warning(f"Step '{step.name}' validation failed: {validation_errors}")

                            if retry_count >= step.max_retries:
                                # Max retries reached
                                logger.error(f"Step '{step.name}' failed after {step.max_retries} retries - final errors: {validation_errors}")
                                error_msg = f"Step '{step.name}' validation failed after {step.max_retries} retries. Errors: {'; '.join(validation_errors)}"
                                raise RuntimeError(error_msg)

                            retry_count += 1

                    # Restore original tools and model after step completes
                    self.session.allowed_tools = original_allowed
                    self.session.disallowed_tools = original_disallowed
                    if original_model is not None:
                        self.session.model = original_model

                except Exception as e:
                    # Restore original tools and model even on error
                    self.session.allowed_tools = original_allowed
                    self.session.disallowed_tools = original_disallowed
                    if original_model is not None:
                        self.session.model = original_model

                    logger.error(f"Error in step '{step.name}': {str(e)}")
                    self.state.errors.append({
                        "step": step.name,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                    raise

            self.state.completed_at = datetime.now()
            results = self._prepare_results()
            if results.get('duration') is not None:
                logger.info(f"Workflow '{self.name}' completed successfully in {results.get('duration')} seconds (total cost: ${self.state.cumulative_cost:.4f})")
            else:
                logger.info(f"Workflow '{self.name}' completed successfully (total cost: ${self.state.cumulative_cost:.4f})")

            # Complete progress tracking
            try:
                self.update_progress("Workflow completed!", force_percentage=1.0)
            except Exception as e:
                logger.debug(f"Failed to update final progress: {e}")

            # Format results before cleanup
            formatted_results = self.format_results(results)

            # Clean up working directory if configured
            if self.cleanup_working_dir and self.working_dir.exists():
                try:
                    shutil.rmtree(self.working_dir)
                    logger.info(f"Cleaned up working directory: {self.working_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up working directory {self.working_dir}: {e}")
            elif not self.cleanup_working_dir:
                logger.debug(f"Preserving working directory: {self.working_dir}")


        return results, formatted_results


    def query_with_cost(self, prompt: str, cost_limit: float, turn_step: int = 50, continue_session: bool = False, step_info: Optional[StepExecutionInfo] = None) -> ClaudeCodeResponse:
        """Execute queries with cost monitoring and automatic completion.

        Args:
            prompt: The initial prompt to send to Claude
            cost_limit: Maximum cost in USD before attempting to finish
            turn_step: Maximum turns per iteration to control cost increments
            continue_session: Whether to continue the last stored session

        Note:
            Cost enforcement is iterative rather than strict. The system:
            1. Executes queries in chunks of `turn_step` turns
            2. Monitors cumulative cost after each iteration
            3. Continues until cost limit is approached
            4. Attempts graceful completion if task is unfinished

        Returns:
            ClaudeCodeResponse with the final result and total cost
        """
        logger.debug(f"Starting cost-limited query (limit=${cost_limit:.2f}, turn_step={turn_step}, continue_session={continue_session})")

        total_cost = 0.0
        last_response = None
        iteration = 0

        # First query with the initial prompt
        logger.debug(f"Iteration {iteration}: Initial query")

        response = self.session.query(
            prompt=prompt,
            max_turns=turn_step,
            continue_session=continue_session
        )

        if not response.success:
            logger.error(f"Command failed: {response.content}")
            return response

        last_response = response
        # Update total cost and session info from response
        total_cost = response.cost
        if step_info is not None:
            step_info.cost += response.cost
        logger.debug(f"Iteration {iteration} complete: total_cost=${total_cost:.4f}, session_id={response.session_id}")

        # Check if task is already finished
        if response.is_finished:
            logger.debug(f"Task finished in initial query. Total cost: ${total_cost:.4f}")
            return response

        # Continue querying while under cost limit
        while total_cost < cost_limit:
            iteration += 1
            logger.debug(f"Iteration {iteration}: Continuing session (current_cost=${total_cost:.4f}, limit=${cost_limit:.2f})")

            response = self.session.query(
                prompt=f"continue",
                max_turns=turn_step,
                continue_session=True
            )

            # ORIGINAL HANDLING,
            # Case1, the claude code subprocess does not return 0.
            # Case2, the claude code return json but the json is not valid.
            if not response.success:
                logger.error(f"Command failed: {response.content}")
                return response

            # response.session_id == session_id session id will be different even start with --resume <session_id>

            last_response = response
            total_cost += response.cost
            if step_info is not None:
                step_info.cost += response.cost

            if response.is_finished:
                logger.debug(f"Task finished after {iteration} iterations. Total cost: ${total_cost:.4f}")
                return response

            if total_cost >= cost_limit:
                logger.warning(f"Cost limit reached: ${total_cost:.4f} >= ${cost_limit:.2f}")
                break

            logger.debug(f"Iteration {iteration} complete: iteration_cost=${response.cost:.4f}, total_cost=${total_cost:.4f}")


        # Attempt to complete unfinished task within remaining budget
        if not last_response.is_finished:
            logger.warning("Task not finished after reaching cost limit. Attempting to finish...")

        finish_tries = 0
        max_finish_tries = 3
        while finish_tries < max_finish_tries and not last_response.is_finished:
            logger.debug(f"Finish attempt {finish_tries + 1}/{max_finish_tries}")

            prompt = (
                f"You are approaching the cost limit. Please finish the task as quickly "
                f"as possible. This is attempt {finish_tries + 1}/{max_finish_tries}. "
                f"After {max_finish_tries} attempts, the task will be terminated."
            )

            response = self.session.query(
                prompt=prompt,
                max_turns=turn_step,
                # Resume the same session for completion attempt
                continue_session=True
            )


            if not response.success:
                logger.error(f"Command failed: {response.content}")
                return response
            # Return code is not 0, then parse valid output is not possible.
            last_response = response
            total_cost += response.cost
            if step_info is not None:
                step_info.cost += response.cost
            logger.debug(f"Finish attempt {finish_tries + 1} complete: cost=${response.cost:.4f}, total=${total_cost:.4f}")
            # Verify if completion attempt succeeded
            if response.is_finished:
                logger.debug(f"Task finished after {finish_tries + 1} finish attempts. Total cost: ${total_cost:.4f}")
                return response

            finish_tries += 1

        if not last_response.is_finished:
            logger.warning(f"Task still not finished after {max_finish_tries} attempts. Returning last response.")

        logger.debug(f"Returning final response. Total cost: ${total_cost:.4f}")
        return last_response

    def _custom_context_update(self, step_name: str, response: ClaudeCodeResponse):
        """Hook for subclasses to update context."""
        pass

    def _pre_step_hook(self, step: WorkflowStep) -> None:
        """Hook called before each step execution.

        Override in subclasses to implement workflow-level pre-step logic.
        Can modify self.state.context directly if needed.

        Args:
            step: The step about to be executed
        """
        pass

    def _post_step_hook(self, step: WorkflowStep, response: ClaudeCodeResponse) -> None:
        """Hook called after each step execution.

        Override in subclasses to implement workflow-level post-step logic.

        Args:
            step: The step that was executed
            response: Response from Claude
        """
        # Check if this step has a dynamic generator
        if hasattr(self, '_dynamic_generators') and step.name in self._dynamic_generators:
            logger.info(f"Generating dynamic steps after '{step.name}'")
            try:
                # Call the generator function
                generator = self._dynamic_generators[step.name]
                new_steps = generator(response, self.state.context)

                if new_steps:
                    # Insert new steps after the current step
                    insert_pos = self.state.current_step + 1

                    # Insert steps in order
                    for i, new_step in enumerate(new_steps):
                        self.steps.insert(insert_pos + i, new_step)
                        logger.debug(f"Inserted dynamic step '{new_step.name}' at position {insert_pos + i}")

                    logger.info(f"Added {len(new_steps)} dynamic steps. Total steps now: {len(self.steps)}")

                    # Update progress after dynamic steps are added
                    try:
                        dynamic_msg = f"Added {len(new_steps)} dynamic steps"
                        self.update_progress(dynamic_msg)
                    except Exception as e:
                        logger.debug(f"Failed to update progress after dynamic steps: {e}")
                else:
                    logger.debug(f"Dynamic generator for '{step.name}' returned no new steps")

            except Exception as e:
                logger.error(f"Error generating dynamic steps after '{step.name}': {str(e)}")
                self.state.errors.append({
                    "timestamp": datetime.now().isoformat(),
                    "step": step.name,
                    "error": f"Dynamic step generation failed: {str(e)}"
                })
                # Continue execution despite error in dynamic generation

        # Call any subclass implementation
        pass

    def _prepare_results(self) -> Dict[str, Any]:
        """Prepare final workflow results."""
        return {
            "workflow": self.name,
            "responses": {step_name: response.content for step_name, response in self.state.responses.items()},
            "completed_steps": self.state.completed_steps,
            "skipped_steps": self.state.skipped_steps,
            "errors": self.state.errors,
            "duration": (
                (self.state.completed_at - self.state.started_at).total_seconds()
                if self.state.started_at and self.state.completed_at
                else None
            ),
            "total_cost": self.state.cumulative_cost,
            "metadata": [
                {
                    "name": info.name,
                    "cost": info.cost,
                    "status": info.status,
                    "duration": info.duration,
                }
                for info in self.state.step_info.values()
            ]
        }

    @classmethod
    def get_cli_options(cls) -> Dict[str, Any]:
        """Return workflow-specific CLI options.

        Returns:
            Dictionary mapping argument names to their click option configuration.
            Each entry contains the parameters needed for click.option()

        Example:
            {
                "scope": {
                    "param_decls": ["-s", "--scope"],
                    "multiple": True,
                    "type": click.Path(exists=True),
                    "help": "Files to audit"
                }
            }
        """
        return {}

    @classmethod
    def process_cli_args(cls, **kwargs) -> Dict[str, Any]:
        """Process CLI arguments into workflow initialization arguments.

        Args:
            **kwargs: All CLI arguments

        Returns:
            Dictionary of arguments to pass to workflow __init__
        """
        return {}

    def _save_state(self):
        """Save workflow state."""
        state_data = {
            "current_step": self.state.current_step,
            "completed_steps": self.state.completed_steps,
            "skipped_steps": self.state.skipped_steps,
            "context": self.state.context,
            "errors": self.state.errors,
            "cumulative_cost": self.state.cumulative_cost,
            "progress_percentage": self.state.progress_percentage
        }
        state_file = self.working_dir / f"{self.name}_state.json"
        state_file.write_text(json.dumps(state_data, indent=2))
        logger.debug(f"Saved workflow state to {state_file}")

    def _load_state(self):
        """Load workflow state."""
        state_file = self.working_dir / f"{self.name}_state.json"
        logger.debug(f"Loading workflow state from {state_file}")
        data = json.loads(state_file.read_text())
        self.state.current_step = data["current_step"]
        self.state.completed_steps = data["completed_steps"]
        self.state.skipped_steps = data["skipped_steps"]
        self.state.context = data["context"]
        self.state.errors = data["errors"]
        self.state.cumulative_cost = data["cumulative_cost"]
        self.state.progress_percentage = data["progress_percentage"]
        logger.debug(f"Loaded state: step {self.state.current_step}/{len(self.steps)}, completed: {len(self.state.completed_steps)}")

        # Update progress bar if resuming
        try:
            self.update_progress(f"Resumed at step {self.state.current_step + 1}/{len(self.steps)}")
        except Exception as e:
            logger.debug(f"Failed to update progress on resume: {e}")

    @require_initialized
    def add_context(self, key: str, value: Any):
        """Add a context variable."""
        self.state.context[key] = value

    @require_initialized
    def get_context(self, key: str) -> Any:
        """Get a context variable."""
        return self.state.context.get(key)

    @require_initialized
    def get_context_keys(self) -> List[str]:
        """Get all context keys."""
        return list(self.state.context.keys())

    @require_initialized
    def get_cumulative_cost(self) -> float:
        """Get the cumulative cost of all steps executed so far."""
        return self.state.cumulative_cost

    @require_initialized
    def set_progress_hook(self, hook: Optional[Callable[[float, str], None]]) -> None:
        """Set external progress update hook.

        Args:
            hook: Callback function(percentage: float, message: str)
        """
        self._progress_hook = hook

    def _update_status_display(self, force_refresh: bool = True) -> None:
        """Update the status display."""
        if self._status_context:
            try:
                # Update the Live display with fresh content
                self._status_context.update(self._get_status_display())
            except Exception as e:
                logger.debug(f"Failed to update live display: {e}")

    def update_progress_message(self, message: str) -> None:
        """Update only the progress message without changing percentage.

        This is useful for providing status updates during step execution
        (e.g., retries, validation) without moving the progress forward.

        Args:
            message: Progress message to display
        """
        # Update current step name
        self._current_step_name = message

        # Update status display
        self._update_status_display()

        # Call external hook with current percentage if set
        if self._progress_hook:
            try:
                # Use the stored percentage without recalculating
                current_percentage = self.state.progress_percentage
                self._progress_hook(current_percentage, message)
            except Exception as e:
                logger.warning(f"Progress hook failed: {e}")

    @require_initialized
    def update_progress(self, message: str = "", force_percentage: Optional[float] = None) -> None:
        """Update workflow progress.

        Args:
            message: Optional progress message
            force_percentage: Override calculated percentage (0.0-1.0)
        """
        # Calculate progress percentage
        if force_percentage is not None:
            percentage = max(0.0, min(1.0, force_percentage))
        else:
            # Calculate based on completed steps (simple step counting)
            if not self.steps:
                percentage = 0.0
            else:
                total_steps = len(self.steps)
                completed_steps = len(self.state.completed_steps)

                percentage = completed_steps / total_steps if total_steps > 0 else 0.0
                percentage = max(0.0, min(1.0, percentage))

        # Update state
        self.state.progress_percentage = percentage

        # Update current step name
        if message:
            self._current_step_name = message

        # Update status display
        self._update_status_display()

        # Call external hook if set
        if self._progress_hook:
            try:
                self._progress_hook(percentage, message)
            except Exception as e:
                logger.warning(f"Progress hook failed: {e}")

    def _format_duration(self, seconds: float) -> str:
        """Format duration dynamically based on the time scale."""
        days = int(seconds // 86400)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        if days > 0:
            return f"{days:d}d {hours:02d}h {minutes:02d}m {secs:05.2f}s"
        elif hours > 0:
            return f"{hours:d}h {minutes:02d}m {secs:05.2f}s"
        elif minutes > 0:
            return f"{minutes:d}m {secs:05.2f}s"
        else:
            return f"{secs:.2f}s"

    def _get_status_display(self) -> Panel:
        """Build the status display with table and progress."""
        table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 1), width=80)
        table.add_column("Step", no_wrap=True, width=40)
        table.add_column("Time", justify="right", width=15)
        table.add_column("Cost", justify="right", width=12)

        # Add rows for each step
        for i, step in enumerate(self.steps):
            if i in self.state.step_info:
                info = self.state.step_info[i]

                # Determine row style based on status
                if info.status == "completed":
                    row_style = "green"
                    step_name = f"✓ {step.name}"
                elif info.status == "skipped":
                    row_style = "yellow"
                    step_name = f"○ {step.name}"
                elif info.status == "running":
                    row_style = "bright_cyan"
                    step_name = f"⟳ {step.name}"
                else:
                    row_style = "red"
                    step_name = f"✗ {step.name}"

                # Format duration (show live time for running steps)
                if info.status == "running" and info.start_time:
                    # Calculate current running time
                    running_time = (datetime.now() - info.start_time).total_seconds()
                    duration = self._format_duration(running_time)
                elif info.duration > 0:
                    duration = self._format_duration(info.duration)
                else:
                    duration = "-"

                # Format cost
                cost = f"${info.cost:.4f}" if info.cost > 0 else "-"

                table.add_row(step_name, duration, cost, style=row_style)
            else:
                # Step not yet executed
                table.add_row(f"  {step.name}", "-", "-", style="dim")

        # Add total row
        if self.state.step_info:
            total_cost = sum(info.cost for info in self.state.step_info.values())

            # Calculate total duration including running steps
            total_duration = 0.0
            for info in self.state.step_info.values():
                if info.status == "running" and info.start_time:
                    # Add current running time for active steps
                    total_duration += (datetime.now() - info.start_time).total_seconds()
                else:
                    total_duration += info.duration

            table.add_section()
            table.add_row(
                "[bold]Total[/bold]",
                f"[bold]{self._format_duration(total_duration)}[/bold]",
                f"[bold]${total_cost:.4f}[/bold]"
            )

        # Add current progress info
        progress_pct = int(self.state.progress_percentage * 100)
        status_msg = f"Progress: {progress_pct}%"
        if self._current_step_name:
            status_msg = f"{status_msg} - {self._current_step_name}"

        # Return panel with table and status
        return Panel(table, title=status_msg, border_style="blue", width=84)

    @contextmanager
    def _status_display(self):
        """Context manager for status display."""
        # Start the status display
        if self._show_progress and self._console:
            # Use Live display with auto-refresh for real-time updates
            # Use get_renderable parameter for dynamic updates
            self._status_context = Live(
                self._get_status_display(),  # Initial renderable
                refresh_per_second=10,  # Update 10 times per second
                auto_refresh=True,      # Enable automatic refresh
                console=self._console,
                transient=True,        # Keep display after completion
                get_renderable=lambda: self._get_status_display()  # Function to get fresh renderable
            )
            self._status_context.start()
            logger.debug("Started live status display")

        try:
            yield
        finally:
            # Stop the status display and show final summary
            if self._status_context:
                try:
                    # Print the final state of the table before stopping
                    if self._console:
                        # Get the current status display and print it as static content
                        final_display = self._get_status_display()
                        self._console.print(final_display)

                    # Stop the Live display
                    self._status_context.stop()
                except Exception as e:
                    logger.debug(f"Error stopping live display: {e}")
                finally:
                    self._status_context = None
                    logger.debug("Stopped live status display")

    @require_initialized
    def format_results(self, results: Dict[str, Any]) -> AIResult:
        """Convert workflow results to an AIResult object.

        This method uses the result class specified in the constructor
        to parse the working directory and create the appropriate result object.

        Args:
            results: Raw results from workflow execution

        Returns:
            AIResult object that can be printed or exported
        """
        if self.result_class is None:
            # Default to MessageResult if no result class specified
            from ..results import MessageResult
            self.result_class = MessageResult

        return self.result_class.from_working_dir(self.working_dir, results)

    def _extract_json(self, content: str) -> str:
        """Extract JSON from AI response, handling various formats.

        Tries patterns in order:
        1. JSON in code blocks: ```json\n{...}\n```
        2. JSON in generic code blocks: ```\n{...}\n```
        3. Raw JSON: {...} or [...]

        Args:
            content: The response content to extract JSON from

        Returns:
            The extracted JSON string
        """
        # Try JSON in code blocks first
        code_block_match = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', content)
        if code_block_match:
            return code_block_match.group(1).strip()

        # Try raw JSON pattern
        json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', content)
        if json_match:
            return json_match.group(1).strip()

        # Fallback: assume entire content is JSON
        return content.strip()

    def _create_schema_validator(self, schema: Type[BaseModel]) -> Callable[[ClaudeCodeResponse], Tuple[bool, List[str]]]:
        """Create a validator function for the given Pydantic schema.

        Args:
            schema: The Pydantic model to validate against

        Returns:
            A validator function that returns (success, errors)
        """
        def validator(response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
            try:
                # Extract JSON from response
                json_str = self._extract_json(response.content)
                # Parse and validate
                schema.model_validate_json(json_str)
                return (True, [])
            except Exception as e:
                return (False, [f"Schema validation failed: {str(e)}"])
        return validator

    @require_initialized
    def add_extraction_step(
        self,
        after_step: str,
        output_schema: Type[BaseModel],
        name: Optional[str] = None,
        extract_prompt: Optional[str] = None,
        max_cost: float = 0.5,
        context_key: Optional[str] = None
    ):
        """Add an automatic extraction step after a given step.

        This creates a new step that extracts structured data from the previous
        step's output using the provided Pydantic schema.

        Args:
            after_step: Name of the step to extract data from
            output_schema: Pydantic model defining the expected structure
            name: Optional name for the extraction step (defaults to "{after_step}_extract")
            extract_prompt: Optional custom extraction prompt
            max_cost: Maximum cost for extraction (default: 0.5)
            context_key: Optional key to store the extracted data in the context (defaults to "{after_step}_data")
        """
        # Generate default name if not provided
        if name is None:
            name = f"{after_step}_extract"

        if context_key is None:
            context_key = f"{after_step}_data"

        # Generate extraction prompt if not provided
        if extract_prompt is None:
            schema_dict = output_schema.model_json_schema()
            schema_json = json.dumps(schema_dict, indent=2)
            extract_prompt = f"""Extract and format the relevant information from your previous responses as JSON.

Required JSON Schema:
```json
{schema_json}
```

Output ONLY valid JSON matching the schema above. Do not include any additional text, markdown formatting, or code blocks."""

        # Create post-process function for extraction parsing
        def extraction_post_hook(workflow: 'AIWorkflow', response: ClaudeCodeResponse):
            try:
                json_str = workflow._extract_json(response.content)
                parsed_data = output_schema.model_validate_json(json_str)

                # Store parsed data with specified context key
                workflow.state.context[context_key] = parsed_data
                logger.debug(f"Stored parsed data in context as '{context_key}'")
            except Exception as e:
                # This shouldn't happen as validation should have caught it
                logger.error(f"Failed to parse extraction step '{name}' after validation: {e}")

        # Create extraction step with validator and post-process hook
        extraction_step = WorkflowStep(
            name=name,
            prompt_template=extract_prompt,
            continue_session=True,  # Always continue from previous step
            validator=self._create_schema_validator(output_schema),
            max_cost=max_cost,
            max_retries=3,
            _post_hook=extraction_post_hook
        )

        # Find position to insert (right after the target step)
        insert_pos = None
        target_step = None
        for i, step in enumerate(self.steps):
            if step.name == after_step:
                insert_pos = i + 1
                target_step = step
                break

        if insert_pos is None:
            raise ValueError(f"Step '{after_step}' not found in workflow")

        # Warn if target step already has a post hook
        if target_step and target_step._post_hook is not None:
            logger.warning(
                f"Step '{after_step}' already has a _post_hook defined. "
                f"The extraction step will run after '{after_step}', but the existing "
                f"_post_hook on '{after_step}' will still execute. Consider if this is intended."
            )

        # Insert extraction step
        self.steps.insert(insert_pos, extraction_step)
        logger.debug(f"Added extraction step '{name}' after '{after_step}'")
