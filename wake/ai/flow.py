"""Base workflow infrastructure for AI workflows."""

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
    """Definition of a single workflow step."""

    name: str
    prompt_template: str
    tools: Optional[List[str]] = None
    validator: Optional[Callable[[ClaudeCodeResponse], bool]] = None
    max_cost: Optional[float] = None

    def format_prompt(self, context: Dict[str, Any]) -> str:
        """Format the prompt template with context."""
        logger.debug(f"Formatting prompt for step '{self.name}' with context keys: {list(context.keys())}")

        # Warn if there are context keys that are not in the context
        prompt_context_keys = re.findall(r"\{([^}]+)\}", self.prompt_template)
        for key in prompt_context_keys:
            if key not in context:
                logger.warning(f"Context key '{key}' used in step '{self.name}' not provided")

        return self.prompt_template.format(**context)

    def validate_response(self, response: ClaudeCodeResponse) -> bool:
        """Validate the response meets success criteria."""
        if not response.success:
            logger.warning(f"Step '{self.name}' response failed: {response.error}")
            return False

        if self.validator:
            result = self.validator(response)
            logger.debug(f"Step '{self.name}' custom validator returned: {result}")
            return result

        return bool(response.content)


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

    def __init__(
        self,
        name: str,
        session: Optional[ClaudeCodeSession] = None,
        model: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None
    ):
        """Initialize workflow.

        Args:
            name: Workflow name
            session: Claude session to use (optional)
            model: Model name to create session with (ignored if session provided)
            working_dir: Directory for AI to work in (default: .wake/ai/<session-id>/)
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

        # Handle session creation
        if session is not None:
            self.session = session
        elif model is not None:
            self.session = ClaudeCodeSession(model=model, working_dir=self.working_dir)
        else:
            # Default to creating a session with default model
            self.session = ClaudeCodeSession(working_dir=self.working_dir)

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
                 max_cost: Optional[float] = None,
                 validator: Optional[Callable[[ClaudeCodeResponse], bool]] = None):
        """Add a step to the workflow."""
        step = WorkflowStep(
            name=name,
            prompt_template=prompt_template,
            tools=tools,
            max_cost=max_cost,
            validator=validator
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
                # Execute step
                if step.tools:
                    self.session.allowed_tools = step.tools
                    logger.debug(f"Set allowed tools for step '{step.name}': {step.tools}")

                prompt = step.format_prompt(self.state.context)
                logger.debug(f"Executing query for step '{step.name}'")

                if step.max_cost:
                    logger.info(f"Querying with cost limit ${step.max_cost} for step '{step.name}'")
                    response = self.session.query_with_cost(prompt, step.max_cost)
                else:
                    response = self.session.query(prompt)

                # Log response details
                logger.info(f"Step '{step.name}' completed with cost ${response.cost:.4f}, {response.num_turns} turns")
                logger.debug(f"Response: {response.content}")

                # Validate and update state
                if step.validate_response(response):
                    self.state.completed_steps.append(step.name)
                    self.state.responses[step.name] = response
                    self.state.context[f"{step.name}_output"] = response.content
                    self._custom_context_update(step.name, response)
                    self.state.current_step += 1
                    self._save_state()
                    logger.info(f"Step '{step.name}' completed successfully")
                else:
                    raise RuntimeError(f"Step '{step.name}' validation failed")

            except Exception as e:
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