"""Pre-defined audit workflows."""

from .audit import AuditWorkflow

AVAILABLE_WORKFLOWS = {
    "audit": AuditWorkflow,
    # Future: "gas-optimization", "access-control", etc.
}

__all__ = ["AuditWorkflow", "AVAILABLE_WORKFLOWS"]
