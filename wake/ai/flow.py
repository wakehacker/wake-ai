"""Base workflow infrastructure for AI workflows.

Available tools for Claude Code (from https://docs.anthropic.com/en/docs/claude-code/settings):

Tools requiring permission (must be explicitly allowed):
- Bash: Executes shell commands in your environment
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
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from datetime import datetime
import re

from .claude import ClaudeCodeSession, ClaudeCodeResponse

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class WorkflowStep:
    """Definition of a single workflow step.

    Args:
        name: Step name
        prompt_template: Prompt template with {context_var} placeholders
        tools: List of allowed tools for this step (overrides session defaults)
        disallowed_tools: List of disallowed tools for this step (overrides session defaults)
        validator: Optional validation function returning (success, errors)
        max_cost: Maximum cost allowed for initial attempt
        max_retry_cost: Maximum cost for retry attempts (defaults to max_cost)
        max_retries: Maximum number of retries if validation fails
    """

    name: str
    prompt_template: str
    tools: Optional[List[str]] = None
    disallowed_tools: Optional[List[str]] = None
    validator: Optional[Callable[[ClaudeCodeResponse], Tuple[bool, List[str]]]] = None
    max_cost: Optional[float] = None
    max_retry_cost: Optional[float] = None
    max_retries: int = 3

    def format_prompt(self, context: Dict[str, Any]) -> str:
        """Format the prompt template with context."""
        logger.debug(f"Formatting prompt for step '{self.name}' with context keys: {list(context.keys())}")

        # Warn if there are context keys that are not in the context
        prompt_context_keys = re.findall(r"\{([^}]+)\}", self.prompt_template)
        for key in prompt_context_keys:
            if key not in context:
                logger.warning(f"Context key '{key}' used in step '{self.name}' not provided")

        return self.prompt_template.format(**context)

    def validate_response(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        """Validate the response meets success criteria.

        Returns:
            Tuple of (success: bool, errors: List[str])
        """
        if not response.success:
            logger.warning(f"Step '{self.name}' response failed: {response.error}")
            return (False, [response.error or "Response failed"])

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
class WorkflowState:
    """State tracking for workflow execution."""

    current_step: int = 0
    completed_steps: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    responses: Dict[str, ClaudeCodeResponse] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AIWorkflow(ABC):
    """Base class for fixed AI workflows."""

    # Default tools for the workflow (can be overridden by subclasses)
    allowed_tools: List[str] = []
    disallowed_tools: List[str] = []

    def __init__(
        self,
        name: str,
        session: Optional[ClaudeCodeSession] = None,
        model: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
        execution_dir: Optional[Union[str, Path]] = None,
        allowed_tools: Optional[List[str]] = None,
        disallowed_tools: Optional[List[str]] = None
    ):
        """Initialize workflow.

        Args:
            name: Workflow name
            session: Claude session to use (optional)
            model: Model name to create session with (ignored if session provided)
            working_dir: Directory for AI to work in (default: .wake/ai/<session-id>/)
            execution_dir: Directory where Claude CLI is executed (default: current directory)
            allowed_tools: Override default allowed tools
            disallowed_tools: Override default disallowed tools
        """
        self.name = name

        # Set up working directory
        if working_dir is not None:
            self.working_dir = Path(working_dir)
        else:
            # Generate session ID for working directory
            from datetime import datetime
            import random
            import string
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            session_id = f"{timestamp}_{suffix}"
            self.working_dir = Path.cwd() / ".wake" / "ai" / session_id

        # Create working directory
        self.working_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created working directory: {self.working_dir}")

        # Use provided tools or class defaults
        tools_allowed = allowed_tools if allowed_tools is not None else self.allowed_tools
        tools_disallowed = disallowed_tools if disallowed_tools is not None else self.disallowed_tools

        # Set execution directory
        exec_dir = Path(execution_dir) if execution_dir else Path.cwd()

        # Handle session creation
        if session is not None:
            self.session = session
        elif model is not None:
            self.session = ClaudeCodeSession(
                model=model,
                working_dir=self.working_dir,
                execution_dir=exec_dir,
                allowed_tools=tools_allowed,
                disallowed_tools=tools_disallowed
            )
        else:
            # Default to creating a session with default model
            self.session = ClaudeCodeSession(
                working_dir=self.working_dir,
                execution_dir=exec_dir,
                allowed_tools=tools_allowed,
                disallowed_tools=tools_disallowed
            )

        self.steps: List[WorkflowStep] = []
        self.state = WorkflowState()
        self._setup_steps()
        logger.info(f"Workflow '{name}' initialized with {len(self.steps)} steps")

        # Add working directory to context
        self.state.context["working_dir"] = str(self.working_dir)

    @abstractmethod
    def _setup_steps(self):
        """Setup workflow steps. Must be implemented by subclasses."""
        pass

    def add_step(self, name: str, prompt_template: str, tools: Optional[List[str]] = None,
                 disallowed_tools: Optional[List[str]] = None,
                 max_cost: Optional[float] = None,
                 validator: Optional[Callable[[ClaudeCodeResponse], Tuple[bool, List[str]]]] = None,
                 max_retries: int = 3,
                 max_retry_cost: Optional[float] = None):
        """Add a step to the workflow."""
        step = WorkflowStep(
            name=name,
            prompt_template=prompt_template,
            tools=tools,
            disallowed_tools=disallowed_tools,
            max_cost=max_cost,
            validator=validator,
            max_retries=max_retries,
            max_retry_cost=max_retry_cost
        )
        self.steps.append(step)
        logger.debug(f"Added step '{name}' to workflow (tools: {tools}, max_cost: {max_cost})")

    def execute(self, context: Optional[Dict[str, Any]] = None, resume: bool = False) -> Dict[str, Any]:
        """Execute the workflow."""
        logger.info(f"Starting workflow '{self.name}' execution (resume={resume})")

        if resume and (self.working_dir / f"{self.name}_state.json").exists():
            logger.debug(f"Resuming workflow from saved state")
            self._load_state()
        else:
            self.state = WorkflowState()
            self.state.context = context or {}
            # Add working directory to context
            self.state.context["working_dir"] = str(self.working_dir)
            self.state.started_at = datetime.now()
            logger.info(f"Starting fresh workflow execution with working_dir: {self.working_dir}")

        # Execute steps
        while self.state.current_step < len(self.steps):
            step = self.steps[self.state.current_step]
            logger.info(f"Executing step {self.state.current_step + 1}/{len(self.steps)}: '{step.name}'")

            try:
                # Execute step with retry logic
                retry_count = 0
                validation_errors = []
                response = None

                # Save original tools
                original_allowed = self.session.allowed_tools
                original_disallowed = self.session.disallowed_tools

                while retry_count <= step.max_retries:
                    # Set tools if specified (step overrides workflow defaults)
                    if step.tools is not None:
                        self.session.allowed_tools = step.tools
                        logger.debug(f"Set allowed tools for step '{step.name}': {step.tools}")

                    if step.disallowed_tools is not None:
                        self.session.disallowed_tools = step.disallowed_tools
                        logger.debug(f"Set disallowed tools for step '{step.name}': {step.disallowed_tools}")

                    # Execute query
                    if retry_count == 0:
                        # First attempt - use original prompt
                        prompt = step.format_prompt(self.state.context)
                        logger.debug(f"Executing query for step '{step.name}'")

                        # Continue session only if this is not the first step
                        should_continue = self.state.current_step > 0

                        if step.max_cost:
                            logger.info(f"Querying with cost limit ${step.max_cost} for step '{step.name}' (continue_session={should_continue})")
                            response = self.session.query_with_cost(prompt, step.max_cost, continue_session=should_continue)
                        else:
                            logger.info(f"Querying step '{step.name}' (continue_session={should_continue})")
                            response = self.session.query(prompt, continue_session=should_continue)
                    else:
                         # Retry attempt - add error correction prompt
                        error_prompt = "The following errors occurred, please fix them:\n"
                        for error in validation_errors:
                            error_prompt += f"- {error}\n"
                        prompt = error_prompt
                        logger.info(f"Retrying step '{step.name}' (attempt {retry_count}/{step.max_retries}) with error correction")

                        # Always continue session for retries
                        if step.max_retry_cost:
                            logger.info(f"Querying retry with cost limit ${step.max_retry_cost} for step '{step.name}'")
                            response = self.session.query_with_cost(prompt, step.max_retry_cost, continue_session=True)
                        else:
                            logger.info(f"Querying retry for step '{step.name}'")
                            response = self.session.query(prompt, continue_session=True)

                    # Log response details
                    logger.info(f"Step '{step.name}' completed with cost ${response.cost:.4f}, {response.num_turns} turns")
                    logger.debug(f"Response: {response.content}")

                    # Log session ID after first step's first query
                    if self.state.current_step == 0 and retry_count == 0 and response.session_id:
                        logger.info(f"Claude session ID: {response.session_id}")

                    # Validate response
                    success, validation_errors = step.validate_response(response)

                    if success:
                        # Validation passed
                        self.state.completed_steps.append(step.name)
                        self.state.responses[step.name] = response
                        self.state.context[f"{step.name}_output"] = response.content
                        self._custom_context_update(step.name, response)
                        self.state.current_step += 1
                        self._save_state()
                        logger.info(f"Step '{step.name}' completed successfully after {retry_count} retries")
                        break
                    else:
                        # Validation failed
                        logger.warning(f"Step '{step.name}' validation failed: {validation_errors}")

                        if retry_count >= step.max_retries:
                            # Max retries reached
                            error_msg = f"Step '{step.name}' validation failed after {step.max_retries} retries. Errors: {'; '.join(validation_errors)}"
                            raise RuntimeError(error_msg)

                        retry_count += 1

                # Restore original tools after step completes
                self.session.allowed_tools = original_allowed
                self.session.disallowed_tools = original_disallowed

            except Exception as e:
                # Restore original tools even on error
                self.session.allowed_tools = original_allowed
                self.session.disallowed_tools = original_disallowed

                logger.error(f"Error in step '{step.name}': {str(e)}")
                self.state.errors.append({
                    "step": step.name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                raise

        self.state.completed_at = datetime.now()
        results = self._prepare_results()
        logger.info(f"Workflow '{self.name}' completed successfully in {results.get('duration', 0):.2f} seconds")
        return results

    def _custom_context_update(self, step_name: str, response: ClaudeCodeResponse):
        """Hook for subclasses to update context."""
        pass

    def _prepare_results(self) -> Dict[str, Any]:
        """Prepare final workflow results."""
        return {
            "workflow": self.name,
            "responses": {step_name: response.content for step_name, response in self.state.responses.items()},
            "completed_steps": self.state.completed_steps,
            "errors": self.state.errors,
            "duration": (
                (self.state.completed_at - self.state.started_at).total_seconds()
                if self.state.started_at and self.state.completed_at
                else None
            ),
            "total_cost": sum(response.cost for response in self.state.responses.values())
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
            "context": self.state.context,
            "errors": self.state.errors
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
        self.state.context = data["context"]
        self.state.errors = data["errors"]
        logger.debug(f"Loaded state: step {self.state.current_step}/{len(self.steps)}, completed: {len(self.state.completed_steps)}")

    def add_context(self, key: str, value: Any):
        """Add a context variable."""
        self.state.context[key] = value

    def get_context(self, key: str) -> Any:
        """Get a context variable."""
        return self.state.context.get(key)

    def get_context_keys(self) -> List[str]:
        """Get all context keys."""
        return list(self.state.context.keys())
