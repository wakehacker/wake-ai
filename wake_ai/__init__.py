"""AI workflows for Wake framework."""

from .audit import AuditWorkflow, AuditDetectionResults
from .example import ExampleWorkflow
from .test import TestWorkflow
from .validation_test import ValidationTestWorkflow

AVAILABLE_WORKFLOWS = {
    "audit": AuditWorkflow,
    "test": TestWorkflow,
    "validation_test": ValidationTestWorkflow,
    "example": ExampleWorkflow,
}

__all__ = [
    "AuditWorkflow",
    "AuditDetectionResults", 
    "ExampleWorkflow",
    "TestWorkflow",
    "ValidationTestWorkflow",
    "AVAILABLE_WORKFLOWS",
]