"""
WebSocket Manager for Real-Time Task Updates and Notifications.

Implements WebSocket support for real-time task status updates,
live notifications, and interactive task monitoring.
"""

from src.utils.logger import get_logger

from .manager import (
    WebSocketManager,
    get_websocket_manager,
    init_websocket_manager,
    shutdown_websocket_manager,
)
from .models import (
    BidStatus,
    BidUpdateData,
    InteractiveResponseData,
    NotificationData,
    NotificationType,
    TaskStatus,
    TaskUpdateData,
    WebSocketAuthError,
    WebSocketMessage,
    WebSocketMessageType,
)

logger = get_logger(__name__)

__all__ = [
    "BidStatus",
    "BidUpdateData",
    "InteractiveResponseData",
    "NotificationData",
    "NotificationType",
    "TaskStatus",
    "TaskUpdateData",
    "WebSocketAuthError",
    "WebSocketManager",
    "WebSocketMessage",
    "WebSocketMessageType",
    "get_websocket_manager",
    "init_websocket_manager",
    "shutdown_websocket_manager",
]
