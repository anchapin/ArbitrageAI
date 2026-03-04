"""
Graceful Shutdown and State Recovery System (Issue #102).

Provides graceful shutdown capabilities and state recovery for:
- Active task execution
- Database sessions
- Redis connections
- Background jobs
- Scheduled tasks
- WebSocket connections

Features:
- Signal handling (SIGTERM, SIGINT)
- State persistence before shutdown
- State recovery on restart
- Timeout-based forced shutdown
- Comprehensive logging

Usage:
    from src.utils.graceful_shutdown import GracefulShutdownManager

    shutdown_manager = GracefulShutdownManager()
    await shutdown_manager.initialize()

    # Register shutdown handlers
    shutdown_manager.register_handler("task_execution", cleanup_tasks)

    # On shutdown signal
    await shutdown_manager.shutdown()
"""

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
from pathlib import Path
import signal
import time
from typing import Any

import aiofiles

from .logger import get_logger
from .telemetry import get_tracer

logger = get_logger(__name__)


class ShutdownReason(str, Enum):
    """Reasons for shutdown."""
    SIGNAL = "signal"
    TIMEOUT = "timeout"
    ERROR = "error"
    MANUAL = "manual"


class ShutdownState(str, Enum):
    """Current shutdown state."""
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN_COMPLETE = "shutdown_complete"


@dataclass
class ShutdownStateData:
    """State data to persist during shutdown."""
    active_tasks: list[dict[str, Any]]
    pending_jobs: list[dict[str, Any]]
    scheduled_tasks: list[dict[str, Any]]
    websocket_connections: list[dict[str, Any]]
    timestamp: str
    shutdown_reason: str | None = None


