"""
Health Check and Monitoring System (Issue #101).

Provides comprehensive health monitoring for all system components including:
- Database connectivity
- Redis connectivity
- LLM service health
- External API health
- System resource monitoring
- Service dependency health

Usage:
    from src.utils.health_check import HealthMonitor

    monitor = HealthMonitor()
    health = await monitor.check_all()
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import time
from typing import Any

import aiohttp
import psutil
from sqlalchemy import text

from src.api.database import SessionLocal
from src.utils.logger import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ServiceType(str, Enum):
    """Types of services that can be monitored."""
    DATABASE = "database"
    REDIS = "redis"
    LLM_LOCAL = "llm_local"
    LLM_CLOUD = "llm_cloud"
    MARKETPLACE = "marketplace"
    VECTOR_DB = "vector_db"
    SCHEDULER = "scheduler"
    WORKER = "worker"
    API = "api"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    service: str
    service_type: ServiceType
    status: HealthStatus
    response_time_ms: float | None = None
    message: str = ""
    details: dict[str, Any] | None = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class SystemHealth:
    """Overall system health status."""
    status: HealthStatus
    timestamp: str
    checks: list[HealthCheckResult]
    system_metrics: dict[str, Any] | None = None
    uptime_seconds: float = 0.0
    version: str = "1.0.0"


class HealthMonitor:
    """
    Comprehensive health monitoring system.

    Features:
    - Multi-service health checking
    - Response time tracking
    - System resource monitoring
    - Dependency health verification
    - Graceful degradation detection
    """

    def __init__(
        self,
        database_url: str | None = None,
        redis_url: str | None = None,
        ollama_url: str = "http://localhost:11434",
        openai_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 5.0,
    ):
        self.database_url = database_url
        self.redis_url = redis_url
        self.ollama_url = ollama_url
        self.openai_url = openai_url
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.start_time = time.time()
        self._redis_client = None

    async def check_all(self) -> SystemHealth:
        """
        Perform comprehensive health check on all services.

        Returns:
            SystemHealth: Overall system health status
        """
        time.time()

        # Run all health checks concurrently
        tasks = [
            self.check_database(),
            self.check_redis(),
            self.check_llm_local(),
            self.check_llm_cloud(),
            self.check_vector_db(),
            self.check_scheduler(),
            self.check_worker(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        health_checks = []
        for result in results:
            if isinstance(result, Exception):
                health_checks.append(HealthCheckResult(
                    service="unknown",
                    service_type=ServiceType.API,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {result!s}",
                ))
            elif isinstance(result, HealthCheckResult):
                health_checks.append(result)

        # Add system metrics
        system_metrics = self._get_system_metrics()

        # Determine overall status
        overall_status = self._calculate_overall_status(health_checks)

        return SystemHealth(
            status=overall_status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            checks=health_checks,
            system_metrics=system_metrics,
            uptime_seconds=time.time() - self.start_time,
        )

    async def check_database(self) -> HealthCheckResult:
        """Check database connectivity and performance."""
        start = time.time()
        try:
            db = SessionLocal()
            try:
                # Test connection
                result = db.execute(text("SELECT 1"))
                result.fetchone()

                response_time = (time.time() - start) * 1000

                return HealthCheckResult(
                    service="PostgreSQL",
                    service_type=ServiceType.DATABASE,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=round(response_time, 2),
                    message="Database connection successful",
                )
            finally:
                db.close()
        except (TimeoutError, asyncio.TimeoutError) as e:
            return HealthCheckResult(
                service="PostgreSQL",
                service_type=ServiceType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection timeout: {e!s}",
            )
        except (ConnectionError, ConnectionRefusedError) as e:
            return HealthCheckResult(
                service="PostgreSQL",
                service_type=ServiceType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection error: {e!s}",
            )
        except Exception as e:
            logger.error(f"Database health check failed: {e}", exc_info=True)
            return HealthCheckResult(
                service="PostgreSQL",
                service_type=ServiceType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {e!s}",
            )

    async def check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity and performance."""
        start = time.time()
        try:
            import redis.asyncio as redis

            if self._redis_client is None:
                self._redis_client = redis.from_url(
                    self.redis_url or "redis://localhost:6379/0",
                    encoding="utf-8",
                    decode_responses=True,
                )

            # Test connection
            await self._redis_client.ping()
            response_time = (time.time() - start) * 1000

            return HealthCheckResult(
                service="Redis",
                service_type=ServiceType.REDIS,
                status=HealthStatus.HEALTHY,
                response_time_ms=round(response_time, 2),
                message="Redis connection successful",
            )
        except (TimeoutError, asyncio.TimeoutError) as e:
            return HealthCheckResult(
                service="Redis",
                service_type=ServiceType.REDIS,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection timeout: {e!s}",
            )
        except (ConnectionError, ConnectionRefusedError) as e:
            return HealthCheckResult(
                service="Redis",
                service_type=ServiceType.REDIS,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection error: {e!s}",
            )
        except Exception as e:
            logger.error(f"Redis health check failed: {e}", exc_info=True)
            return HealthCheckResult(
                service="Redis",
                service_type=ServiceType.REDIS,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {e!s}",
            )

    async def check_llm_local(self) -> HealthCheckResult:
        """Check local LLM (Ollama) health."""
        start = time.time()
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.ollama_url}/api/tags",
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("models", [])
                        response_time = (time.time() - start) * 1000

                        status = HealthStatus.HEALTHY if models else HealthStatus.DEGRADED
                        message = f"Ollama healthy with {len(models)} models" if models else "Ollama running but no models loaded"

                        return HealthCheckResult(
                            service="Ollama (Local LLM)",
                            service_type=ServiceType.LLM_LOCAL,
                            status=status,
                            response_time_ms=round(response_time, 2),
                            message=message,
                            details={"models": len(models)},
                        )
                    return HealthCheckResult(
                        service="Ollama (Local LLM)",
                        service_type=ServiceType.LLM_LOCAL,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Ollama returned status {response.status}",
                    )
        except (TimeoutError, asyncio.TimeoutError) as e:
            return HealthCheckResult(
                service="Ollama (Local LLM)",
                service_type=ServiceType.LLM_LOCAL,
                status=HealthStatus.UNHEALTHY,
                message=f"Ollama health check timeout: {e!s}",
            )
        except (ConnectionError, ConnectionRefusedError, aiohttp.ClientError) as e:
            return HealthCheckResult(
                service="Ollama (Local LLM)",
                service_type=ServiceType.LLM_LOCAL,
                status=HealthStatus.UNHEALTHY,
                message=f"Ollama connection error: {e!s}",
            )
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}", exc_info=True)
            return HealthCheckResult(
                service="Ollama (Local LLM)",
                service_type=ServiceType.LLM_LOCAL,
                status=HealthStatus.UNHEALTHY,
                message=f"Ollama health check failed: {e!s}",
            )

    async def check_llm_cloud(self) -> HealthCheckResult:
        """Check cloud LLM (OpenAI) health."""
        start = time.time()
        try:
            import os

            from openai import AsyncOpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return HealthCheckResult(
                    service="OpenAI (Cloud LLM)",
                    service_type=ServiceType.LLM_CLOUD,
                    status=HealthStatus.DEGRADED,
                    message="OpenAI API key not configured",
                )

            client = AsyncOpenAI(api_key=api_key)

            # Test with a simple request
            await client.models.list()
            response_time = (time.time() - start) * 1000

            return HealthCheckResult(
                service="OpenAI (Cloud LLM)",
                service_type=ServiceType.LLM_CLOUD,
                status=HealthStatus.HEALTHY,
                response_time_ms=round(response_time, 2),
                message="OpenAI API accessible",
            )
        except (TimeoutError, asyncio.TimeoutError) as e:
            return HealthCheckResult(
                service="OpenAI (Cloud LLM)",
                service_type=ServiceType.LLM_CLOUD,
                status=HealthStatus.UNHEALTHY,
                message=f"OpenAI API timeout: {e!s}",
            )
        except (ConnectionError, ConnectionRefusedError) as e:
            return HealthCheckResult(
                service="OpenAI (Cloud LLM)",
                service_type=ServiceType.LLM_CLOUD,
                status=HealthStatus.UNHEALTHY,
                message=f"OpenAI API connection error: {e!s}",
            )
        except Exception as e:
            logger.error(f"OpenAI API health check failed: {e}", exc_info=True)
            return HealthCheckResult(
                service="OpenAI (Cloud LLM)",
                service_type=ServiceType.LLM_CLOUD,
                status=HealthStatus.UNHEALTHY,
                message=f"OpenAI API health check failed: {e!s}",
            )

    async def check_vector_db(self) -> HealthCheckResult:
        """Check ChromaDB vector database health."""
        start = time.time()
        try:
            import chromadb

            client = chromadb.Client()
            collections = client.list_collections()
            response_time = (time.time() - start) * 1000

            return HealthCheckResult(
                service="ChromaDB (Vector DB)",
                service_type=ServiceType.VECTOR_DB,
                status=HealthStatus.HEALTHY,
                response_time_ms=round(response_time, 2),
                message=f"ChromaDB healthy with {len(collections)} collections",
                details={"collections": len(collections)},
            )
        except (TimeoutError, asyncio.TimeoutError) as e:
            return HealthCheckResult(
                service="ChromaDB (Vector DB)",
                service_type=ServiceType.VECTOR_DB,
                status=HealthStatus.UNHEALTHY,
                message=f"ChromaDB health check timeout: {e!s}",
            )
        except Exception as e:
            logger.error(f"ChromaDB health check failed: {e}", exc_info=True)
            return HealthCheckResult(
                service="ChromaDB (Vector DB)",
                service_type=ServiceType.VECTOR_DB,
                status=HealthStatus.UNHEALTHY,
                message=f"ChromaDB health check failed: {e!s}",
            )

    async def check_scheduler(self) -> HealthCheckResult:
        """Check scheduler service health."""
        try:
            from src.agent_execution.scheduler import TaskScheduler

            db = SessionLocal()
            try:
                scheduler = TaskScheduler(db)
                await scheduler.initialize()

                # Check if scheduler is running
                schedules = await scheduler.list_schedules()

                return HealthCheckResult(
                    service="Task Scheduler",
                    service_type=ServiceType.SCHEDULER,
                    status=HealthStatus.HEALTHY,
                    message=f"Scheduler running with {len(schedules)} active schedules",
                    details={"active_schedules": len(schedules)},
                )
            finally:
                db.close()
        except (TimeoutError, asyncio.TimeoutError) as e:
            return HealthCheckResult(
                service="Task Scheduler",
                service_type=ServiceType.SCHEDULER,
                status=HealthStatus.UNHEALTHY,
                message=f"Scheduler health check timeout: {e!s}",
            )
        except (ConnectionError, ConnectionRefusedError) as e:
            return HealthCheckResult(
                service="Task Scheduler",
                service_type=ServiceType.SCHEDULER,
                status=HealthStatus.UNHEALTHY,
                message=f"Scheduler connection error: {e!s}",
            )
        except Exception as e:
            logger.error(f"Scheduler health check failed: {e}", exc_info=True)
            return HealthCheckResult(
                service="Task Scheduler",
                service_type=ServiceType.SCHEDULER,
                status=HealthStatus.UNHEALTHY,
                message=f"Scheduler health check failed: {e!s}",
            )

    async def check_worker(self) -> HealthCheckResult:
        """Check background worker health."""
        try:
            # Check if worker process is running
            worker_running = False

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = " ".join(proc.info.get("cmdline", []) or [])
                    if "background_job_queue" in cmdline or "worker" in cmdline:
                        worker_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if worker_running:
                return HealthCheckResult(
                    service="Background Worker",
                    service_type=ServiceType.WORKER,
                    status=HealthStatus.HEALTHY,
                    message="Worker process is running",
                )
            return HealthCheckResult(
                service="Background Worker",
                service_type=ServiceType.WORKER,
                status=HealthStatus.DEGRADED,
                message="Worker process not detected",
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.debug(f"Worker check process access error: {e}", exc_info=True)
            return HealthCheckResult(
                service="Background Worker",
                service_type=ServiceType.WORKER,
                status=HealthStatus.DEGRADED,
                message="Worker process check encountered access errors",
            )
        except Exception as e:
            logger.error(f"Worker health check failed: {e}", exc_info=True)
            return HealthCheckResult(
                service="Background Worker",
                service_type=ServiceType.WORKER,
                status=HealthStatus.UNHEALTHY,
                message=f"Worker health check failed: {e!s}",
            )

    def _get_system_metrics(self) -> dict[str, Any]:
        """Get current system resource metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_mb": round(memory.available / 1024 / 1024, 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
            }
        except (ValueError, TypeError) as e:
            logger.error(f"System metrics validation error: {e}", exc_info=True)
            return {}
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}", exc_info=True)
            return {}

    def _calculate_overall_status(
        self,
        checks: list[HealthCheckResult],
    ) -> HealthStatus:
        """
        Calculate overall system health status.

        Rules:
        - If any critical service is UNHEALTHY -> UNHEALTHY
        - If any service is DEGRADED -> DEGRADED
        - Otherwise -> HEALTHY
        """
        critical_services = {
            ServiceType.DATABASE,
            ServiceType.REDIS,
            ServiceType.API,
        }

        has_unhealthy_critical = False
        has_degraded = False

        for check in checks:
            if check.status == HealthStatus.UNHEALTHY:
                if check.service_type in critical_services:
                    has_unhealthy_critical = True
                else:
                    has_degraded = True
            elif check.status == HealthStatus.DEGRADED:
                has_degraded = True

        if has_unhealthy_critical:
            return HealthStatus.UNHEALTHY
        if has_degraded:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    async def get_status_page(self) -> str:
        """
        Generate HTML status page.

        Returns:
            str: HTML status page
        """
        health = await self.check_all()

        status_colors = {
            HealthStatus.HEALTHY: "#28a745",
            HealthStatus.DEGRADED: "#ffc107",
            HealthStatus.UNHEALTHY: "#dc3545",
            HealthStatus.UNKNOWN: "#6c757d",
        }

        checks_html = ""
        for check in health.checks:
            color = status_colors.get(check.status, "#6c757d")
            checks_html += f"""
            <div class="check-item">
                <div class="check-header">
                    <span class="check-name">{check.service}</span>
                    <span class="check-status" style="background-color: {color}">
                        {check.status.value.upper()}
                    </span>
                </div>
                <div class="check-details">
                    <p>{check.message}</p>
                    {f'<p>Response Time: {check.response_time_ms}ms</p>' if check.response_time_ms else ''}
                </div>
            </div>
            """

        system_metrics_html = ""
        if health.system_metrics:
            metrics = health.system_metrics
            system_metrics_html = f"""
            <div class="system-metrics">
                <h3>System Metrics</h3>
                <div class="metric">CPU: {metrics.get('cpu_percent', 0)}%</div>
                <div class="metric">Memory: {metrics.get('memory_percent', 0)}%</div>
                <div class="metric">Disk: {metrics.get('disk_percent', 0)}%</div>
            </div>
            """

        overall_color = status_colors.get(health.status, "#6c757d")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>ArbitrageAI - System Health</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                    max-width: 800px;
                    margin: 40px auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .status-header {{
                    background-color: {overall_color};
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                    text-align: center;
                }}
                .check-item {{
                    background-color: white;
                    padding: 15px;
                    margin-bottom: 10px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .check-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 10px;
                }}
                .check-name {{
                    font-weight: bold;
                    font-size: 16px;
                }}
                .check-status {{
                    padding: 5px 10px;
                    border-radius: 4px;
                    color: white;
                    font-size: 12px;
                    font-weight: bold;
                }}
                .check-details {{
                    color: #666;
                    font-size: 14px;
                }}
                .system-metrics {{
                    background-color: white;
                    padding: 15px;
                    border-radius: 8px;
                    margin-top: 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .metric {{
                    display: inline-block;
                    margin-right: 20px;
                    padding: 10px;
                    background-color: #f8f9fa;
                    border-radius: 4px;
                }}
                .uptime {{
                    text-align: center;
                    margin-top: 20px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="status-header">
                <h1>System Health: {health.status.value.upper()}</h1>
                <p>Last updated: {health.timestamp}</p>
            </div>

            <h2>Service Health Checks</h2>
            {checks_html}

            {system_metrics_html}

            <div class="uptime">
                <p>Uptime: {health.uptime_seconds / 3600:.2f} hours</p>
                <p>Version: {health.version}</p>
            </div>
        </body>
        </html>
        """


# Global health monitor instance
_health_monitor: HealthMonitor | None = None


def get_health_monitor() -> HealthMonitor:
    """Get or create the global health monitor instance."""
    global _health_monitor  # noqa: PLW0603
    if _health_monitor is None:
        import os

        _health_monitor = HealthMonitor(
            database_url=os.getenv("DATABASE_URL"),
            redis_url=os.getenv("REDIS_URL"),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
            timeout_seconds=float(os.getenv("HEALTH_CHECK_TIMEOUT", "5.0")),
        )
    return _health_monitor
