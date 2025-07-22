"""Runner functions for AI workflows. Used by CLI."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Workflows are passed from CLI, not imported here
from .core import ClaudeNotAvailableError, WorkflowExecutionError
from wake_ai.core.flow import AIWorkflow

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
        Dict containing both raw and formatted results:
        - "raw": Raw workflow results dict
        - "formatted": Formatted AIResult object

    Raises:
        RuntimeError: If Claude CLI is not available
        ValueError: If workflow class is invalid
        Exception: Any exception from workflow execution

    Example:
        >>> from wake_ai import TestWorkflow, AuditWorkflow
        >>>
        >>> # Run a simple test workflow
        >>> results = run_ai_workflow(TestWorkflow)
        >>> print(results["formatted"])

        >>> # Run an audit workflow with specific parameters
        >>> results = run_ai_workflow(
        ...     AuditWorkflow,
        ...     model="opus",
        ...     scope_files=["contracts/Token.sol", "contracts/Vault.sol"],
        ...     context_docs=["docs/spec.md"],
        ...     focus_areas=["reentrancy", "access-control"]
        ... )
        >>> results["formatted"].export_json("audit_results.json")
    """
    # Get workflow name
    if workflow_name is None:
        workflow_name = getattr(workflow_class, 'name', workflow_class.__name__)

    # Process arguments using workflow's processor if available
    if hasattr(workflow_class, 'process_cli_args'):
        init_args = workflow_class.process_cli_args(**kwargs)
    else:
        init_args = {}

    # Add common parameters
    if model:
        init_args["model"] = model
    if working_dir:
        init_args["working_dir"] = working_dir
    for key in ["execution_dir", "allowed_tools", "disallowed_tools", "cleanup_working_dir"]:
        if key in kwargs:
            init_args[key] = kwargs[key]

    # Initialize workflow
    workflow: AIWorkflow = workflow_class(**init_args)

    logger.info(f"Running {workflow_name} workflow with model {model}, working_dir: {workflow.working_dir}")

    # Execute workflow
    logger.debug(f"Executing {workflow_name} workflow (resume={resume})")
    try:
        results, formatted_results = workflow.execute(resume=resume)
        logger.debug(f"Workflow {workflow_name} completed successfully")
        # Return both raw and formatted results
        return {"raw": results, "formatted": formatted_results}
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