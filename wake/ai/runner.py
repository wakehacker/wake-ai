"""Runner functions for AI workflows."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from .claude import ClaudeCodeSession
from .workflows import AVAILABLE_WORKFLOWS
from .utils import validate_claude_cli

logger = logging.getLogger(__name__)


def run_ai_workflow(
    workflow_name: str,
    model: str = "sonnet",
    working_dir: Optional[Union[str, Path]] = None,
    state_dir: Optional[Union[str, Path]] = None,
    resume: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """Run an AI workflow programmatically.

    Args:
        workflow_name: Name of the workflow to run (e.g., "audit", "test")
        model: Claude model to use (default: "sonnet")
        working_dir: Working directory for Claude session
        state_dir: Directory to store workflow state
        resume: Whether to resume from previous state
        **kwargs: Workflow-specific arguments passed to workflow constructor

    Returns:
        Dict containing workflow results

    Raises:
        RuntimeError: If Claude CLI is not available
        ValueError: If workflow name is not found
        Exception: Any exception from workflow execution

    Example:
        >>> # Run a simple test workflow
        >>> results = run_ai_workflow("test")
        
        >>> # Run an audit workflow with specific parameters
        >>> results = run_ai_workflow(
        ...     "audit",
        ...     model="opus",
        ...     scope_files=["contracts/Token.sol", "contracts/Vault.sol"],
        ...     context_docs=["docs/spec.md"],
        ...     focus_areas=["reentrancy", "access-control"]
        ... )
        
        >>> # Run a custom workflow with its own parameters
        >>> results = run_ai_workflow(
        ...     "custom_workflow",
        ...     custom_param1="value1",
        ...     custom_param2=["list", "of", "values"]
        ... )
    """
    # Validate Claude CLI is available
    validate_claude_cli()
    
    # Get workflow class
    workflow_class = AVAILABLE_WORKFLOWS.get(workflow_name)
    if not workflow_class:
        available = ", ".join(AVAILABLE_WORKFLOWS.keys())
        raise ValueError(f"Unknown workflow: {workflow_name}. Available workflows: {available}")
    
    # Set up working directory
    if working_dir is None:
        working_dir = Path.cwd()
    else:
        working_dir = Path(working_dir)
    
    logger.info(f"Running {workflow_name} workflow with model {model}")
    
    # Extract session-specific kwargs
    verbose = kwargs.pop("verbose", False)
    
    # Initialize Claude session
    session = ClaudeCodeSession(
        model=model,
        working_dir=working_dir,
        verbose=verbose
    )
    
    # All remaining kwargs go to the workflow
    init_args = {"session": session}
    init_args.update(kwargs)
    
    # Initialize workflow with all provided arguments
    try:
        workflow = workflow_class(**init_args)
    except TypeError as e:
        # If workflow doesn't accept some arguments, try with just session
        logger.warning(f"Workflow initialization with full args failed: {e}")
        logger.warning(f"Attempting with session only. Unused args: {list(kwargs.keys())}")
        workflow = workflow_class(session=session)
    
    # Override state directory if provided
    if state_dir:
        workflow.state_dir = Path(state_dir)
        workflow.state_dir.mkdir(parents=True, exist_ok=True)
    
    # Execute workflow
    logger.info(f"Executing {workflow_name} workflow (resume={resume})")
    try:
        results = workflow.execute(resume=resume)
        logger.info(f"Workflow {workflow_name} completed successfully")
        return results
    except Exception as e:
        logger.error(f"Workflow {workflow_name} failed: {e}")
        raise


def run_simple_audit(
    model: str = "sonnet",
    **kwargs
) -> Dict[str, Any]:
    """Convenience function to run a security audit.

    Args:
        model: Claude model to use
        **kwargs: Audit-specific arguments (scope_files, context_docs, focus_areas, etc.)

    Returns:
        Dict containing audit results

    Example:
        >>> # Audit entire codebase
        >>> results = run_simple_audit()
        
        >>> # Audit specific files
        >>> results = run_simple_audit(
        ...     scope_files=["contracts/Token.sol"],
        ...     context_docs=["docs/spec.md"],
        ...     focus_areas=["reentrancy"]
        ... )
    """
    return run_ai_workflow(
        "audit",
        model=model,
        **kwargs
    )


def run_test_workflow(model: str = "sonnet") -> Dict[str, Any]:
    """Run the simple test workflow.

    Args:
        model: Claude model to use

    Returns:
        Dict containing test results

    Example:
        >>> results = run_test_workflow()
        >>> print(results["completed_steps"])
        ['say_hi', 'ask_how_are_you']
    """
    return run_ai_workflow("test", model=model)