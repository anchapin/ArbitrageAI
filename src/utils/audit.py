"""Audit logging utilities.

This module provides functionality for creating and managing audit logs
in the database.
"""

from sqlalchemy.orm import Session

from src.api.models import AuditLog


def create_audit_log(
    db: Session,
    action: str,
    user_id: str | None = None,
    target_resource: str | None = None,
    target_resource_id: str | None = None,
    details: str | None = None,
):
    """Create a new audit log entry."""
    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        target_resource=target_resource,
        target_resource_id=target_resource_id,
        details=details,
    )
    db.add(log_entry)
    db.commit()
