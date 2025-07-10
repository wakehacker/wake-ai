"""Base workflow infrastructure for AI workflows."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from .claude import ClaudeCodeSession, ClaudeCodeResponse


@dataclass
class WorkflowStep:
    """Definition of a single workflow step."""

    name: str
    prompt_template: str
    tools: Optional[List[str]] = None
    validator: Optional[Callable[[ClaudeCodeResponse], bool]] = None
    max_cost: Optional[float] = None
    context_keys: List[str] = field(default_factory=list)

    def format_prompt(self, context: Dict[str, Any]) -> str:
        """Format the prompt template with context."""
        prompt_context = {k: v for k, v in context.items() if k in self.context_keys}
        return self.prompt_template.format(**prompt_context)

    def validate_response(self, response: ClaudeCodeResponse) -> bool:
        """Validate the response meets success criteria."""
        if not response.success:
            return False

        if self.validator:
            return self.validator(response)

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
        state_dir: Optional[Path] = None
    ):
        self.name = name
        self.session = session or ClaudeCodeSession()
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.steps: List[WorkflowStep] = []
        self.state = WorkflowState()
        self._setup_steps()

    @abstractmethod
    def _setup_steps(self):
        """Setup workflow steps. Must be implemented by subclasses."""
        pass

    def add_step(self, name: str, prompt_template: str, tools: Optional[List[str]] = None, context_keys: Optional[List[str]] = None):
        """Add a step to the workflow."""
        step = WorkflowStep(
            name=name,
            prompt_template=prompt_template,
            tools=tools,
            context_keys=context_keys or []
        )
        self.steps.append(step)

    def execute(self, context: Optional[Dict[str, Any]] = None, resume: bool = False) -> Dict[str, Any]:
        """Execute the workflow."""
        if resume and (self.state_dir / f"{self.name}_state.json").exists():
            self._load_state()
        else:
            self.state = WorkflowState()
            self.state.context = context or {}
            self.state.started_at = datetime.now()

        # Execute steps
        while self.state.current_step < len(self.steps):
            step = self.steps[self.state.current_step]

            try:
                # Execute step
                if step.tools:
                    self.session.allowed_tools = step.tools

                prompt = step.format_prompt(self.state.context)
                if step.max_cost:
                    response = self.session.query_with_cost(prompt, step.max_cost)
                else:
                    response = self.session.query(prompt)

                # Validate and update state
                if step.validate_response(response):
                    self.state.completed_steps.append(step.name)
                    self.state.responses[step.name] = response
                    self.state.context[f"{step.name}_output"] = response.content
                    self._custom_context_update(step.name, response)
                    self.state.current_step += 1
                    self._save_state()
                else:
                    raise RuntimeError(f"Step '{step.name}' validation failed")

            except Exception as e:
                self.state.errors.append({
                    "step": step.name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                raise

        self.state.completed_at = datetime.now()
        return self._prepare_results()

    def _custom_context_update(self, step_name: str, response: ClaudeCodeResponse):
        """Hook for subclasses to update context."""
        pass

    def _prepare_results(self) -> Dict[str, Any]:
        """Prepare final workflow results."""
        return {
            "workflow": self.name,
            "completed_steps": self.state.completed_steps,
            "errors": self.state.errors,
            "duration": (
                (self.state.completed_at - self.state.started_at).total_seconds()
                if self.state.started_at and self.state.completed_at
                else None
            )
        }

    def _save_state(self):
        """Save workflow state."""
        state_data = {
            "current_step": self.state.current_step,
            "completed_steps": self.state.completed_steps,
            "context": self.state.context,
            "errors": self.state.errors
        }
        state_file = self.state_dir / f"{self.name}_state.json"
        state_file.write_text(json.dumps(state_data, indent=2))

    def _load_state(self):
        """Load workflow state."""
        state_file = self.state_dir / f"{self.name}_state.json"
        data = json.loads(state_file.read_text())
        self.state.current_step = data["current_step"]
        self.state.completed_steps = data["completed_steps"]
        self.state.context = data["context"]
        self.state.errors = data["errors"]