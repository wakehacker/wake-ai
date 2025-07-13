"""Pre-defined audit workflows."""

from .audit import AuditWorkflow
from .test import TestWorkflow
from .validation_test import ValidationTestWorkflow

AVAILABLE_WORKFLOWS = {
    "audit": AuditWorkflow,
    "test": TestWorkflow,
    "validation_test": ValidationTestWorkflow,
    # Future: "gas-optimization", "access-control", etc.
}

__all__ = ["AuditWorkflow", "TestWorkflow", "ValidationTestWorkflow", "AVAILABLE_WORKFLOWS"]
