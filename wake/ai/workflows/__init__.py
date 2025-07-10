"""Pre-defined audit workflows."""

from .audit import AuditWorkflow
from .test import TestWorkflow

AVAILABLE_WORKFLOWS = {
    "audit": AuditWorkflow,
    "test": TestWorkflow,
    # Future: "gas-optimization", "access-control", etc.
}

__all__ = ["AuditWorkflow", "TestWorkflow", "AVAILABLE_WORKFLOWS"]
