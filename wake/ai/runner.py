"""Runner functions for AI workflows. Used by CLI."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from .workflows import AVAILABLE_WORKFLOWS
from .exceptions import ClaudeNotAvailableError, WorkflowExecutionError

logger = logging.getLogger(__name__)


def run_ai_workflow(
    workflow_name: str,
    model: str = "sonnet",
    working_dir: Optional[Union[str, Path]] = None,
    resume: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """Run an AI workflow programmatically.

    Args:
        workflow_name: Name of the workflow to run (e.g., "audit", "test")
        model: Claude model to use (default: "sonnet")
        working_dir: Working directory for Claude session
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

    # Extract tool configuration
    allowed_tools = kwargs.pop("allowed_tools", None)
    disallowed_tools = kwargs.pop("disallowed_tools", None)

    # All remaining kwargs go to the workflow
    init_args = {
        "model": model,
        "working_dir": working_dir,
        "allowed_tools": allowed_tools,
        "disallowed_tools": disallowed_tools
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

    # Override state directory if provided
    if working_dir:
        workflow.working_dir = Path(working_dir)
        workflow.working_dir.mkdir(parents=True, exist_ok=True)

    # Execute workflow
    logger.info(f"Executing {workflow_name} workflow (resume={resume})")
    try:
        results = workflow.execute(resume=resume)
        logger.info(f"Workflow {workflow_name} completed successfully")
        return results
    except ClaudeNotAvailableError:
        # Re-raise as is for clear error message
        raise
    except Exception as e:
        logger.error(f"Workflow {workflow_name} failed: {e}")
        raise WorkflowExecutionError(workflow_name, str(e), e)