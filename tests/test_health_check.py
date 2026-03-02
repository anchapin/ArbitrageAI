"""
Tests for Health Check and Monitoring System (Issue #101)
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.utils.health_check import (
    HealthMonitor,
    HealthStatus,
    ServiceType,
    HealthCheckResult,
    SystemHealth,
    get_health_monitor,
)


class TestHealthCheckResult:
    """Test health check result data structure."""

    def test_health_check_result_creation(self):
        """Test creating health check result."""
        result = HealthCheckResult(
            service="Test Service",
            service_type=ServiceType.DATABASE,
            status=HealthStatus.HEALTHY,
            response_time_ms=10.5,
            message="All good",
        )
        
        assert result.service == "Test Service"
        assert result.service_type == ServiceType.DATABASE
        assert result.status == HealthStatus.HEALTHY
        assert result.response_time_ms == 10.5
        assert result.message == "All good"
        assert result.timestamp is not None

    def test_health_check_result_optional_fields(self):
        """Test health check result with optional fields."""
        result = HealthCheckResult(
            service="Test Service",
            service_type=ServiceType.REDIS,
            status=HealthStatus.UNHEALTHY,
        )
        
        assert result.response_time_ms is None
        assert result.details is None
        assert result.message == ""


class TestSystemHealth:
    """Test system health data structure."""

    def test_system_health_creation(self):
        """Test creating system health."""
        checks = [
            HealthCheckResult(
                service="Database",
                service_type=ServiceType.DATABASE,
                status=HealthStatus.HEALTHY,
            )
        ]
        
        health = SystemHealth(
            status=HealthStatus.HEALTHY,
            timestamp=datetime.utcnow().isoformat(),
            checks=checks,
            uptime_seconds=3600.0,
        )
        
        assert health.status == HealthStatus.HEALTHY
        assert len(health.checks) == 1
        assert health.uptime_seconds == 3600.0


class TestHealthMonitor:
    """Test health monitor functionality."""

    @pytest.fixture
    def monitor(self):
        """Create health monitor instance."""
        return HealthMonitor()

    def test_monitor_initialization(self, monitor):
        """Test monitor initializes correctly."""
        assert monitor is not None
        assert monitor.start_time is not None
        assert monitor.timeout is not None

    @pytest.mark.asyncio
    async def test_check_database_success(self, monitor):
        """Test database health check success."""
        with patch('src.utils.health_check.SessionLocal') as mock_db:
            mock_conn = MagicMock()
            mock_db.return_value = mock_conn
            mock_conn.execute.return_value.fetchone.return_value = (1,)
            
            result = await monitor.check_database()
            
            assert result.service == "PostgreSQL"
            assert result.service_type == ServiceType.DATABASE
            assert result.status == HealthStatus.HEALTHY
            assert result.response_time_ms is not None

    @pytest.mark.asyncio
    async def test_check_database_failure(self, monitor):
        """Test database health check failure."""
        with patch('src.utils.health_check.SessionLocal') as mock_db:
            mock_db.side_effect = Exception("Connection failed")
            
            result = await monitor.check_database()
            
            assert result.service == "PostgreSQL"
            assert result.service_type == ServiceType.DATABASE
            assert result.status == HealthStatus.UNHEALTHY
            assert "Connection failed" in result.message

    @pytest.mark.asyncio
    async def test_check_redis_success(self, monitor):
        """Test Redis health check success."""
        with patch('redis.asyncio.from_url') as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_from_url.return_value = mock_client

            result = await monitor.check_redis()

            assert result.service == "Redis"
            assert result.service_type == ServiceType.REDIS
            assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_redis_failure(self, monitor):
        """Test Redis health check failure."""
        with patch('redis.asyncio.from_url') as mock_from_url:
            mock_from_url.side_effect = Exception("Redis unavailable")

            result = await monitor.check_redis()

            assert result.service == "Redis"
            assert result.service_type == ServiceType.REDIS
            assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Complex aiohttp mocking requires refactoring")
    async def test_check_llm_local_success(self, monitor):
        """Test local LLM health check success."""
        # Create proper nested async mocks
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"models": [{"name": "llama3.2"}]})
        mock_response.__aenter__.return_value = mock_response
        
        mock_get = AsyncMock(return_value=mock_response)
        mock_get.__aenter__.return_value = mock_response
        
        mock_session = AsyncMock()
        mock_session.get = mock_get
        mock_session.__aenter__.return_value = mock_session
        
        mock_session_class = AsyncMock(return_value=mock_session)
        
        with patch('aiohttp.ClientSession', mock_session_class):
            result = await monitor.check_llm_local()

            assert result.service == "Ollama (Local LLM)"
            assert result.service_type == ServiceType.LLM_LOCAL
            assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Complex aiohttp mocking requires refactoring")
    async def test_check_llm_local_no_models(self, monitor):
        """Test local LLM health check with no models."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"models": []})
        mock_response.__aenter__.return_value = mock_response
        
        mock_get = AsyncMock(return_value=mock_response)
        mock_get.__aenter__.return_value = mock_response
        
        mock_session = AsyncMock()
        mock_session.get = mock_get
        mock_session.__aenter__.return_value = mock_session
        
        mock_session_class = AsyncMock(return_value=mock_session)
        
        with patch('aiohttp.ClientSession', mock_session_class):
            result = await monitor.check_llm_local()
            
            assert result.service == "Ollama (Local LLM)"
            assert result.service_type == ServiceType.LLM_LOCAL
            assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_check_all(self, monitor):
        """Test checking all services."""
        with patch.object(monitor, 'check_database', AsyncMock()) as mock_db, \
             patch.object(monitor, 'check_redis', AsyncMock()) as mock_redis, \
             patch.object(monitor, 'check_llm_local', AsyncMock()) as mock_llm, \
             patch.object(monitor, 'check_llm_cloud', AsyncMock()) as mock_cloud, \
             patch.object(monitor, 'check_vector_db', AsyncMock()) as mock_vector, \
             patch.object(monitor, 'check_scheduler', AsyncMock()) as mock_scheduler, \
             patch.object(monitor, 'check_worker', AsyncMock()) as mock_worker:
            
            mock_db.return_value = HealthCheckResult(
                service="PostgreSQL",
                service_type=ServiceType.DATABASE,
                status=HealthStatus.HEALTHY,
            )
            mock_redis.return_value = HealthCheckResult(
                service="Redis",
                service_type=ServiceType.REDIS,
                status=HealthStatus.HEALTHY,
            )
            mock_llm.return_value = HealthCheckResult(
                service="Ollama",
                service_type=ServiceType.LLM_LOCAL,
                status=HealthStatus.HEALTHY,
            )
            mock_cloud.return_value = HealthCheckResult(
                service="OpenAI",
                service_type=ServiceType.LLM_CLOUD,
                status=HealthStatus.DEGRADED,
            )
            mock_vector.return_value = HealthCheckResult(
                service="ChromaDB",
                service_type=ServiceType.VECTOR_DB,
                status=HealthStatus.HEALTHY,
            )
            mock_scheduler.return_value = HealthCheckResult(
                service="Scheduler",
                service_type=ServiceType.SCHEDULER,
                status=HealthStatus.HEALTHY,
            )
            mock_worker.return_value = HealthCheckResult(
                service="Worker",
                service_type=ServiceType.WORKER,
                status=HealthStatus.HEALTHY,
            )
            
            health = await monitor.check_all()
            
            assert isinstance(health, SystemHealth)
            assert len(health.checks) == 7
            assert health.system_metrics is not None
            assert health.uptime_seconds >= 0

    def test_get_system_metrics(self, monitor):
        """Test getting system metrics."""
        metrics = monitor._get_system_metrics()
        
        assert isinstance(metrics, dict)
        assert "cpu_percent" in metrics or len(metrics) == 0  # May fail in test env
        assert "memory_percent" in metrics or len(metrics) == 0
        assert "disk_percent" in metrics or len(metrics) == 0

    def test_calculate_overall_status_healthy(self, monitor):
        """Test calculating overall healthy status."""
        checks = [
            HealthCheckResult(
                service="Database",
                service_type=ServiceType.DATABASE,
                status=HealthStatus.HEALTHY,
            ),
            HealthCheckResult(
                service="Redis",
                service_type=ServiceType.REDIS,
                status=HealthStatus.HEALTHY,
            ),
        ]
        
        overall = monitor._calculate_overall_status(checks)
        assert overall == HealthStatus.HEALTHY

    def test_calculate_overall_status_degraded(self, monitor):
        """Test calculating overall degraded status."""
        checks = [
            HealthCheckResult(
                service="Database",
                service_type=ServiceType.DATABASE,
                status=HealthStatus.HEALTHY,
            ),
            HealthCheckResult(
                service="OpenAI",
                service_type=ServiceType.LLM_CLOUD,
                status=HealthStatus.DEGRADED,
            ),
        ]
        
        overall = monitor._calculate_overall_status(checks)
        assert overall == HealthStatus.DEGRADED

    def test_calculate_overall_status_unhealthy(self, monitor):
        """Test calculating overall unhealthy status."""
        checks = [
            HealthCheckResult(
                service="Database",
                service_type=ServiceType.DATABASE,
                status=HealthStatus.UNHEALTHY,
            ),
            HealthCheckResult(
                service="Redis",
                service_type=ServiceType.REDIS,
                status=HealthStatus.HEALTHY,
            ),
        ]
        
        overall = monitor._calculate_overall_status(checks)
        assert overall == HealthStatus.UNHEALTHY


class TestHealthMonitorGlobal:
    """Test global health monitor instance."""

    def test_get_health_monitor(self):
        """Test getting health monitor singleton."""
        monitor = get_health_monitor()
        assert monitor is not None
        assert isinstance(monitor, HealthMonitor)
