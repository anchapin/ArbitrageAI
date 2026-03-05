"""WebSocket Models.

Enums and dataclasses for WebSocket communication.
"""

from dataclasses import dataclass
from enum import Enum as PyEnum
from typing import Any


class WebSocketMessageType(PyEnum):
    """WebSocket message types."""
    TASK_STATUS_UPDATE = "task_status_update"
    TASK_PROGRESS_UPDATE = "task_progress_update"
    TASK_COMPLETED = "task_completed"
    TASK_ERROR = "task_error"
    BID_PLACED = "bid_placed"
    BID_STATUS_UPDATE = "bid_status_update"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    AUTH_RESPONSE = "auth_response"
    INTERACTIVE_RESPONSE = "interactive_response"
    SYSTEM_ALERT = "system_alert"


class TaskStatus(PyEnum):
    """Task status for WebSocket updates."""
    PENDING = "PENDING"
    PAID = "PAID"
    PLANNING = "PLANNING"
    PROCESSING = "PROCESSING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVIEWING = "REVIEWING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATION = "ESCALATION"


class BidStatus(PyEnum):
    """Bid status for WebSocket updates."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUBMITTED = "SUBMITTED"
    WON = "WON"
    LOST = "LOST"
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"


class NotificationType(PyEnum):
    """Notification types."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class WebSocketMessage:
    """WebSocket message data structure."""
    type: str
    timestamp: float
    data: dict[str, Any]

    def to_json(self) -> str:
        """Convert message to JSON string."""
        import json
        return json.dumps({
            "type": self.type,
            "timestamp": self.timestamp,
            "data": self.data,
        })


@dataclass
class TaskUpdateData:
    """Task update message data."""
    task_id: str
    status: str
    message: str
    progress: float | None = None
    estimated_completion: str | None = None
    result_url: str | None = None
    error_details: str | None = None


@dataclass
class BidUpdateData:
    """Bid update message data."""
    bid_id: str
    job_id: str
    status: str
    message: str
    marketplace: str
    bid_amount: int | None = None


@dataclass
class NotificationData:
    """Notification message data."""
    type: str
    title: str
    message: str
    duration: int | None = None
    persistent: bool = False


@dataclass
class InteractiveResponseData:
    """Interactive response message data."""
    action: str
    task_id: str
    success: bool
    message: str
    data: dict[str, Any] | None = None


class WebSocketAuthError(Exception):
    """Authentication error for WebSocket connections."""
