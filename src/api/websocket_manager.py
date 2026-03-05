"""WebSocket Manager for Real-Time Task Updates and Notifications.

Implements WebSocket support for real-time task status updates, live notifications,
and interactive task monitoring. Provides connection pooling, heartbeat mechanism,
and fallback to polling for non-WebSocket clients.

Features:
- WebSocket connection manager with authentication
- Real-time task status streaming (bid placed, execution started, completed)
- Live error notifications and alerts
- Interactive task control (pause, cancel, prioritize)
- Connection pooling and heartbeat mechanism
- Fallback to polling for non-WebSocket clients
- Client library for React frontend integration
- Load balancing across WebSocket servers

Usage:
    manager = WebSocketManager()
    await manager.connect_client(websocket, client_id)
    await manager.send_task_update(task_id, "PROCESSING", "Task started execution")
"""

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum as PyEnum
import json
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import jwt
from sqlalchemy.exc import IntegrityError, OperationalError

from src.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


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
    duration: int | None = None  # milliseconds
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


class WebSocketManager:
    """WebSocket connection manager with authentication and real-time updates."""

    def __init__(self, config: Config | None = None):
        """Initialize the WebSocket manager.

        Args:
            config: Configuration object (default: None)
        """
        self.config = config or Config()

        # Connection management
        self.active_connections: dict[str, WebSocket] = {}
        self.client_sessions: dict[str, dict[str, Any]] = {}
        self.connection_pools: dict[str, set[str]] = {}  # Pool -> client IDs

        # Task tracking
        self.task_subscriptions: dict[str, set[str]] = {}  # task_id -> client_ids
        self.bid_subscriptions: dict[str, set[str]] = {}   # bid_id -> client_ids

        # Heartbeat management
        self.heartbeat_tasks: dict[str, asyncio.Task] = {}
        self.last_heartbeat: dict[str, float] = {}

        # Rate limiting
        self.message_rate_limits: dict[str, list[float]] = {}
        self.max_messages_per_minute = 60

        # Background tasks
        self.cleanup_task: asyncio.Task | None = None
        self.heartbeat_interval = 30  # seconds

        # Authentication
        self.jwt_secret = self.config.JWT_SECRET_KEY
        self.jwt_algorithm = "HS256"

        logger.info("WebSocket Manager initialized")

    async def start(self):
        """Start background tasks."""
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("WebSocket Manager started")

    async def stop(self):
        """Stop background tasks and close all connections."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled")

        # Close all connections
        for client_id, _websocket in list(self.active_connections.items()):
            try:
                await self.disconnect_client(client_id)
            except (ConnectionError, BrokenPipeError) as e:
                logger.error(f"Connection error closing connection for {client_id}: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error closing connection for {client_id}: {e}", exc_info=True)

        logger.info("WebSocket Manager stopped")

    async def authenticate_client(self, websocket: WebSocket, token: str) -> str:
        """Authenticate a client using JWT token."""
        try:
            # Decode JWT token
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            client_id = payload.get("client_id")
            user_id = payload.get("user_id")

            if not client_id or not user_id:
                raise WebSocketAuthError("Invalid token payload")

            # Validate token expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                raise WebSocketAuthError("Token expired")

            # Store session info
            self.client_sessions[client_id] = {
                "user_id": user_id,
                "connected_at": time.time(),
                "last_activity": time.time(),
                "authenticated": True,
                "websocket": websocket,
            }

            logger.info(f"Client {client_id} authenticated successfully")
            return client_id

        except jwt.ExpiredSignatureError:
            raise WebSocketAuthError("Token expired") from None
        except jwt.InvalidTokenError as e:
            raise WebSocketAuthError(f"Invalid token: {e}") from e

    async def connect_client(self, websocket: WebSocket, client_id: str) -> bool:
        """Connect a client to the WebSocket manager."""
        await websocket.accept()

        # Check rate limits
        if not self._check_rate_limit(client_id):
            await self._send_message(websocket, WebSocketMessageType.AUTH_RESPONSE, {
                "success": False,
                "error": "Rate limit exceeded",
            })
            await websocket.close(code=1008)  # Policy violation
            return False

        try:
            # Authenticate client
            auth_token = await websocket.receive_text()
            client_id = await self.authenticate_client(websocket, auth_token)

            # Store connection
            self.active_connections[client_id] = websocket
            self.last_heartbeat[client_id] = time.time()

            # Start heartbeat task
            if client_id in self.heartbeat_tasks:
                self.heartbeat_tasks[client_id].cancel()
            self.heartbeat_tasks[client_id] = asyncio.create_task(
                self._heartbeat_loop(client_id),
            )

            # Send success response
            await self._send_message(websocket, WebSocketMessageType.AUTH_RESPONSE, {
                "success": True,
                "client_id": client_id,
                "server_time": time.time(),
            })

            # Start message handler
            await self._handle_client_messages(client_id)

        except WebSocketAuthError as e:
            await self._send_message(websocket, WebSocketMessageType.AUTH_RESPONSE, {
                "success": False,
                "error": str(e),
            })
            await websocket.close(code=1008)  # Policy violation
            return False
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected during authentication")
            return False
        except (ConnectionError, BrokenPipeError) as e:
            logger.error(f"Connection error connecting client {client_id}: {e}", exc_info=True)
            await websocket.close(code=1011)  # Internal error
            return False
        except Exception as e:
            logger.error(f"Error connecting client {client_id}: {e}", exc_info=True)
            await websocket.close(code=1011)  # Internal error
            return False

        return True

    async def disconnect_client(self, client_id: str):
        """Disconnect a client and clean up resources."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.close()
            except (ConnectionError, BrokenPipeError) as e:
                logger.error(f"Connection error closing websocket for {client_id}: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error closing websocket for {client_id}: {e}", exc_info=True)

        # Clean up resources
        self.active_connections.pop(client_id, None)
        self.client_sessions.pop(client_id, None)
        self.last_heartbeat.pop(client_id, None)

        # Cancel heartbeat task
        if client_id in self.heartbeat_tasks:
            self.heartbeat_tasks[client_id].cancel()
            self.heartbeat_tasks.pop(client_id, None)

        # Remove from subscriptions
        for task_id, client_ids in list(self.task_subscriptions.items()):
            client_ids.discard(client_id)
            if not client_ids:
                self.task_subscriptions.pop(task_id, None)

        for bid_id, client_ids in list(self.bid_subscriptions.items()):
            client_ids.discard(client_id)
            if not client_ids:
                self.bid_subscriptions.pop(bid_id, None)

        logger.info(f"Client {client_id} disconnected")

    async def subscribe_to_task(self, client_id: str, task_id: str):
        """Subscribe a client to task updates."""
        if client_id not in self.active_connections:
            return False

        if task_id not in self.task_subscriptions:
            self.task_subscriptions[task_id] = set()

        self.task_subscriptions[task_id].add(client_id)
        logger.debug(f"Client {client_id} subscribed to task {task_id}")
        return True

    async def subscribe_to_bid(self, client_id: str, bid_id: str):
        """Subscribe a client to bid updates."""
        if client_id not in self.active_connections:
            return False

        if bid_id not in self.bid_subscriptions:
            self.bid_subscriptions[bid_id] = set()

        self.bid_subscriptions[bid_id].add(client_id)
        logger.debug(f"Client {client_id} subscribed to bid {bid_id}")
        return True

    async def unsubscribe_from_task(self, client_id: str, task_id: str):
        """Unsubscribe a client from task updates."""
        if task_id in self.task_subscriptions:
            self.task_subscriptions[task_id].discard(client_id)
            if not self.task_subscriptions[task_id]:
                self.task_subscriptions.pop(task_id, None)

    async def unsubscribe_from_bid(self, client_id: str, bid_id: str):
        """Unsubscribe a client from bid updates."""
        if bid_id in self.bid_subscriptions:
            self.bid_subscriptions[bid_id].discard(client_id)
            if not self.bid_subscriptions[bid_id]:
                self.bid_subscriptions.pop(bid_id, None)

    async def send_task_update(
        self,
        task_id: str,
        status: TaskStatus | str,
        message: str,
        progress: float | None = None,
        estimated_completion: datetime | None = None,
        result_url: str | None = None,
        error_details: str | None = None,
    ):
        """Send task status update to all subscribed clients."""
        status_str = status.value if isinstance(status, TaskStatus) else status

        data = TaskUpdateData(
            task_id=task_id,
            status=status_str,
            message=message,
            progress=progress,
            estimated_completion=estimated_completion.isoformat() if estimated_completion else None,
            result_url=result_url,
            error_details=error_details,
        )

        await self._broadcast_to_subscribers(
            self.task_subscriptions.get(task_id, set()),
            WebSocketMessageType.TASK_STATUS_UPDATE,
            asdict(data),
        )

    async def send_task_progress(
        self,
        task_id: str,
        progress: float,
        message: str = "Task in progress",
    ):
        """Send task progress update."""
        await self.send_task_update(
            task_id=task_id,
            status=TaskStatus.PROCESSING,
            message=message,
            progress=progress,
        )

    async def send_task_completed(
        self,
        task_id: str,
        result_url: str,
        message: str = "Task completed successfully",
    ):
        """Send task completion notification."""
        data = TaskUpdateData(
            task_id=task_id,
            status=TaskStatus.COMPLETED.value,
            message=message,
            result_url=result_url,
        )
        await self._broadcast_to_subscribers(
            self.task_subscriptions.get(task_id, set()),
            WebSocketMessageType.TASK_COMPLETED,
            asdict(data),
        )

    async def send_task_error(
        self,
        task_id: str,
        error_message: str,
        error_details: str | None = None,
    ):
        """Send task error notification."""
        data = TaskUpdateData(
            task_id=task_id,
            status=TaskStatus.FAILED.value,
            message=error_message,
            error_details=error_details,
        )
        await self._broadcast_to_subscribers(
            self.task_subscriptions.get(task_id, set()),
            WebSocketMessageType.TASK_ERROR,
            asdict(data),
        )

    async def send_bid_update(
        self,
        bid_id: str,
        job_id: str,
        status: BidStatus | str,
        message: str,
        marketplace: str,
        bid_amount: int | None = None,
    ):
        """Send bid status update to all subscribed clients."""
        status_str = status.value if isinstance(status, BidStatus) else status

        data = BidUpdateData(
            bid_id=bid_id,
            job_id=job_id,
            status=status_str,
            message=message,
            marketplace=marketplace,
            bid_amount=bid_amount,
        )

        await self._broadcast_to_subscribers(
            self.bid_subscriptions.get(bid_id, set()),
            WebSocketMessageType.BID_STATUS_UPDATE,
            asdict(data),
        )

    async def send_notification(
        self,
        client_id: str,
        notification_type: NotificationType | str,
        title: str,
        message: str,
        duration: int | None = None,
        persistent: bool = False,
    ):
        """Send a notification to a specific client."""
        type_str = notification_type.value if isinstance(notification_type, NotificationType) else notification_type

        data = NotificationData(
            type=type_str,
            title=title,
            message=message,
            duration=duration,
            persistent=persistent,
        )

        await self._send_to_client(client_id, WebSocketMessageType.NOTIFICATION, asdict(data))

    async def send_system_alert(
        self,
        alert_type: str,
        message: str,
        clients: list[str] | None = None,
    ):
        """Send system alert to specified clients or all clients."""
        data = {
            "type": alert_type,
            "message": message,
            "timestamp": time.time(),
        }

        if clients:
            await self._broadcast_to_clients(clients, WebSocketMessageType.SYSTEM_ALERT, data)
        else:
            await self._broadcast_to_all(WebSocketMessageType.SYSTEM_ALERT, data)

    async def send_interactive_response(
        self,
        client_id: str,
        action: str,
        task_id: str,
        success: bool,
        message: str,
        data: dict[str, Any] | None = None,
    ):
        """Send interactive action response to client."""
        response_data = InteractiveResponseData(
            action=action,
            task_id=task_id,
            success=success,
            message=message,
            data=data,
        )

        await self._send_to_client(client_id, WebSocketMessageType.INTERACTIVE_RESPONSE, asdict(response_data))

    async def handle_interactive_action(
        self,
        client_id: str,
        action: str,
        task_id: str,
        params: dict[str, Any],
    ):
        """Handle interactive actions from clients (pause, cancel, prioritize)."""
        try:
            # Validate client has permission for this task
            if not await self._validate_task_access(client_id, task_id):
                await self.send_interactive_response(
                    client_id, action, task_id, False, "Access denied",
                )
                return

            # Handle specific actions
            if action == "pause":
                result = await self._pause_task(task_id, params)
                await self.send_interactive_response(
                    client_id, action, task_id, result["success"], result["message"],
                )
            elif action == "cancel":
                result = await self._cancel_task(task_id, params)
                await self.send_interactive_response(
                    client_id, action, task_id, result["success"], result["message"],
                )
            elif action == "prioritize":
                result = await self._prioritize_task(task_id, params)
                await self.send_interactive_response(
                    client_id, action, task_id, result["success"], result["message"],
                )
            else:
                await self.send_interactive_response(
                    client_id, action, task_id, False, f"Unknown action: {action}",
                )

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Error handling interactive action {action} for task {task_id} (data error): {e}", exc_info=True)
            await self.send_interactive_response(
                client_id, action, task_id, False, f"Internal error: {e!s}",
            )
        except Exception as e:
            logger.error(f"Error handling interactive action {action} for task {task_id}: {e}", exc_info=True)
            await self.send_interactive_response(
                client_id, action, task_id, False, f"Internal error: {e!s}",
            )

    async def _handle_client_messages(self, client_id: str):
        """Handle incoming messages from a client."""
        websocket = self.active_connections[client_id]

        try:
            while websocket.application_state == WebSocketState.CONNECTED:
                try:
                    message = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=1.0,
                    )

                    # Update last activity
                    self.client_sessions[client_id]["last_activity"] = time.time()

                    # Process message
                    await self._process_client_message(client_id, message)

                except asyncio.TimeoutError:
                    # Check if connection is still alive
                    if websocket.application_state != WebSocketState.CONNECTED:
                        break

        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected")
        except (ConnectionError, BrokenPipeError) as e:
            logger.error(f"Connection error handling messages for client {client_id}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error handling messages for client {client_id}: {e}", exc_info=True)
        finally:
            await self.disconnect_client(client_id)

    async def _process_client_message(self, client_id: str, message: str):
        """Process a message from a client."""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            payload = data.get("data", {})

            if message_type == "subscribe_task":
                await self.subscribe_to_task(client_id, payload.get("task_id"))
            elif message_type == "subscribe_bid":
                await self.subscribe_to_bid(client_id, payload.get("bid_id"))
            elif message_type == "unsubscribe_task":
                await self.unsubscribe_from_task(client_id, payload.get("task_id"))
            elif message_type == "unsubscribe_bid":
                await self.unsubscribe_from_bid(client_id, payload.get("bid_id"))
            elif message_type == "interactive_action":
                await self.handle_interactive_action(
                    client_id,
                    payload.get("action"),
                    payload.get("task_id"),
                    payload.get("params", {}),
                )
            elif message_type == "heartbeat":
                self.last_heartbeat[client_id] = time.time()
            else:
                logger.warning(f"Unknown message type from client {client_id}: {message_type}")

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from client {client_id}: {message}")
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error processing message from client {client_id}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error processing message from client {client_id}: {e}", exc_info=True)

    @staticmethod
    async def _send_message(websocket: WebSocket, message_type: WebSocketMessageType, data: dict[str, Any]):
        """Send a message to a specific websocket."""
        if websocket.application_state == WebSocketState.CONNECTED:
            message = WebSocketMessage(
                type=message_type.value,
                timestamp=time.time(),
                data=data,
            )
            await websocket.send_text(message.to_json())

    async def _send_to_client(self, client_id: str, message_type: WebSocketMessageType, data: dict[str, Any]):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await self._send_message(websocket, message_type, data)

    async def _broadcast_to_subscribers(self, client_ids: set[str], message_type: WebSocketMessageType, data: dict[str, Any]):
        """Broadcast a message to a set of subscribed clients."""
        for client_id in client_ids:
            await self._send_to_client(client_id, message_type, data)

    async def _broadcast_to_clients(self, client_ids: list[str], message_type: WebSocketMessageType, data: dict[str, Any]):
        """Broadcast a message to specific clients."""
        for client_id in client_ids:
            await self._send_to_client(client_id, message_type, data)

    async def _broadcast_to_all(self, message_type: WebSocketMessageType, data: dict[str, Any]):
        """Broadcast a message to all connected clients."""
        for client_id in self.active_connections:
            await self._send_to_client(client_id, message_type, data)

    async def _heartbeat_loop(self, client_id: str):
        """Send periodic heartbeat messages to a client."""
        websocket = self.active_connections[client_id]

        while websocket.application_state == WebSocketState.CONNECTED:
            try:
                await self._send_message(websocket, WebSocketMessageType.HEARTBEAT, {
                    "timestamp": time.time(),
                    "server_time": time.time(),
                })
                await asyncio.sleep(self.heartbeat_interval)
            except (ConnectionError, BrokenPipeError) as e:
                logger.error(f"Connection error in heartbeat for client {client_id}: {e}", exc_info=True)
                await self.disconnect_client(client_id)
                break
            except Exception as e:
                logger.error(f"Heartbeat failed for client {client_id}: {e}", exc_info=True)
                await self.disconnect_client(client_id)
                break

    async def _cleanup_loop(self):
        """Background cleanup task."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute

                # Clean up stale connections
                current_time = time.time()
                stale_clients = []

                for client_id, last_time in self.last_heartbeat.items():
                    if current_time - last_time > 120:  # 2 minutes timeout
                        stale_clients.append(client_id)

                for client_id in stale_clients:
                    logger.warning(f"Client {client_id} heartbeat timeout, disconnecting")
                    await self.disconnect_client(client_id)

                # Clean up old rate limit data
                cutoff_time = current_time - 60
                for client_id in list(self.message_rate_limits.keys()):
                    self.message_rate_limits[client_id] = [
                        timestamp for timestamp in self.message_rate_limits[client_id]
                        if timestamp > cutoff_time
                    ]
                    if not self.message_rate_limits[client_id]:
                        self.message_rate_limits.pop(client_id, None)

            except asyncio.CancelledError:
                break
            except (OperationalError, IntegrityError) as e:
                logger.error(f"Database error in cleanup loop: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)

    def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client has exceeded message rate limit."""
        current_time = time.time()

        if client_id not in self.message_rate_limits:
            self.message_rate_limits[client_id] = []

        # Remove old timestamps
        self.message_rate_limits[client_id] = [
            timestamp for timestamp in self.message_rate_limits[client_id]
            if current_time - timestamp < 60
        ]

        # Check limit
        if len(self.message_rate_limits[client_id]) >= self.max_messages_per_minute:
            return False

        # Add current timestamp
        self.message_rate_limits[client_id].append(current_time)
        return True

    async def _validate_task_access(self, client_id: str, task_id: str) -> bool:
        """Validate that a client has access to a task.

        Args:
            client_id: The client identifier
            task_id: The task identifier to validate access for

        Returns:
            bool: True if client has access, False otherwise
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        session_data = self.client_sessions.get(client_id, {})
        user_id = session_data.get("user_id")

        if not user_id:
            logger.warning(f"No user_id found in session for client {client_id}")
            return False

        try:
            # Create database session
            engine = create_engine(self.config.DATABASE_URL)

            with Session(engine) as db:
                # Import Task model here to avoid circular imports
                from .models import Task

                # Query task by ID and verify ownership
                task = db.query(Task).filter(
                    Task.id == task_id,
                    Task.client_id == user_id,
                ).first()

                if task:
                    logger.debug(f"Client {client_id} has access to task {task_id}")
                    return True
                logger.warning(
                    f"Client {client_id} (user: {user_id}) attempted "
                    f"to access unauthorized task {task_id}",
                )
                return False

        except (OperationalError, IntegrityError) as e:
            logger.error(f"Database error validating task access: {e}", exc_info=True)
            # Fail closed - deny access on error
            return False
        except Exception as e:
            logger.error(f"Error validating task access: {e}", exc_info=True)
            # Fail closed - deny access on error
            return False

    async def _pause_task(self, task_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Pause a task execution.

        Args:
            task_id: The task identifier to pause
            params: Additional parameters (e.g., reason for pause)

        Returns:
            Dict containing success status and message
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        try:
            engine = create_engine(self.config.DATABASE_URL)

            with Session(engine) as db:
                from .models import Task, TaskStatus

                # Query the task
                task = db.query(Task).filter(Task.id == task_id).first()

                if not task:
                    return {
                        "success": False,
                        "message": f"Task {task_id} not found",
                        "error_code": "TASK_NOT_FOUND",
                    }

                # Check if task can be paused
                if task.status not in {TaskStatus.PLANNING, TaskStatus.PROCESSING}:
                    return {
                        "success": False,
                        "message": f"Task cannot be paused in status: {task.status}",
                        "error_code": "INVALID_STATUS_FOR_PAUSE",
                    }

                # Update task status to indicate paused state
                # Store the original status to resume later
                previous_status = task.status.value
                task.status = TaskStatus.PENDING  # Return to pending state
                task.metadata = task.metadata or {}
                task.metadata["paused_at"] = datetime.now().isoformat()
                task.metadata["previous_status"] = previous_status
                task.metadata["pause_reason"] = params.get("reason", "User requested")

                db.commit()

                logger.info(f"Task {task_id} paused successfully (previous status: {previous_status})")

                # Send WebSocket notification to subscribers
                await self._send_pause_notification(task_id, previous_status)

                return {
                    "success": True,
                    "message": f"Task {task_id} paused successfully",
                    "previous_status": previous_status,
                    "paused_at": task.metadata["paused_at"],
                }

        except (OperationalError, IntegrityError) as e:
            logger.error(f"Database error pausing task {task_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": "Database error occurred",
                "error_code": "DATABASE_ERROR",
            }
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Data error pausing task {task_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to pause task: {e!s}",
                "error_code": "PAUSE_ERROR",
            }
        except Exception as e:
            logger.error(f"Error pausing task {task_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to pause task: {e!s}",
                "error_code": "PAUSE_ERROR",
            }

    async def _send_pause_notification(self, task_id: str, previous_status: str):
        """Send pause notification to task subscribers."""
        if task_id in self.task_subscriptions:
            message = WebSocketMessage(
                type=WebSocketMessageType.TASK_STATUS_UPDATE,
                timestamp=time.time(),
                data={
                    "task_id": task_id,
                    "status": "PAUSED",
                    "previous_status": previous_status,
                    "message": "Task paused by user",
                    "paused_at": datetime.now().isoformat(),
                },
            )

            for client_id in self.task_subscriptions[task_id]:
                await self.send_message(client_id, message)

    async def _cancel_task(self, task_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Cancel a task execution.

        Args:
            task_id: The task identifier to cancel
            params: Additional parameters (e.g., cancellation reason)

        Returns:
            Dict containing success status and message
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        try:
            engine = create_engine(self.config.DATABASE_URL)

            with Session(engine) as db:
                from .models import Task, TaskStatus

                # Query the task
                task = db.query(Task).filter(Task.id == task_id).first()

                if not task:
                    return {
                        "success": False,
                        "message": f"Task {task_id} not found",
                        "error_code": "TASK_NOT_FOUND",
                    }

                # Check if task can be cancelled
                cancellable_statuses = [
                    TaskStatus.PENDING,
                    TaskStatus.PLANNING,
                    TaskStatus.PROCESSING,
                    TaskStatus.REVIEW_REQUIRED,
                ]

                if task.status not in cancellable_statuses:
                    return {
                        "success": False,
                        "message": f"Task cannot be cancelled in status: {task.status}",
                        "error_code": "INVALID_STATUS_FOR_CANCEL",
                    }

                # Store previous state for audit
                previous_status = task.status.value
                cancellation_reason = params.get("reason", "User requested cancellation")

                # Update task status to FAILED with cancellation metadata
                task.status = TaskStatus.FAILED
                task.metadata = task.metadata or {}
                task.metadata["cancelled_at"] = datetime.now().isoformat()
                task.metadata["previous_status"] = previous_status
                task.metadata["cancellation_reason"] = cancellation_reason
                task.metadata["cancelled_by"] = "user"
                task.error_message = f"Task cancelled: {cancellation_reason}"

                db.commit()

                logger.info(f"Task {task_id} cancelled successfully (previous status: {previous_status})")

                # Send WebSocket notification to subscribers
                await self._send_cancel_notification(task_id, previous_status, cancellation_reason)

                return {
                    "success": True,
                    "message": f"Task {task_id} cancelled successfully",
                    "previous_status": previous_status,
                    "cancelled_at": task.metadata["cancelled_at"],
                    "cancellation_reason": cancellation_reason,
                }

        except (OperationalError, IntegrityError) as e:
            logger.error(f"Database error cancelling task {task_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": "Database error occurred",
                "error_code": "DATABASE_ERROR",
            }
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Data error cancelling task {task_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to cancel task: {e!s}",
                "error_code": "CANCEL_ERROR",
            }
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to cancel task: {e!s}",
                "error_code": "CANCEL_ERROR",
            }

    async def _send_cancel_notification(
        self,
        task_id: str,
        previous_status: str,
        cancellation_reason: str,
    ):
        """Send cancellation notification to task subscribers."""
        if task_id in self.task_subscriptions:
            message = WebSocketMessage(
                type=WebSocketMessageType.TASK_STATUS_UPDATE,
                timestamp=time.time(),
                data={
                    "task_id": task_id,
                    "status": "CANCELLED",
                    "previous_status": previous_status,
                    "message": "Task cancelled by user",
                    "cancellation_reason": cancellation_reason,
                    "cancelled_at": datetime.now().isoformat(),
                },
            )

            for client_id in self.task_subscriptions[task_id]:
                await self.send_message(client_id, message)

    async def _prioritize_task(self, task_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Prioritize a task in the execution queue.

        Args:
            task_id: The task identifier to prioritize
            params: Additional parameters (e.g., priority level, reason)

        Returns:
            Dict containing success status and message
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        try:
            engine = create_engine(self.config.DATABASE_URL)

            with Session(engine) as db:
                from .models import Task, TaskStatus

                # Query the task
                task = db.query(Task).filter(Task.id == task_id).first()

                if not task:
                    return {
                        "success": False,
                        "message": f"Task {task_id} not found",
                        "error_code": "TASK_NOT_FOUND",
                    }

                # Check if task can be prioritized
                prioritizable_statuses = [
                    TaskStatus.PENDING,
                    TaskStatus.PLANNING,
                    TaskStatus.PROCESSING,
                ]

                if task.status not in prioritizable_statuses:
                    return {
                        "success": False,
                        "message": f"Task cannot be prioritized in status: {task.status}",
                        "error_code": "INVALID_STATUS_FOR_PRIORITY",
                    }

                # Get priority level (1-10, where 10 is highest)
                priority_level = params.get("priority", 5)
                priority_level = max(1, min(10, priority_level))  # Clamp between 1-10

                # Update task priority in metadata
                task.metadata = task.metadata or {}
                previous_priority = task.metadata.get("priority", 5)
                task.metadata["priority"] = priority_level
                task.metadata["priority_updated_at"] = datetime.now().isoformat()
                task.metadata["priority_reason"] = params.get("reason", "User requested")

                db.commit()

                logger.info(
                    f"Task {task_id} priority updated: {previous_priority} -> {priority_level}",
                )

                # Send WebSocket notification to subscribers
                await self._send_priority_notification(
                    task_id,
                    previous_priority,
                    priority_level,
                )

                return {
                    "success": True,
                    "message": f"Task {task_id} priority updated to {priority_level}",
                    "previous_priority": previous_priority,
                    "new_priority": priority_level,
                    "priority_updated_at": task.metadata["priority_updated_at"],
                }

        except (OperationalError, IntegrityError) as e:
            logger.error(f"Database error updating task priority {task_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": "Database error occurred",
                "error_code": "DATABASE_ERROR",
            }
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Data error updating task priority {task_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to update task priority: {e!s}",
                "error_code": "PRIORITY_ERROR",
            }
        except Exception as e:
            logger.error(f"Error updating task priority {task_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to update task priority: {e!s}",
                "error_code": "PRIORITY_ERROR",
            }

    async def _send_priority_notification(
        self,
        task_id: str,
        previous_priority: int,
        new_priority: int,
    ):
        """Send priority update notification to task subscribers."""
        if task_id in self.task_subscriptions:
            message = WebSocketMessage(
                type=WebSocketMessageType.TASK_PROGRESS_UPDATE,
                timestamp=time.time(),
                data={
                    "task_id": task_id,
                    "priority_updated": True,
                    "previous_priority": previous_priority,
                    "new_priority": new_priority,
                    "message": f"Task priority changed to {new_priority}",
                    "updated_at": datetime.now().isoformat(),
                },
            )

            for client_id in self.task_subscriptions[task_id]:
                await self.send_message(client_id, message)

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)

    def get_subscriptions_count(self) -> dict[str, int]:
        """Get subscription counts."""
        return {
            "task_subscriptions": len(self.task_subscriptions),
            "bid_subscriptions": len(self.bid_subscriptions),
            "total_subscriptions": sum(len(clients) for clients in self.task_subscriptions.values()) +
                                 sum(len(clients) for clients in self.bid_subscriptions.values()),
        }


# Global WebSocket manager instance
websocket_manager: WebSocketManager | None = None


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    global websocket_manager  # noqa: PLW0603
    if websocket_manager is None:
        websocket_manager = WebSocketManager()
    return websocket_manager


async def init_websocket_manager():
    """Initialize the WebSocket manager."""
    global websocket_manager  # noqa: PLW0603
    websocket_manager = WebSocketManager()
    await websocket_manager.start()


async def shutdown_websocket_manager():
    """Shutdown the WebSocket manager."""
    global websocket_manager
    if websocket_manager:
        await websocket_manager.stop()
