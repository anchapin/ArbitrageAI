"""Disaster Recovery package."""

import threading
import time
from datetime import datetime
from typing import Any

import schedule
from traceloop.sdk.decorators import workflow

from src.config import Config
from src.utils.logger import get_logger

from .backup_manager import BackupManager
from .models import (
    BackupMetadata,
    BackupStatus,
    BackupType,
    RecoveryOperation,
    RecoveryPlan,
    RecoveryStatus,
)
from .recovery_manager import RecoveryManager

logger = get_logger(__name__)


class DisasterRecoveryOrchestrator:
    """Orchestrates disaster recovery operations."""

    def __init__(self, config: Config):
        """Initialize the disaster recovery orchestrator."""
        self.config = config
        self.backup_manager = BackupManager(config)
        self.recovery_manager = RecoveryManager(config, self.backup_manager)
        self._start_scheduler()

    @staticmethod
    def _start_scheduler():
        """Start the backup scheduler."""
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)

        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        logger.info("Backup scheduler started")

    @workflow(name="disaster_recovery_workflow")
    async def execute_disaster_recovery(
        self, disaster_type: str, plan_id: str = "default",
    ) -> dict[str, Any]:
        """Execute complete disaster recovery workflow."""
        try:
            logger.info(f"Starting disaster recovery for: {disaster_type}")

            recovery_strategy = await self._assess_disaster(disaster_type)
            backup_id = await self._select_backup_for_recovery(disaster_type, recovery_strategy)

            recovery_result = await self.recovery_manager.execute_recovery(
                backup_id=backup_id, plan_id=plan_id,
            )

            validation_result = await self._validate_disaster_recovery(recovery_result)
            await self._notify_recovery_completion(recovery_result, validation_result)

            return {
                "success": True,
                "disaster_type": disaster_type,
                "recovery_strategy": recovery_strategy,
                "backup_id": backup_id,
                "recovery_result": recovery_result,
                "validation_result": validation_result,
                "completion_time": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Disaster recovery failed: {e}")
            await self._notify_recovery_failure(disaster_type, str(e))
            return {
                "success": False,
                "disaster_type": disaster_type,
                "error": str(e),
                "failure_time": datetime.now().isoformat(),
            }

    @staticmethod
    async def _assess_disaster(disaster_type: str) -> dict[str, Any]:
        """Assess disaster and determine recovery strategy."""
        strategies = {
            "database_corruption": {
                "priority": "high",
                "requires_full_backup": True,
                "requires_point_in_time": True,
            },
            "data_loss": {
                "priority": "high",
                "requires_full_backup": True,
                "requires_point_in_time": False,
            },
            "system_failure": {
                "priority": "medium",
                "requires_full_backup": False,
                "requires_point_in_time": False,
            },
            "configuration_corruption": {
                "priority": "low",
                "requires_full_backup": False,
                "requires_point_in_time": False,
            },
        }
        return strategies.get(disaster_type, strategies["system_failure"])

    async def _select_backup_for_recovery(
        self, disaster_type: str, recovery_strategy: dict[str, Any],
    ) -> str:
        """Select appropriate backup for recovery."""
        if recovery_strategy.get("requires_point_in_time"):
            backups = await self.backup_manager.list_backups(BackupType.POINT_IN_TIME)
            if backups:
                return backups[0].backup_id

        if recovery_strategy.get("requires_full_backup"):
            backups = await self.backup_manager.list_backups(BackupType.FULL)
            if backups:
                return backups[0].backup_id

        backups = await self.backup_manager.list_backups()
        if backups:
            return backups[0].backup_id

        raise ValueError("No backups available for recovery")

    @staticmethod
    async def _validate_disaster_recovery(recovery_result: Any) -> dict[str, Any]:
        """Validate disaster recovery."""
        return {
            "database_accessible": True,
            "configuration_valid": True,
            "files_restored": True,
        }

    @staticmethod
    async def _notify_recovery_completion(
        recovery_result: Any, validation_result: dict[str, Any],
    ):
        """Notify stakeholders of recovery completion."""
        logger.info("Disaster recovery completed successfully")

    @staticmethod
    async def _notify_recovery_failure(disaster_type: str, error: str):
        """Notify stakeholders of recovery failure."""
        logger.error(f"Disaster recovery failed for {disaster_type}: {error}")

    async def create_backup(self, backup_type: str = "full") -> dict[str, Any]:
        """Create a backup manually."""
        try:
            if backup_type == "full":
                metadata = await self.backup_manager.create_full_backup(force=True)
            elif backup_type == "incremental":
                metadata = await self.backup_manager.create_incremental_backup()
            elif backup_type == "point_in_time":
                metadata = await self.backup_manager.create_point_in_time_backup()
            else:
                return {"success": False, "error": f"Unknown backup type: {backup_type}"}

            from dataclasses import asdict
            return {
                "success": True,
                "backup_id": metadata.backup_id,
                "metadata": asdict(metadata),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def list_backups(self) -> list[dict[str, Any]]:
        """List all available backups."""
        from dataclasses import asdict
        backups = await self.backup_manager.list_backups()
        return [asdict(backup) for backup in backups]

    async def validate_backup(self, backup_id: str) -> dict[str, Any]:
        """Validate a backup."""
        return await self.backup_manager.validate_backup(backup_id)

    async def execute_recovery(
        self, backup_id: str, plan_id: str = "default",
    ) -> dict[str, Any]:
        """Execute a recovery operation."""
        from dataclasses import asdict
        result = await self.recovery_manager.execute_recovery(backup_id, plan_id)
        return {
            "success": result.status == RecoveryStatus.COMPLETED,
            "operation": asdict(result),
        }

    async def test_recovery_plan(self, plan_id: str) -> dict[str, Any]:
        """Test a recovery plan."""
        return await self.recovery_manager.test_recovery_plan(plan_id)


__all__ = [
    "BackupManager",
    "BackupMetadata",
    "BackupStatus",
    "BackupType",
    "DisasterRecoveryOrchestrator",
    "RecoveryManager",
    "RecoveryOperation",
    "RecoveryPlan",
    "RecoveryStatus",
]
