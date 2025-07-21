"""Runner functions for AI workflows. Used by CLI."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Workflows are passed from CLI, not imported here
from .core import ClaudeNotAvailableError, WorkflowExecutionError

logger = logging.getLogger(__name__)


def run_ai_workflow(
    workflow_class,
    workflow_name: Optional[str] = None,
    model: str = "sonnet",
    working_dir: Optional[Union[str, Path]] = None,
    resume: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """Run an AI workflow programmatically.

    Args:
        workflow_class: The workflow class to instantiate and run
        workflow_name: Optional name for logging (defaults to workflow_class.name)
        model: Claude model to use (default: "sonnet")
        working_dir: Working directory for Claude session
        resume: Whether to resume from previous state
        **kwargs: Workflow-specific arguments passed to workflow constructor

    Returns:
        Dict containing workflow results

    Raises:
        RuntimeError: If Claude CLI is not available
        ValueError: If workflow class is invalid
        Exception: Any exception from workflow execution

    Example:
        >>> from wake_ai import TestWorkflow, AuditWorkflow
        >>> 
        >>> # Run a simple test workflow
        >>> results = run_ai_workflow(TestWorkflow)

        >>> # Run an audit workflow with specific parameters
        >>> results = run_ai_workflow(
        ...     AuditWorkflow,
        ...     model="opus",
        ...     scope_files=["contracts/Token.sol", "contracts/Vault.sol"],
        ...     context_docs=["docs/spec.md"],
        ...     focus_areas=["reentrancy", "access-control"]
        ... )
    """
    # Get workflow name
    if workflow_name is None:
        workflow_name = getattr(workflow_class, 'name', workflow_class.__name__)

    # Set up working directory
    if working_dir is None:
        working_dir = Path.cwd()
    else:
        working_dir = Path(working_dir)

    # Extract tool configuration
    allowed_tools = kwargs.pop("allowed_tools", None)
    disallowed_tools = kwargs.pop("disallowed_tools", None)
    execution_dir = kwargs.pop("execution_dir", None)
    cleanup_working_dir = kwargs.pop("cleanup_working_dir", None)

    # All remaining kwargs go to the workflow
    init_args = {
        "model": model,
        "working_dir": working_dir,
        "execution_dir": execution_dir,
        "allowed_tools": allowed_tools,
        "disallowed_tools": disallowed_tools,
        "cleanup_working_dir": cleanup_working_dir
    }
    init_args.update(kwargs)

    # Initialize workflow with all provided arguments
    try:
        workflow = workflow_class(**init_args)
    except TypeError as e:
        # If workflow doesn't accept some arguments, try with minimal args
        logger.warning(f"Workflow initialization with full args failed: {e}")
        logger.warning(f"Attempting with minimal args. Unused args: {list(kwargs.keys())}")
        workflow = workflow_class(model=model, working_dir=working_dir)

    logger.info(f"Running {workflow_name} workflow with model {model}, working_dir: {workflow.working_dir}")

    # Override state directory if provided
    if working_dir:
        workflow.working_dir = Path(working_dir)
        workflow.working_dir.mkdir(parents=True, exist_ok=True)

    # Execute workflow
    logger.debug(f"Executing {workflow_name} workflow (resume={resume})")
    try:
        results = workflow.execute(resume=resume)
        logger.debug(f"Workflow {workflow_name} completed successfully")
        return results
    except ClaudeNotAvailableError:
        # Re-raise as is for clear error message
        raise
    except Exception as e:
        logger.error(f"Workflow {workflow_name} failed: {e}")
        raise WorkflowExecutionError(workflow_name, str(e), e)


def run_ai_workflow_by_name(
    workflow_name: str,
    workflows_dict: Dict[str, Any],
    model: str = "sonnet",
    working_dir: Optional[Union[str, Path]] = None,
    resume: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """Run an AI workflow by name using a workflows dictionary.
    
    This is a convenience function for CLI usage where workflows are looked up by name.
    
    Args:
        workflow_name: Name of the workflow to run
        workflows_dict: Dictionary mapping workflow names to workflow classes
        model: Claude model to use (default: "sonnet")
        working_dir: Working directory for Claude session  
        resume: Whether to resume from previous state
        **kwargs: Workflow-specific arguments
        
    Returns:
        Dict containing workflow results
    """
    workflow_class = workflows_dict.get(workflow_name)
    if not workflow_class:
        available = ", ".join(workflows_dict.keys())
        raise ValueError(f"Unknown workflow: {workflow_name}. Available workflows: {available}")
    
    return run_ai_workflow(
        workflow_class,
        workflow_name=workflow_name,
        model=model,
        working_dir=working_dir,
        resume=resume,
        **kwargs
    )