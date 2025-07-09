"""Pre-defined audit workflows."""

from .security_audit import SecurityAuditWorkflow

AVAILABLE_WORKFLOWS = {
    "security-audit": SecurityAuditWorkflow,
    # Future: "gas-optimization", "access-control", etc.
}

__all__ = ["SecurityAuditWorkflow", "AVAILABLE_WORKFLOWS"]