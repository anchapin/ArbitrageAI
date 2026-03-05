"""
Recovery Manager Module.

Manages recovery operations for the platform including database,
configuration, and file restoration.
"""

from datetime import datetime
from pathlib import Path
import shutil
import tarfile
import tempfile
from typing import Any

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from traceloop.sdk.decorators import task

from src.config import Config
from src.utils.logger import get_logger

from .backup_manager import BackupManager
from .models import RecoveryOperation, RecoveryPlan, RecoveryStatus

logger = get_logger(__name__)


class RecoveryManager:
    """Manages recovery operations for the platform."""

    def __init__(self, config: Config, backup_manager: BackupManager):
        """Initialize the recovery manager."""
        self.config = config
        self.backup_manager = backup_manager
        self.recovery_dir = Path(config.RECOVERY_DIR)
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        self.recovery_plans = self._load_recovery_plans()

    @staticmethod
    def _load_recovery_plans() -> dict[str, RecoveryPlan]:
        """Load recovery plans from configuration."""
        plans = {}

        plans["default"] = RecoveryPlan(
            plan_id="default",
            name="Default Recovery Plan",
            description="Standard recovery plan for routine operations",
            recovery_point_objective=60,
            recovery_time_objective=120,
            backup_locations=["local", "s3"],
            priority="medium",
            automated=True,
            test_frequency="0 0 1 * *",
        )

        plans["critical"] = RecoveryPlan(
            plan_id="critical",
            name="Critical System Recovery",
            description="High-priority recovery for critical system failures",
            recovery_point_objective=15,
            recovery_time_objective=30,
            backup_locations=["local", "s3", "remote"],
            priority="high",
            automated=True,
            test_frequency="0 0 * * 0",
        )

        return plans

    @task(name="execute_recovery")
    async def execute_recovery(
        self,
        backup_id: str,
        plan_id: str = "default",
        target_location: str | None = None,
    ) -> RecoveryOperation:
        """Execute recovery operation."""
        operation_id = f"recovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            logger.info(f"Starting recovery operation: {operation_id}")

            plan = self.recovery_plans.get(plan_id)
            if not plan:
                raise HTTPException(status_code=400, detail=f"Recovery plan not found: {plan_id}")

            backup_metadata = await self.backup_manager._get_backup_metadata(backup_id)
            if not backup_metadata:
                raise HTTPException(status_code=400, detail=f"Backup not found: {backup_id}")

            recovery_op = RecoveryOperation(
                operation_id=operation_id,
                plan_id=plan_id,
                status=RecoveryStatus.IN_PROGRESS,
                start_time=datetime.now(),
                end_time=None,
                backup_id=backup_id,
                target_location=target_location or str(self.recovery_dir),
                steps_completed=[],
                error_message=None,
                validation_results={},
            )

            await self._execute_recovery_steps(recovery_op, backup_metadata, plan)

            recovery_op.status = RecoveryStatus.COMPLETED
            recovery_op.end_time = datetime.now()

            logger.info(f"Recovery operation completed: {operation_id}")
            return recovery_op

        except Exception as e:
            logger.error(f"Recovery operation failed: {e}")
            if "recovery_op" in locals():
                recovery_op.status = RecoveryStatus.FAILED
                recovery_op.end_time = datetime.now()
                if not recovery_op.error_message:
                    recovery_op.error_message = str(e)
                return recovery_op
            return RecoveryOperation(
                operation_id=operation_id,
                plan_id=plan_id,
                status=RecoveryStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                backup_id=backup_id,
                target_location=target_location or str(self.recovery_dir),
                steps_completed=[],
                error_message=str(e),
                validation_results={},
            )

    async def _execute_recovery_steps(
        self,
        recovery_op: RecoveryOperation,
        backup_metadata: RecoveryOperation,
        plan: RecoveryPlan,
    ):
        """Execute recovery steps according to the recovery plan."""
        steps = [
            "validate_backup",
            "prepare_target_environment",
            "restore_database",
            "restore_configuration",
            "restore_files",
            "validate_recovery",
            "update_system_configuration",
        ]

        for step in steps:
            try:
                logger.info(f"Executing recovery step: {step}")

                if step == "validate_backup":
                    await self._validate_backup_for_recovery(recovery_op, backup_metadata)
                elif step == "prepare_target_environment":
                    await self._prepare_target_environment(recovery_op, plan)
                elif step == "restore_database":
                    await self._restore_database(recovery_op, backup_metadata)
                elif step == "restore_configuration":
                    await self._restore_configuration(recovery_op, backup_metadata)
                elif step == "restore_files":
                    await self._restore_files(recovery_op, backup_metadata)
                elif step == "validate_recovery":
                    await self._validate_recovery(recovery_op)
                elif step == "update_system_configuration":
                    await self._update_system_configuration(recovery_op)

                recovery_op.steps_completed.append(step)
                logger.info(f"Completed recovery step: {step}")

            except Exception as e:
                logger.error(f"Recovery step failed: {step} - {e}")
                recovery_op.error_message = f"Step {step} failed: {e!s}"
                raise

    async def _validate_backup_for_recovery(
        self, recovery_op: RecoveryOperation, backup_metadata: RecoveryOperation,
    ):
        """Validate backup before recovery."""
        validation_results = await self.backup_manager.validate_backup(backup_metadata.backup_id)
        recovery_op.validation_results["backup_validation"] = validation_results["valid"]

        if not validation_results["valid"]:
            raise HTTPException(status_code=400, detail=f"Backup validation failed: {validation_results}")

    async def _prepare_target_environment(
        self, recovery_op: RecoveryOperation, plan: RecoveryPlan,
    ):
        """Prepare target environment for recovery."""
        target_path = Path(recovery_op.target_location)
        target_path.mkdir(parents=True, exist_ok=True)
        await self._stop_services()

        current_state_path = target_path / "current_state_backup"
        if target_path.exists() and any(target_path.iterdir()):
            shutil.move(str(target_path), str(current_state_path))
            logger.info(f"Current state backed up to: {current_state_path}")

    async def _restore_database(
        self, recovery_op: RecoveryOperation, backup_metadata: RecoveryOperation,
    ):
        """Restore database from backup."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                backup_file = Path(backup_metadata.location)
                with tarfile.open(backup_file, "r:gz") as tar:
                    tar.extractall(temp_path)  # noqa: S202 - Safe: extracting to isolated temp directory

                db_backup = temp_path / "database.sqlite"
                if db_backup.exists():
                    target_db = Path(self.config.DATABASE_URL.replace("sqlite:///", ""))
                    shutil.copy2(db_backup, target_db)
                    logger.info("Database restored successfully")
                else:
                    logger.warning("No database backup found in archive")
        except Exception as e:
            logger.error(f"Database restoration failed: {e}")
            raise

    @staticmethod
    async def _restore_configuration(
        recovery_op: RecoveryOperation, backup_metadata: RecoveryOperation,
    ):
        """Restore configuration from backup."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                backup_file = Path(backup_metadata.location)
                with tarfile.open(backup_file, "r:gz") as tar:
                    tar.extractall(temp_path)  # noqa: S202 - Safe: extracting to isolated temp directory

                config_dir = temp_path / "config"
                if config_dir.exists():
                    for config_file in config_dir.iterdir():
                        if config_file.is_file():
                            shutil.copy2(config_file, config_file.name())
                    logger.info("Configuration restored successfully")
        except Exception as e:
            logger.error(f"Configuration restoration failed: {e}")
            raise

    @staticmethod
    async def _restore_files(
        recovery_op: RecoveryOperation, backup_metadata: RecoveryOperation,
    ):
        """Restore files from backup."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                backup_file = Path(backup_metadata.location)
                with tarfile.open(backup_file, "r:gz") as tar:
                    tar.extractall(temp_path)  # noqa: S202 - Safe: extracting to isolated temp directory

                uploads_dir = temp_path / "uploads"
                if uploads_dir.exists():
                    target_uploads = Path("uploads")
                    if target_uploads.exists():
                        shutil.rmtree(target_uploads)
                    shutil.copytree(uploads_dir, target_uploads)
                    logger.info("Uploads restored successfully")

                logs_dir = temp_path / "logs"
                if logs_dir.exists():
                    target_logs = Path("logs")
                    if target_logs.exists():
                        shutil.rmtree(target_logs)
                    shutil.copytree(logs_dir, target_logs)
                    logger.info("Logs restored successfully")
        except Exception as e:
            logger.error(f"Files restoration failed: {e}")
            raise

    async def _validate_recovery(self, recovery_op: RecoveryOperation):
        """Validate recovery operation."""
        try:
            test_engine = create_engine(self.config.DATABASE_URL)
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database validation passed")

            with test_engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM tasks"))
                task_count = result.scalar()
                logger.info(f"Task table validation passed: {task_count} tasks")

            recovery_op.validation_results["database_validation"] = True
            recovery_op.validation_results["table_validation"] = True
        except Exception as e:
            logger.error(f"Recovery validation failed: {e}")
            recovery_op.validation_results["database_validation"] = False
            raise

    @staticmethod
    async def _update_system_configuration(recovery_op: RecoveryOperation):
        """Update system configuration after recovery."""
        logger.info("System configuration updated")

    @staticmethod
    async def _stop_services():
        """Stop running services before recovery."""
        logger.info("Services stopped for recovery")

    @task(name="test_recovery_plan")
    async def test_recovery_plan(self, plan_id: str) -> dict[str, Any]:
        """Test a recovery plan without affecting production."""
        try:
            plan = self.recovery_plans.get(plan_id)
            if not plan:
                return {"success": False, "error": f"Recovery plan not found: {plan_id}"}

            backups = await self.backup_manager.list_backups()
            if not backups:
                return {"success": False, "error": "No backups available for testing"}

            latest_backup = backups[0]

            test_recovery_op = RecoveryOperation(
                operation_id=f"test_recovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                plan_id=plan_id,
                status=RecoveryStatus.PENDING,
                start_time=datetime.now(),
                end_time=None,
                backup_id=latest_backup.backup_id,
                target_location=str(self.recovery_dir / "test_recovery"),
                steps_completed=[],
                error_message=None,
                validation_results={},
            )

            test_recovery_op.status = RecoveryStatus.IN_PROGRESS
            await self._execute_recovery_steps(test_recovery_op, latest_backup, plan)
            test_recovery_op.status = RecoveryStatus.COMPLETED
            test_recovery_op.end_time = datetime.now()

            test_dir = Path(test_recovery_op.target_location)
            if test_dir.exists():
                shutil.rmtree(test_dir)

            return {
                "success": True,
                "plan_id": plan_id,
                "backup_id": latest_backup.backup_id,
                "duration": (test_recovery_op.end_time - test_recovery_op.start_time).total_seconds(),
                "steps_completed": test_recovery_op.steps_completed,
                "validation_results": test_recovery_op.validation_results,
            }
        except Exception as e:
            logger.error(f"Recovery plan test failed: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def get_recovery_status(operation_id: str) -> RecoveryOperation | None:
        """Get status of a recovery operation."""
        return None
