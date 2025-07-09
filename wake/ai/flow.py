"""Multi-step AI workflow orchestration."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime

from .claude import ClaudeCodeSession, ClaudeCodeResponse
from .templates import TEMPLATES


@dataclass
class WorkflowStep:
    """Definition of a single workflow step."""
    
    name: str
    prompt_template: str
    tools: Optional[List[str]] = None
    validator: Optional[Callable[[ClaudeCodeResponse], bool]] = None
    max_retries: int = 3
    success_criteria: Optional[str] = None
    context_keys: List[str] = field(default_factory=list)
    
    def format_prompt(self, context: Dict[str, Any]) -> str:
        """Format the prompt template with context."""
        # Extract only the needed context keys
        prompt_context = {k: v for k, v in context.items() if k in self.context_keys}
        return self.prompt_template.format(**prompt_context)
    
    def validate_response(self, response: ClaudeCodeResponse) -> bool:
        """Validate the response meets success criteria."""
        if not response.success:
            return False
        
        if self.validator:
            return self.validator(response)
        
        # Default validation - just check if we got content
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "context": self.context,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowState":
        """Create state from dictionary."""
        state = cls(
            current_step=data.get("current_step", 0),
            completed_steps=data.get("completed_steps", []),
            context=data.get("context", {}),
            errors=data.get("errors", [])
        )
        
        if data.get("started_at"):
            state.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            state.completed_at = datetime.fromisoformat(data["completed_at"])
        
        return state


class AIWorkflow(ABC):
    """Base class for AI workflows."""
    
    def __init__(
        self,
        name: str,
        session: Optional[ClaudeCodeSession] = None,
        state_dir: Optional[Union[str, Path]] = None
    ):
        """Initialize workflow.
        
        Args:
            name: Workflow name
            session: Claude Code session to use
            state_dir: Directory for saving workflow state
        """
        self.name = name
        self.session = session or ClaudeCodeSession()
        self.state_dir = Path(state_dir) if state_dir else Path(".wake-ai/workflows")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.steps: List[WorkflowStep] = []
        self.state = WorkflowState()
        self._setup_steps()
    
    @abstractmethod
    def _setup_steps(self):
        """Setup workflow steps. Must be implemented by subclasses."""
        pass
    
    def add_step(
        self,
        name: str,
        prompt_template: str,
        tools: Optional[List[str]] = None,
        validator: Optional[Callable[[ClaudeCodeResponse], bool]] = None,
        context_keys: Optional[List[str]] = None
    ):
        """Add a step to the workflow."""
        step = WorkflowStep(
            name=name,
            prompt_template=prompt_template,
            tools=tools,
            validator=validator,
            context_keys=context_keys or []
        )
        self.steps.append(step)
    
    def execute(
        self,
        context: Optional[Dict[str, Any]] = None,
        resume: bool = False,
        interactive: bool = False
    ) -> Dict[str, Any]:
        """Execute the workflow.
        
        Args:
            context: Initial context for the workflow
            resume: Resume from saved state
            interactive: Allow interactive steps
            
        Returns:
            Final workflow results
        """
        # Initialize or resume state
        if resume:
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
                response = self._execute_step(step, interactive)
                
                # Validate response
                if step.validate_response(response):
                    self.state.completed_steps.append(step.name)
                    self.state.responses[step.name] = response
                    self._update_context(step.name, response)
                    self.state.current_step += 1
                    
                    # Save state after each successful step
                    self._save_state()
                else:
                    # Handle validation failure
                    self._handle_step_failure(step, response, "Validation failed")
                    
            except Exception as e:
                self._handle_step_failure(step, None, str(e))
        
        # Mark completion
        self.state.completed_at = datetime.now()
        self._save_state()
        
        return self._prepare_results()
    
    def _execute_step(
        self,
        step: WorkflowStep,
        interactive: bool = False
    ) -> ClaudeCodeResponse:
        """Execute a single workflow step."""
        # Update session tools if needed
        if step.tools:
            self.session.allowed_tools = step.tools
        
        # Format prompt with current context
        prompt = step.format_prompt(self.state.context)
        
        # Execute query
        if interactive:
            # For interactive steps, we'd start an interactive session
            # For now, we'll use non-interactive mode
            return self.session.query(prompt, non_interactive=True)
        else:
            return self.session.query(prompt, non_interactive=True)
    
    def _update_context(self, step_name: str, response: ClaudeCodeResponse):
        """Update workflow context after a step."""
        # Store step output in context
        self.state.context[f"{step_name}_output"] = response.content
        
        # Extract any structured data from response
        if response.tool_calls:
            self.state.context[f"{step_name}_tools"] = response.tool_calls
        
        # Allow subclasses to add custom context updates
        self._custom_context_update(step_name, response)
    
    def _custom_context_update(self, step_name: str, response: ClaudeCodeResponse):
        """Hook for subclasses to update context."""
        pass
    
    def _handle_step_failure(
        self,
        step: WorkflowStep,
        response: Optional[ClaudeCodeResponse],
        error: str
    ):
        """Handle step execution failure."""
        self.state.errors.append({
            "step": step.name,
            "error": error,
            "response": response.raw_output if response else None,
            "timestamp": datetime.now().isoformat()
        })
        
        # For now, we'll stop on failure
        # Could implement retry logic here
        raise RuntimeError(f"Step '{step.name}' failed: {error}")
    
    def _prepare_results(self) -> Dict[str, Any]:
        """Prepare final workflow results."""
        return {
            "workflow": self.name,
            "completed_steps": self.state.completed_steps,
            "context": self.state.context,
            "errors": self.state.errors,
            "duration": (
                (self.state.completed_at - self.state.started_at).total_seconds()
                if self.state.started_at and self.state.completed_at
                else None
            )
        }
    
    def _save_state(self):
        """Save workflow state to disk."""
        state_file = self.state_dir / f"{self.name}_state.json"
        state_file.write_text(json.dumps(self.state.to_dict(), indent=2))
    
    def _load_state(self):
        """Load workflow state from disk."""
        state_file = self.state_dir / f"{self.name}_state.json"
        if state_file.exists():
            data = json.loads(state_file.read_text())
            self.state = WorkflowState.from_dict(data)


# Pre-built workflows

class CodeAnalysisWorkflow(AIWorkflow):
    """Workflow for analyzing codebase structure."""
    
    def _setup_steps(self):
        self.add_step(
            name="explore_structure",
            prompt_template=TEMPLATES["CODEBASE_ANALYSIS"],
            tools=["read", "search", "grep"],
            context_keys=["directory", "focus_areas"]
        )
        
        self.add_step(
            name="identify_patterns",
            prompt_template="""Based on the codebase analysis:
            1. Identify common design patterns used
            2. List architectural decisions
            3. Find potential improvements
            
            Previous analysis: {explore_structure_output}""",
            tools=["read", "grep"],
            context_keys=["explore_structure_output"]
        )
        
        self.add_step(
            name="generate_report",
            prompt_template="""Generate a comprehensive report including:
            1. Codebase overview
            2. Key findings from pattern analysis
            3. Recommended improvements
            
            Structure analysis: {explore_structure_output}
            Pattern analysis: {identify_patterns_output}""",
            tools=[],
            context_keys=["explore_structure_output", "identify_patterns_output"]
        )


class RefactoringWorkflow(AIWorkflow):
    """Workflow for guided refactoring."""
    
    def _setup_steps(self):
        self.add_step(
            name="analyze_target",
            prompt_template="""Analyze the target for refactoring:
            Target: {target}
            Goal: {goal}
            
            1. Understand current implementation
            2. Identify refactoring opportunities
            3. Check for dependencies""",
            tools=["read", "grep", "search"],
            context_keys=["target", "goal"]
        )
        
        self.add_step(
            name="plan_refactoring",
            prompt_template="""Create a detailed refactoring plan:
            Target: {target}
            Goal: {goal}
            Analysis: {analyze_target_output}
            
            Include:
            1. Step-by-step changes
            2. Risk assessment
            3. Testing strategy""",
            tools=[],
            context_keys=["target", "goal", "analyze_target_output"]
        )
        
        self.add_step(
            name="implement_changes",
            prompt_template="""Implement the refactoring plan:
            Plan: {plan_refactoring_output}
            
            Make changes carefully and incrementally.""",
            tools=["read", "write", "edit"],
            context_keys=["plan_refactoring_output"]
        )
        
        self.add_step(
            name="verify_changes",
            prompt_template="""Verify the refactoring:
            1. Check that changes meet the goal
            2. Ensure no functionality is broken
            3. Run any available tests
            
            Changes made: {implement_changes_output}""",
            tools=["read", "bash"],
            context_keys=["implement_changes_output"]
        )