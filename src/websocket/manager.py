"""
WebSocket Manager.

Manages WebSocket connections for real-time updates.
"""

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import jwt

from src.config import Config
from src.utils.logger import get_logger

from .models import (
    BidStatus,
    BidUpdateData,
    NotificationData,
    NotificationType,
    TaskStatus,
    TaskUpdateData,
    WebSocketAuthError,
    WebSocketMessage,
    WebSocketMessageType,
)

logger = get_logger(__name__)


class WebSocketManager:
    """WebSocket connection manager with authentication and real-time updates."""

    def __init__(self, config: Config | None = None):
        """Initialize the WebSocket manager."""
        self.config = config or Config()

        self.active_connections: dict[str, WebSocket] = {}
        self.client_sessions: dict[str, dict[str, Any]] = {}
        self.connection_pools: dict[str, set[str]] = {}

        self.task_subscriptions: dict[str, set[str]] = {}
        self.bid_subscriptions: dict[str, set[str]] = {}

        self.heartbeat_tasks: dict[str, asyncio.Task] = {}
        self.last_heartbeat: dict[str, float] = {}

        self.message_rate_limits: dict[str, list[float]] = {}
        self.max_messages_per_minute = 60

        self.cleanup_task: asyncio.Task | None = None
        self.heartbeat_interval = 30

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

        for client_id, _websocket in list(self.active_connections.items()):
            try:
                await self.disconnect_client(client_id)
            except Exception as e:
                logger.error(f"Error closing connection for {client_id}: {e}", exc_info=True)

        logger.info("WebSocket Manager stopped")

    async def authenticate_client(self, websocket: WebSocket, token: str) -> str:
        """Authenticate a client using JWT token."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            client_id = payload.get("client_id")
            user_id = payload.get("user_id")

            if not client_id or not user_id:
                raise WebSocketAuthError("Invalid token payload")

            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                raise WebSocketAuthError("Token expired")

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

        if not self._check_rate_limit(client_id):
            await self._send_message(websocket, WebSocketMessageType.AUTH_RESPONSE, {
                "success": False,
                "error": "Rate limit exceeded",
            })
            await websocket.close(code=1008)
            return False

        try:
            auth_token = await websocket.receive_text()
            client_id = await self.authenticate_client(websocket, auth_token)

            self.active_connections[client_id] = websocket
            self.last_heartbeat[client_id] = time.time()

            if client_id in self.heartbeat_tasks:
                self.heartbeat_tasks[client_id].cancel()
            self.heartbeat_tasks[client_id] = asyncio.create_task(
                self._heartbeat_loop(client_id),
            )

            await self._send_message(websocket, WebSocketMessageType.AUTH_RESPONSE, {
                "success": True,
                "client_id": client_id,
                "server_time": time.time(),
            })

            await self._handle_client_messages(client_id)

        except WebSocketAuthError as e:
            await self._send_message(websocket, WebSocketMessageType.AUTH_RESPONSE, {
                "success": False,
                "error": str(e),
            })
            await websocket.close(code=1008)
            return False
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected during authentication")
            return False
        except Exception as e:
            logger.error(f"Error connecting client {client_id}: {e}", exc_info=True)
            await websocket.close(code=1011)
            return False

        return True

    async def disconnect_client(self, client_id: str):
        """Disconnect a client and clean up resources."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.close()
            except Exception as e:
                logger.error(f"Error closing websocket for {client_id}: {e}", exc_info=True)

        self.active_connections.pop(client_id, None)
        self.client_sessions.pop(client_id, None)
        self.last_heartbeat.pop(client_id, None)

        if client_id in self.heartbeat_tasks:
            self.heartbeat_tasks[client_id].cancel()
            self.heartbeat_tasks.pop(client_id, None)

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
            except Exception as e:
                logger.error(f"Heartbeat failed for client {client_id}: {e}", exc_info=True)
                await self.disconnect_client(client_id)
                break

    async def _cleanup_loop(self):
        """Background cleanup task."""
        while True:
            try:
                await asyncio.sleep(60)

                current_time = time.time()
                stale_clients = []

                for client_id, last_time in self.last_heartbeat.items():
                    if current_time - last_time > 120:
                        stale_clients.append(client_id)

                for client_id in stale_clients:
                    logger.warning(f"Client {client_id} heartbeat timeout, disconnecting")
                    await self.disconnect_client(client_id)

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
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)

    def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client has exceeded message rate limit."""
        current_time = time.time()

        if client_id not in self.message_rate_limits:
            self.message_rate_limits[client_id] = []

        self.message_rate_limits[client_id] = [
            timestamp for timestamp in self.message_rate_limits[client_id]
            if current_time - timestamp < 60
        ]

        if len(self.message_rate_limits[client_id]) >= self.max_messages_per_minute:
            return False

        self.message_rate_limits[client_id].append(current_time)
        return True

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


websocket_manager: WebSocketManager | None = None


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    global websocket_manager
    if websocket_manager is None:
        websocket_manager = WebSocketManager()
    return websocket_manager


async def init_websocket_manager():
    """Initialize the WebSocket manager."""
    global websocket_manager
    websocket_manager = WebSocketManager()
    await websocket_manager.start()


async def shutdown_websocket_manager():
    """Shutdown the WebSocket manager."""
    global websocket_manager
    if websocket_manager:
        await websocket_manager.stop()
