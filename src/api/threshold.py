"""
Threshold and escalation module.

This module contains escalation logic, human-in-the-loop (HITL)
functionality, and threshold petition handling.
"""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

# High-value threshold for profit protection (in dollars)
from src.config.config_manager import ConfigManager
from src.utils.logger import get_logger
from src.utils.notifications import TelegramNotifier

from .models import EscalationLog, ReviewStatus, TaskStatus

HIGH_VALUE_THRESHOLD = ConfigManager.get("HIGH_VALUE_THRESHOLD")

# Maximum number of retry attempts before escalation
MAX_RETRY_ATTEMPTS = ConfigManager.get("MAX_RETRY_ATTEMPTS")


def _should_escalate_task(
    task, retry_count: int, error_message: str | None = None,
) -> tuple:
    """
    Determine if a task should be escalated to human review.

    Escalation criteria (Pillar 1.7):
    1. Agent failed after MAX_RETRY_ATTEMPTS (3 retries)
    2. High-value task ($200+) failed (profit protection)

    Args:
        task: The Task object
        retry_count: Number of retry attempts made
        error_message: Optional error message from the failure

    Returns:
        Tuple of (should_escalate: bool, reason: str or None)
    """
    amount_dollars = (task.amount_paid / 100) if task.amount_paid else 0
    is_high_value = amount_dollars >= HIGH_VALUE_THRESHOLD

    if retry_count >= MAX_RETRY_ATTEMPTS:
        reason = "max_retries_exceeded"
        if is_high_value:
            reason = "max_retries_exceeded_high_value"
        return True, reason

    if is_high_value and error_message:
        reason = "high_value_task_failed"
        return True, reason

    return False, None


async def _escalate_task(
    db: Session, task, reason: str, error_message: str | None = None,
):
    """
    Escalate a task to human review with idempotent notification.

    Uses a database transaction (savepoint) to atomically update the task
    status and create the EscalationLog entry.

    Args:
        db: Database session
        task: The Task object to escalate
        reason: Reason for escalation
        error_message: Optional error details
    """
    logger = get_logger(__name__)

    amount_dollars = (task.amount_paid / 100) if task.amount_paid else 0
    is_high_value = amount_dollars >= HIGH_VALUE_THRESHOLD

    logger.warning(f"[ESCALATION] Task {task.id} escalated: {reason}")
    logger.warning(f"[ESCALATION] Amount: ${amount_dollars}, High-value: {is_high_value}")

    if error_message:
        logger.warning(f"[ESCALATION] Error: {error_message[:200]}...")

    idempotency_key = f"{task.id}_{reason}"
    should_send_notification = False
    escalation_log = None

    try:
        db.begin_nested()

        task.status = TaskStatus.ESCALATION
        task.escalation_reason = reason
        task.escalated_at = datetime.now(timezone.utc)
        task.last_error = error_message
        task.review_status = ReviewStatus.PENDING

        escalation_log = (
            db.query(EscalationLog)
            .filter(EscalationLog.idempotency_key == idempotency_key)
            .first()
        )

        if escalation_log is None:
            escalation_log = EscalationLog(
                task_id=task.id,
                reason=reason,
                error_message=error_message,
                idempotency_key=idempotency_key,
                amount_paid=task.amount_paid,
                domain=task.domain,
                client_email=task.client_email,
                notification_sent=False,
                notification_attempt_count=0,
            )
            db.add(escalation_log)

        should_send_notification = is_high_value and not escalation_log.notification_sent
        db.commit()

    except (OperationalError, IntegrityError, SQLAlchemyError) as e:
        db.rollback()
        logger.error(f"[ESCALATION] Database error in escalation transaction: {e}", exc_info=True)
        task.status = TaskStatus.ESCALATION
        task.escalation_reason = reason
        task.escalated_at = datetime.now(timezone.utc)
        task.last_error = error_message
        task.review_status = ReviewStatus.PENDING
        db.commit()
        return
    except Exception as e:
        db.rollback()
        logger.error(f"[ESCALATION] Unexpected error in escalation transaction: {e}", exc_info=True)
        task.status = TaskStatus.ESCALATION
        task.escalation_reason = reason
        task.escalated_at = datetime.now(timezone.utc)
        task.last_error = error_message
        task.review_status = ReviewStatus.PENDING
        db.commit()
        return

    if should_send_notification and escalation_log is not None:
        try:
            notifier = TelegramNotifier()
            context = f"Reason: {reason}"
            if error_message:
                context += f"\nError: {error_message[:200]}"

            notification_sent = await notifier.request_human_help(
                task_id=task.id,
                context=context,
                amount_paid=task.amount_paid,
                domain=task.domain,
                client_email=task.client_email,
            )

            escalation_log.notification_sent = notification_sent
            escalation_log.notification_attempt_count += 1
            escalation_log.last_notification_attempt_at = datetime.now(timezone.utc)

            if notification_sent:
                logger.info(f"[ESCALATION] Telegram notification sent for high-value task {task.id}")
            else:
                escalation_log.notification_error = "Notification returned False after retries"
                logger.warning(f"[ESCALATION] Telegram notification failed for task {task.id}")

            db.commit()
        except Exception as e:
            escalation_log.notification_attempt_count += 1
            escalation_log.last_notification_attempt_at = datetime.now(timezone.utc)
            escalation_log.notification_error = str(e)[:500]
            logger.error(f"[ESCALATION] Failed to send Telegram notification: {e}", exc_info=True)
            db.commit()
    elif escalation_log is not None and not should_send_notification:
        escalation_log.notification_attempt_count += 1
        escalation_log.last_notification_attempt_at = datetime.now(timezone.utc)
        db.commit()


__all__ = [
    "HIGH_VALUE_THRESHOLD",
    "MAX_RETRY_ATTEMPTS",
    "_escalate_task",
    "_should_escalate_task",
]