class GracefulShutdownManager:
    """
    Manages graceful shutdown and state recovery.

    Features:
    - Signal handling for SIGTERM and SIGINT
    - State persistence to disk
    - State recovery on restart
    - Timeout-based forced shutdown
    - Custom shutdown handlers
    - Comprehensive logging and telemetry
    """

    def __init__(
        self,
        state_dir: str = "data/shutdown_state",
        shutdown_timeout: float = 30.0,
        max_state_age_hours: int = 24,
    ):
        """Initialize the graceful shutdown manager.

        Args:
            state_dir: Directory to store shutdown state files.
            shutdown_timeout: Maximum time to wait for graceful shutdown in seconds.
            max_state_age_hours: Maximum age of state files to recover from.
        """
        self.state_dir = Path(state_dir)
        self.shutdown_timeout = shutdown_timeout
        self.max_state_age_hours = max_state_age_hours
        self.state = ShutdownState.RUNNING
        self.shutdown_reason: ShutdownReason | None = None
        self.shutdown_handlers: dict[str, Callable[[], Awaitable[None]]] = {}
        self.active_tasks: dict[str, Any] = {}
        self.pending_jobs: list[dict[str, Any]] = []
        self.websocket_connections: dict[str, Any] = {}
        self.start_time = time.time()
        self._shutdown_event = asyncio.Event()
        self._tracer = get_tracer("graceful_shutdown")

    async def initialize(self) -> None:
        """Initialize the shutdown manager and check for recovery."""
        # Create state directory
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Setup signal handlers
        self._setup_signal_handlers()

        # Check for state to recover
        await self._check_recovery()

        logger.info("Graceful shutdown manager initialized")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()

        # Handle SIGTERM (docker stop, kubernetes termination)
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(
            self._handle_signal(ShutdownReason.SIGNAL),
        ))

        # Handle SIGINT (Ctrl+C)
        loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(
            self._handle_signal(ShutdownReason.SIGNAL),
        ))

    async def _handle_signal(self, reason: ShutdownReason) -> None:
        """Handle shutdown signal."""
        logger.info(f"Received shutdown signal: {reason.value}")
        await self.shutdown(reason)

    def register_handler(
        self,
        name: str,
        handler: Callable[[], Awaitable[None]],
    ) -> None:
        """
        Register a shutdown handler.

        Args:
            name: Handler name
            handler: Async function to call on shutdown
        """
        self.shutdown_handlers[name] = handler
        logger.debug(f"Registered shutdown handler: {name}")

    def unregister_handler(self, name: str) -> None:
        """Unregister a shutdown handler."""
        if name in self.shutdown_handlers:
            del self.shutdown_handlers[name]
            logger.debug(f"Unregistered shutdown handler: {name}")

    def register_task(self, task_id: str, task_data: dict[str, Any]) -> None:
        """Register an active task for tracking."""
        self.active_tasks[task_id] = {
            **task_data,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.debug(f"Registered active task: {task_id}")

    def unregister_task(self, task_id: str) -> None:
        """Unregister a completed task."""
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
            logger.debug(f"Unregistered task: {task_id}")

    def register_websocket(self, connection_id: str, connection_data: dict[str, Any]) -> None:
        """Register a WebSocket connection for tracking."""
        self.websocket_connections[connection_id] = {
            **connection_data,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }

    def unregister_websocket(self, connection_id: str) -> None:
        """Unregister a WebSocket connection."""
        if connection_id in self.websocket_connections:
            del self.websocket_connections[connection_id]

    async def shutdown(self, reason: ShutdownReason = ShutdownReason.SIGNAL) -> None:
        """
        Perform graceful shutdown.

        Args:
            reason: Reason for shutdown
        """
        if self.state != ShutdownState.RUNNING:
            logger.warning(f"Shutdown already in progress: {self.state.value}")
            return

        logger.info(f"Starting graceful shutdown: {reason.value}")
        self.state = ShutdownState.SHUTTING_DOWN
        self.shutdown_reason = reason

        start_time = time.time()

        try:
            # Save state before shutdown
            await self._save_state()

            # Run all shutdown handlers with timeout
            shutdown_tasks = []
            for name, handler in self.shutdown_handlers.items():
                task = asyncio.create_task(
                    self._run_handler_with_timeout(name, handler),
                    name=f"shutdown_{name}",
                )
                shutdown_tasks.append(task)

            # Wait for all handlers with overall timeout
            if shutdown_tasks:
                _done, pending = await asyncio.wait(
                    shutdown_tasks,
                    timeout=self.shutdown_timeout,
                    return_when=asyncio.ALL_COMPLETED,
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

            # Close WebSocket connections
            await self._close_websockets()

            # Wait for active tasks to complete (with timeout)
            await self._wait_for_active_tasks()

            elapsed = time.time() - start_time
            logger.info(f"Graceful shutdown completed in {elapsed:.2f}s")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            self.state = ShutdownState.SHUTDOWN_COMPLETE
            self._shutdown_event.set()

    async def _run_handler_with_timeout(
        self,
        name: str,
        handler: Callable[[], Awaitable[None]],
    ) -> None:
        """Run a shutdown handler with timeout."""
        try:
            await asyncio.wait_for(handler(), timeout=10.0)
            logger.debug(f"Shutdown handler completed: {name}")
        except asyncio.TimeoutError:
            logger.error(f"Shutdown handler timed out: {name}")
        except Exception as e:
            logger.error(f"Shutdown handler failed: {name} - {e}")

    async def _save_state(self) -> None:
        """Save current state to disk for recovery."""
        state_file = self.state_dir / "shutdown_state.json"

        state_data = ShutdownStateData(
            active_tasks=list(self.active_tasks.values()),
            pending_jobs=self.pending_jobs,
            scheduled_tasks=[],  # Would be populated from scheduler
            websocket_connections=list(self.websocket_connections.values()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            shutdown_reason=self.shutdown_reason.value if self.shutdown_reason else None,
        )

        try:
            async with aiofiles.open(state_file, "w") as f:
                await f.write(json.dumps(asdict(state_data), indent=2))
            logger.info(f"State saved to {state_file}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    async def _check_recovery(self) -> None:
        """Check for state to recover from previous shutdown."""
        state_file = self.state_dir / "shutdown_state.json"

        if not state_file.exists():
            logger.info("No previous state found, starting fresh")
            return

        try:
            # Check state file age
            mtime = datetime.fromtimestamp(state_file.stat().st_mtime, tz=timezone.utc)
            age = datetime.now(timezone.utc) - mtime

            if age > timedelta(hours=self.max_state_age_hours):
                logger.info(f"State file too old ({age}), skipping recovery")
                return

            # Load and recover state
            async with aiofiles.open(state_file) as f:
                content = await f.read()
                state_data = json.loads(content)

            # Recover active tasks
            for task_data in state_data.get("active_tasks", []):
                await self._recover_task(task_data)

            # Recover pending jobs
            self.pending_jobs = state_data.get("pending_jobs", [])

            logger.info(f"Recovered {len(state_data.get('active_tasks', []))} tasks")

        except Exception as e:
            logger.error(f"Failed to recover state: {e}")

    async def _recover_task(self, task_data: dict[str, Any]) -> None:
        """
        Recover a task from previous state.

        Override this method to implement custom task recovery logic.
        """
        logger.info(f"Recovering task: {task_data.get('id', 'unknown')}")
        # Default implementation: log the task for manual review
        # Custom implementation would re-queue the task

    async def _close_websockets(self) -> None:
        """Close all WebSocket connections gracefully."""
        if not self.websocket_connections:
            return

        logger.info(f"Closing {len(self.websocket_connections)} WebSocket connections")

        # Notify all connections
        for connection_id, connection_data in list(self.websocket_connections.items()):
            try:
                # Send shutdown notification
                if "websocket" in connection_data:
                    websocket = connection_data["websocket"]
                    await websocket.send_json({
                        "type": "system_shutdown",
                        "message": "Server is shutting down gracefully",
                    })
            except Exception as e:
                logger.error(f"Failed to notify WebSocket {connection_id}: {e}")

        # Clear connections
        self.websocket_connections.clear()

    async def _wait_for_active_tasks(self) -> None:
        """Wait for active tasks to complete."""
        if not self.active_tasks:
            return

        logger.info(f"Waiting for {len(self.active_tasks)} active tasks to complete")

        # Wait up to shutdown_timeout for tasks to complete
        start = time.time()
        while self.active_tasks and (time.time() - start) < self.shutdown_timeout:
            await asyncio.sleep(0.5)

        if self.active_tasks:
            logger.warning(
                f"Forcing shutdown with {len(self.active_tasks)} tasks still active",
            )

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown to complete."""
        await self._shutdown_event.wait()

    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self.state != ShutdownState.RUNNING

    def get_status(self) -> dict[str, Any]:
        """Get current shutdown manager status."""
        return {
            "state": self.state.value,
            "shutdown_reason": self.shutdown_reason.value if self.shutdown_reason else None,
            "active_tasks": len(self.active_tasks),
            "pending_jobs": len(self.pending_jobs),
            "websocket_connections": len(self.websocket_connections),
            "uptime_seconds": time.time() - self.start_time,
        }


# Global shutdown manager instance
_shutdown_manager: GracefulShutdownManager | None = None


def get_shutdown_manager() -> GracefulShutdownManager:
    """Get or create the global shutdown manager instance."""
    global _shutdown_manager  # noqa: PLW0603
    if _shutdown_manager is None:
        _shutdown_manager = GracefulShutdownManager()
    return _shutdown_manager


def reset_shutdown_manager() -> None:
    """Reset the global shutdown manager (for testing)."""
    global _shutdown_manager  # noqa: PLW0603
    _shutdown_manager = None
