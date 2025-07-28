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
import logging
import re
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from jinja2 import Environment, StrictUndefined, Template, meta
from pydantic import BaseModel

from ..results import AIResult
from .claude import ClaudeCodeResponse, ClaudeCodeSession

# Set up logging
logger = logging.getLogger(__name__)


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
    skipped_steps: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    responses: Dict[str, ClaudeCodeResponse] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cumulative_cost: float = 0.0


class AIWorkflow(ABC):
    """Base class for fixed AI workflows."""

    # Default cleanup behavior (can be overridden by subclasses)
    cleanup_working_dir: bool = True

    def __init__(
        self,
        name: str,
        result_class: Optional[Type[AIResult]] = None,
        session: Optional[ClaudeCodeSession] = None,
        model: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
        execution_dir: Optional[Union[str, Path]] = None,
        allowed_tools: Optional[List[str]] = None,
        disallowed_tools: Optional[List[str]] = None,
        cleanup_working_dir: Optional[bool] = None
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
        """
        self.name = name
        self.result_class = result_class

        # Set cleanup behavior (use instance value if provided, else class default)
        self.cleanup_working_dir = cleanup_working_dir if cleanup_working_dir is not None else self.__class__.cleanup_working_dir

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
                disallowed_tools=tools_disallowed
            )
        else:
            # Default to creating a session with default model
            self.session = ClaudeCodeSession(
                working_dir=self.working_dir,
                execution_dir=self.execution_dir,
                allowed_tools=tools_allowed,
                disallowed_tools=tools_disallowed
            )

        self.steps: List[WorkflowStep] = []
        self.state = WorkflowState()
        self._dynamic_generators: Dict[str, Callable[[ClaudeCodeResponse, Dict[str, Any]], List[WorkflowStep]]] = {}

        self._setup_steps()
        logger.debug(f"Workflow '{name}' initialized with {len(self.steps)} steps")

        # Add working directory to context
        self.add_context("working_dir", str(self.working_dir))

    @abstractmethod
    def _setup_steps(self):
        """Setup workflow steps. Must be implemented by subclasses."""
        pass

    def add_step(self, name: str, prompt_template: str, allowed_tools: Optional[List[str]] = None,
                 disallowed_tools: Optional[List[str]] = None,
                 max_cost: Optional[float] = None,
                 validator: Optional[Callable[[ClaudeCodeResponse], Tuple[bool, List[str]]]] = None,
                 max_retries: int = 3,
                 max_retry_cost: Optional[float] = None,
                 continue_session: bool = False,
                 condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
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
            after_step: Optional step name after which to insert this step. If None, appends to end.
        """
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
            condition=condition
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

    def execute(self, context: Optional[Dict[str, Any]] = None, resume: bool = False) -> Tuple[Dict[str, Any], AIResult]:
        """Execute the workflow.

        Returns:
            Tuple of (raw results dict, formatted AIResult object)
        """
        logger.debug(f"Starting workflow '{self.name}' execution (resume={resume})")

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
                    self.state.current_step += 1
                    self._save_state()
                    continue

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
                            logger.debug(f"Querying with cost limit ${step.max_cost} for step '{step.name}' (continue_session={should_continue})")
                            response = self.session.query_with_cost(prompt, step.max_cost, continue_session=should_continue)
                        else:
                            logger.debug(f"Querying step '{step.name}' (continue_session={should_continue})")
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
                            logger.debug(f"Querying retry with cost limit ${step.max_retry_cost} for step '{step.name}'")
                            response = self.session.query_with_cost(prompt, step.max_retry_cost, continue_session=True)
                        else:
                            logger.debug(f"Querying retry for step '{step.name}'")
                            response = self.session.query(prompt, continue_session=True)

                    # Log response details
                    retry_msg = f" after {retry_count} retries" if retry_count > 0 else ""
                    logger.info(f"Step '{step.name}' completed{retry_msg} - cost: ${response.cost:.4f}, turns: {response.num_turns}")
                    logger.debug(f"Response: {response.content}")

                    # Log session ID after first step's first query
                    if self.state.current_step == 0 and retry_count == 0 and response.session_id:
                        logger.debug(f"Claude session ID: {response.session_id}")

                    # Validate response
                    success, validation_errors = step.validate_response(response)

                    if success:
                        # Validation passed
                        self.state.completed_steps.append(step.name)
                        self.state.responses[step.name] = response
                        self.state.context[f"{step.name}_output"] = response.content
                        self._custom_context_update(step.name, response)
                        
                        # Update cumulative cost
                        self.state.cumulative_cost += response.cost

                        # Call step-specific post-processing if defined (used internally)
                        if step._post_hook:
                            step._post_hook(self, response)

                        # Call workflow-level post-step hook
                        self._post_step_hook(step, response)

                        self.state.current_step += 1
                        self._save_state()
                        # Step completion already logged above with retry info
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
        logger.info(f"Workflow '{self.name}' completed successfully in {results.get('duration', 0):.2f} seconds (total cost: ${self.state.cumulative_cost:.4f})")

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
            "total_cost": self.state.cumulative_cost
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
            "cumulative_cost": self.state.cumulative_cost
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
        self.state.skipped_steps = data.get("skipped_steps", [])  # Backwards compatibility
        self.state.context = data["context"]
        self.state.errors = data["errors"]
        self.state.cumulative_cost = data.get("cumulative_cost", 0.0)  # Backwards compatibility
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
    
    def get_cumulative_cost(self) -> float:
        """Get the cumulative cost of all steps executed so far."""
        return self.state.cumulative_cost

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
