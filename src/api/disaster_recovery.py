"""Disaster Recovery API Endpoints.

This module provides REST API endpoints for disaster recovery operations,
including backup management, recovery operations, and disaster recovery workflows.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session

# Import telemetry
from traceloop.sdk.decorators import task

from src.api.database import get_db
from src.config import Config
from src.disaster_recovery import (
    BackupManager,
    BackupMetadata,
    BackupType,
    RecoveryManager,
)
from src.disaster_recovery.legacy import DisasterRecoveryOrchestrator
from src.utils.logger import get_logger
from src.utils.telemetry import get_tracer

# Initialize logger and telemetry
logger = get_logger(__name__)
tracer = get_tracer(__name__)

# Router setup
router = APIRouter(
    prefix="/disaster-recovery",
    tags=["disaster-recovery"],
    responses={404: {"description": "Not found"}},
)


# Pydantic models for API requests/responses
class BackupRequest(BaseModel):
    """Request model for creating backups."""

    backup_type: str = Field(
        ..., description="Type of backup: full, incremental, point_in_time",
    )
    force: bool = Field(False, description="Force backup even if not scheduled")
    timestamp: str | None = Field(
        None, description="Timestamp for point-in-time backup",
    )


class BackupResponse(BaseModel):
    """Response model for backup operations."""

    backup_id: str
    backup_type: str
    status: str
    timestamp: str
    size: int
    location: str
    message: str


class RecoveryRequest(BaseModel):
    """Request model for recovery operations."""

    backup_id: str = Field(..., description="ID of backup to restore")
    plan_id: str = Field("default", description="Recovery plan to use")
    target_location: str | None = Field(
        None, description="Target location for recovery",
    )


class RecoveryResponse(BaseModel):
    """Response model for recovery operations."""

    operation_id: str
    plan_id: str
    status: str
    start_time: str
    end_time: str | None
    backup_id: str
    target_location: str
    steps_completed: list[str]
    validation_results: dict[str, bool]
    error_message: str | None


class DisasterRecoveryRequest(BaseModel):
    """Request model for disaster recovery workflow."""

    disaster_type: str = Field(
        ...,
        description="Type of disaster: database_corruption, data_loss, system_failure, ransomware_attack",
    )
    plan_id: str = Field("default", description="Recovery plan to use")


class DisasterRecoveryResponse(BaseModel):
    """Response model for disaster recovery workflow."""

    success: bool
    disaster_type: str
    recovery_strategy: dict[str, Any]
    backup_id: str
    recovery_result: dict[str, Any]
    validation_result: dict[str, Any]
    completion_time: str | None
    failure_time: str | None
    error: str | None


class RecoveryPlanResponse(BaseModel):
    """Response model for recovery plans."""

    plan_id: str
    name: str
    description: str
    recovery_point_objective: int
    recovery_time_objective: int
    backup_locations: list[str]
    priority: str
    automated: bool
    test_frequency: str


class BackupListResponse(BaseModel):
    """Response model for backup lists."""

    backups: list[BackupMetadata]
    total: int
    available_types: list[str]


class RecoveryMetricsResponse(BaseModel):
    """Response model for recovery metrics."""

    rto_average: int
    rpo_average: int
    success_rate: float
    last_recovery_time: str | None
    backup_success_rate: float


class DisasterRecoveryAPI:
    """Main disaster recovery API class."""

    def __init__(self, config: Config):
        """Initialize the disaster recovery API.

        Args:
            config: Configuration object
        """
        self.config = config
        self.backup_manager = BackupManager(config)
        self.recovery_manager = RecoveryManager(config, self.backup_manager)
        self.orchestrator = DisasterRecoveryOrchestrator(config)

    @task(name="create_backup_endpoint")
    async def create_backup(
        self, backup_type: str, force: bool = False, timestamp: str | None = None,
    ) -> BackupResponse:
        """Create a backup of the specified type.

        Args:
            backup_type: Type of backup to create
            force: Force backup even if not scheduled
            timestamp: Timestamp for point-in-time backup

        Returns:
            Backup response with operation details
        """
        try:
            # Validate backup type
            try:
                backup_type_enum = BackupType(backup_type.lower())
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid backup type: {backup_type}. Valid types: {[bt.value for bt in BackupType]}",
                ) from e

            # Create backup based on type
            if backup_type_enum == BackupType.FULL:
                metadata = await self.backup_manager.create_full_backup(force=force)
            elif backup_type_enum == BackupType.INCREMENTAL:
                metadata = await self.backup_manager.create_incremental_backup()
            elif backup_type_enum == BackupType.POINT_IN_TIME:
                if timestamp:
                    try:
                        backup_timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00"),
                        )
                    except ValueError as e:
                        raise HTTPException(
                            status_code=400,
                            detail="Invalid timestamp format. Use ISO format.",
                        ) from e
                else:
                    backup_timestamp = None
                metadata = await self.backup_manager.create_point_in_time_backup(
                    timestamp=backup_timestamp,
                )
            else:
                raise HTTPException(
                    status_code=400, detail=f"Unsupported backup type: {backup_type}",
                )

            return BackupResponse(
                backup_id=metadata.backup_id,
                backup_type=metadata.backup_type.value,
                status=metadata.status.value,
                timestamp=metadata.timestamp.isoformat(),
                size=metadata.size,
                location=metadata.location,
                message="Backup created successfully",
            )

        except HTTPException:
            raise
        except (FileNotFoundError, OSError) as e:
            logger.error(f"File system error during backup creation: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Backup creation failed: {e!s}",
            ) from e
        except Exception as e:
            logger.error(f"Backup creation failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Backup creation failed: {e!s}",
            ) from e

    @task(name="list_backups_endpoint")
    async def list_backups(
        self, backup_type: str | None = None, limit: int = 50, offset: int = 0,
    ) -> BackupListResponse:
        """List available backups.

        Args:
            backup_type: Filter by backup type
            limit: Maximum number of backups to return
            offset: Offset for pagination

        Returns:
            List of backup metadata
        """
        try:
            # Validate backup type if provided
            backup_type_enum = None
            if backup_type:
                try:
                    backup_type_enum = BackupType(backup_type.lower())
                except ValueError as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid backup type: {backup_type}. Valid types: {[bt.value for bt in BackupType]}",
                    ) from e

            # Get backups
            backups = await self.backup_manager.list_backups(
                backup_type=backup_type_enum,
            )

            # Apply pagination
            total = len(backups)
            paginated_backups = backups[offset : offset + limit]

            return BackupListResponse(
                backups=paginated_backups,
                total=total,
                available_types=[bt.value for bt in BackupType],
            )

        except HTTPException:
            raise
        except (ValueError, TypeError) as e:
            logger.error(f"Validation error listing backups: {e}", exc_info=True)
            raise HTTPException(
                status_code=400, detail=f"Invalid request: {e!s}",
            ) from e
        except Exception as e:
            logger.error(f"Failed to list backups: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Failed to list backups: {e!s}",
            ) from e

    @task(name="get_backup_details_endpoint")
    async def get_backup_details(self, backup_id: str) -> BackupMetadata:
        """Get details for a specific backup.

        Args:
            backup_id: ID of backup to retrieve

        Returns:
            Backup metadata
        """
        try:
            metadata = await self.backup_manager._get_backup_metadata(backup_id)
            if not metadata:
                raise HTTPException(
                    status_code=404, detail=f"Backup not found: {backup_id}",
                )

            return metadata

        except HTTPException:
            raise
        except (OSError, FileNotFoundError) as e:
            logger.error(f"Backup file not found: {e}", exc_info=True)
            raise HTTPException(
                status_code=404, detail=f"Backup not found: {e!s}",
            ) from e
        except Exception as e:
            logger.error(f"Failed to get backup details: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Failed to get backup details: {e!s}",
            ) from e

    @task(name="validate_backup_endpoint")
    async def validate_backup(self, backup_id: str) -> dict[str, Any]:
        """Validate backup integrity.

        Args:
            backup_id: ID of backup to validate

        Returns:
            Validation results
        """
        try:
            validation_results = await self.backup_manager.validate_backup(backup_id)
            if not validation_results["valid"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Backup validation failed: {validation_results}",
                )

            return validation_results

        except HTTPException:
            raise
        except (OSError, FileNotFoundError) as e:
            logger.error(f"Backup validation failed (file error): {e}", exc_info=True)
            raise HTTPException(
                status_code=400, detail=f"Backup validation failed: {e!s}",
            ) from e
        except Exception as e:
            logger.error(f"Backup validation failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Backup validation failed: {e!s}",
            ) from e

    @task(name="delete_backup_endpoint")
    async def delete_backup(self, backup_id: str) -> dict[str, str]:
        """Delete a backup.

        Args:
            backup_id: ID of backup to delete

        Returns:
            Deletion confirmation
        """
        try:
            # Get backup metadata to verify it exists
            metadata = await self.backup_manager._get_backup_metadata(backup_id)
            if not metadata:
                raise HTTPException(
                    status_code=404, detail=f"Backup not found: {backup_id}",
                )

            # Delete backup file
            backup_file = Path(metadata.location)
            if backup_file.exists():  # noqa: ASYNC240
                backup_file.unlink()  # noqa: ASYNC240

            # Delete metadata file
            metadata_file = (
                self.backup_manager.backup_dir / f"{backup_id}_metadata.json"
            )
            if metadata_file.exists():
                metadata_file.unlink()

            # Delete from Redis if present
            if self.backup_manager.redis_client:
                key = f"backup:metadata:{backup_id}"
                self.backup_manager.redis_client.delete(key)

            return {"message": f"Backup {backup_id} deleted successfully"}

        except HTTPException:
            raise
        except (FileNotFoundError, OSError) as e:
            logger.error(f"File system error during backup deletion: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Backup deletion failed: {e!s}",
            ) from e
        except Exception as e:
            logger.error(f"Backup deletion failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Backup deletion failed: {e!s}",
            ) from e

    @task(name="execute_recovery_endpoint")
    async def execute_recovery(
        self,
        backup_id: str,
        plan_id: str = "default",
        target_location: str | None = None,
    ) -> RecoveryResponse:
        """Execute recovery operation.

        Args:
            backup_id: ID of backup to restore
            plan_id: Recovery plan to use
            target_location: Target location for recovery

        Returns:
            Recovery operation tracking
        """
        try:
            recovery_op = await self.recovery_manager.execute_recovery(
                backup_id=backup_id, plan_id=plan_id, target_location=target_location,
            )

            return RecoveryResponse(
                operation_id=recovery_op.operation_id,
                plan_id=recovery_op.plan_id,
                status=recovery_op.status.value,
                start_time=recovery_op.start_time.isoformat(),
                end_time=recovery_op.end_time.isoformat()
                if recovery_op.end_time
                else None,
                backup_id=recovery_op.backup_id,
                target_location=recovery_op.target_location,
                steps_completed=recovery_op.steps_completed,
                validation_results=recovery_op.validation_results,
                error_message=recovery_op.error_message,
            )

        except HTTPException:
            raise
        except (FileNotFoundError, OSError) as e:
            logger.error(f"File system error during recovery: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Recovery execution failed: {e!s}",
            ) from e
        except Exception as e:
            logger.error(f"Recovery execution failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Recovery execution failed: {e!s}",
            ) from e

    @task(name="get_recovery_status_endpoint")
    async def get_recovery_status(
        self, operation_id: str,
    ) -> RecoveryResponse | None:
        """Get status of a recovery operation.

        Args:
            operation_id: ID of recovery operation

        Returns:
            Recovery operation status
        """
        try:
            recovery_op = await self.recovery_manager.get_recovery_status(operation_id)
            if not recovery_op:
                return None

            return RecoveryResponse(
                operation_id=recovery_op.operation_id,
                plan_id=recovery_op.plan_id,
                status=recovery_op.status.value,
                start_time=recovery_op.start_time.isoformat(),
                end_time=recovery_op.end_time.isoformat()
                if recovery_op.end_time
                else None,
                backup_id=recovery_op.backup_id,
                target_location=recovery_op.target_location,
                steps_completed=recovery_op.steps_completed,
                validation_results=recovery_op.validation_results,
                error_message=recovery_op.error_message,
            )

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error getting recovery status: {e}", exc_info=True)
            raise HTTPException(
                status_code=400, detail=f"Invalid recovery status request: {e!s}",
            ) from e
        except Exception as e:
            logger.error(f"Failed to get recovery status: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Failed to get recovery status: {e!s}",
            ) from e

    @task(name="test_recovery_plan_endpoint")
    async def test_recovery_plan(self, plan_id: str) -> dict[str, Any]:
        """Test a recovery plan without affecting production.

        Args:
            plan_id: ID of recovery plan to test

        Returns:
            Test results
        """
        try:
            return await self.recovery_manager.test_recovery_plan(plan_id)

        except HTTPException:
            raise
        except (OSError, FileNotFoundError) as e:
            logger.error(f"Recovery plan test failed (file error): {e}", exc_info=True)
            raise HTTPException(
                status_code=400, detail=f"Recovery plan test failed: {e!s}",
            ) from e
        except Exception as e:
            logger.error(f"Recovery plan test failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Recovery plan test failed: {e!s}",
            ) from e

    @task(name="execute_disaster_recovery_endpoint")
    async def execute_disaster_recovery(
        self, disaster_type: str, plan_id: str = "default",
    ) -> DisasterRecoveryResponse:
        """Execute complete disaster recovery workflow.

        Args:
            disaster_type: Type of disaster
            plan_id: Recovery plan to use

        Returns:
            Disaster recovery results
        """
        try:
            results = await self.orchestrator.execute_disaster_recovery(
                disaster_type=disaster_type, plan_id=plan_id,
            )

            return DisasterRecoveryResponse(**results)

        except HTTPException:
            raise
        except (FileNotFoundError, OSError) as e:
            logger.error(f"File system error during disaster recovery: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Disaster recovery failed: {e!s}",
            ) from e
        except Exception as e:
            logger.error(f"Disaster recovery failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Disaster recovery failed: {e!s}",
            ) from e

    @task(name="get_recovery_plans_endpoint")
    async def get_recovery_plans(self) -> list[RecoveryPlanResponse]:
        """Get available recovery plans.

        Returns:
            List of recovery plans
        """
        try:
            return [RecoveryPlanResponse(
                        plan_id=plan.plan_id,
                        name=plan.name,
                        description=plan.description,
                        recovery_point_objective=plan.recovery_point_objective,
                        recovery_time_objective=plan.recovery_time_objective,
                        backup_locations=plan.backup_locations,
                        priority=plan.priority,
                        automated=plan.automated,
                        test_frequency=plan.test_frequency,
                    ) for plan in self.recovery_manager.recovery_plans.values()]

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error getting recovery plans: {e}", exc_info=True)
            raise HTTPException(
                status_code=400, detail=f"Invalid request: {e!s}",
            ) from e
        except Exception as e:
            logger.error(f"Failed to get recovery plans: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Failed to get recovery plans: {e!s}",
            ) from e

    @task(name="get_recovery_metrics_endpoint")
    async def get_recovery_metrics(self) -> RecoveryMetricsResponse:
        """Get disaster recovery metrics.

        Returns:
            Recovery metrics
        """
        try:
            metrics = await self.orchestrator.get_recovery_metrics()
            return RecoveryMetricsResponse(**metrics)

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error getting recovery metrics: {e}", exc_info=True)
            raise HTTPException(
                status_code=400, detail=f"Invalid request: {e!s}",
            ) from e
        except Exception as e:
            logger.error(f"Failed to get recovery metrics: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Failed to get recovery metrics: {e!s}",
            ) from e


# Initialize API instance
disaster_recovery_api = DisasterRecoveryAPI(Config())


# API endpoints
@router.post("/backups", response_model=BackupResponse)
@task(name="create_backup_api")
async def create_backup_endpoint(request: BackupRequest, db: Session = Depends(get_db)):  # noqa: B008
    """Create a backup of the specified type.

    - **backup_type**: Type of backup (full, incremental, point_in_time)
    - **force**: Force backup even if not scheduled (default: false)
    - **timestamp**: Timestamp for point-in-time backup (ISO format)
    """
    return await disaster_recovery_api.create_backup(
        backup_type=request.backup_type,
        force=request.force,
        timestamp=request.timestamp,
    )


@router.get("/backups", response_model=BackupListResponse)
@task(name="list_backups_api")
async def list_backups_endpoint(
    backup_type: str | None = Query(None, description="Filter by backup type"),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of backups to return",
    ),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),  # noqa: B008
):
    """List available backups.

    - **backup_type**: Filter by backup type (optional)
    - **limit**: Maximum number of backups to return (1-100, default: 50)
    - **offset**: Offset for pagination (default: 0)
    """
    return await disaster_recovery_api.list_backups(
        backup_type=backup_type, limit=limit, offset=offset,
    )


@router.get("/backups/{backup_id}", response_model=BackupMetadata)
@task(name="get_backup_details_api")
async def get_backup_details_endpoint(backup_id: str, db: Session = Depends(get_db)):  # noqa: B008
    """Get details for a specific backup.

    - **backup_id**: ID of backup to retrieve
    """
    return await disaster_recovery_api.get_backup_details(backup_id)


@router.post("/backups/{backup_id}/validate", response_model=dict[str, Any])
@task(name="validate_backup_api")
async def validate_backup_endpoint(backup_id: str, db: Session = Depends(get_db)):  # noqa: B008
    """Validate backup integrity.

    - **backup_id**: ID of backup to validate
    """
    return await disaster_recovery_api.validate_backup(backup_id)


@router.delete("/backups/{backup_id}", response_model=dict[str, str])
@task(name="delete_backup_api")
async def delete_backup_endpoint(backup_id: str, db: Session = Depends(get_db)):  # noqa: B008
    """Delete a backup.

    - **backup_id**: ID of backup to delete
    """
    return await disaster_recovery_api.delete_backup(backup_id)


@router.post("/recoveries", response_model=RecoveryResponse)
@task(name="execute_recovery_api")
async def execute_recovery_endpoint(
    request: RecoveryRequest, db: Session = Depends(get_db),  # noqa: B008
):
    """Execute recovery operation.

    - **backup_id**: ID of backup to restore
    - **plan_id**: Recovery plan to use (default: "default")
    - **target_location**: Target location for recovery (optional)
    """
    return await disaster_recovery_api.execute_recovery(
        backup_id=request.backup_id,
        plan_id=request.plan_id,
        target_location=request.target_location,
    )


@router.get("/recoveries/{operation_id}", response_model=RecoveryResponse | None)
@task(name="get_recovery_status_api")
async def get_recovery_status_endpoint(
    operation_id: str, db: Session = Depends(get_db),  # noqa: B008
):
    """Get status of a recovery operation.

    - **operation_id**: ID of recovery operation
    """
    return await disaster_recovery_api.get_recovery_status(operation_id)


@router.post("/recovery-plans/{plan_id}/test", response_model=dict[str, Any])
@task(name="test_recovery_plan_api")
async def test_recovery_plan_endpoint(plan_id: str, db: Session = Depends(get_db)):  # noqa: B008
    """Test a recovery plan without affecting production.

    - **plan_id**: ID of recovery plan to test
    """
    return await disaster_recovery_api.test_recovery_plan(plan_id)


@router.post("/disaster-recovery", response_model=DisasterRecoveryResponse)
@task(name="execute_disaster_recovery_api")
async def execute_disaster_recovery_endpoint(
    request: DisasterRecoveryRequest, db: Session = Depends(get_db),  # noqa: B008
):
    """Execute complete disaster recovery workflow.

    - **disaster_type**: Type of disaster (database_corruption, data_loss, system_failure, ransomware_attack)
    - **plan_id**: Recovery plan to use (default: "default")
    """
    return await disaster_recovery_api.execute_disaster_recovery(
        disaster_type=request.disaster_type, plan_id=request.plan_id,
    )


@router.get("/recovery-plans", response_model=list[RecoveryPlanResponse])
@task(name="get_recovery_plans_api")
async def get_recovery_plans_endpoint(db: Session = Depends(get_db)):  # noqa: B008
    """Get available recovery plans."""
    return await disaster_recovery_api.get_recovery_plans()


@router.get("/metrics", response_model=RecoveryMetricsResponse)
@task(name="get_recovery_metrics_api")
async def get_recovery_metrics_endpoint(db: Session = Depends(get_db)):  # noqa: B008
    """Get disaster recovery metrics."""
    return await disaster_recovery_api.get_recovery_metrics()


# Health check endpoint
@router.get("/health", response_model=dict[str, str])
@task(name="disaster_recovery_health_check")
async def health_check_endpoint(db: Session = Depends(get_db)):  # noqa: B008
    """Health check for disaster recovery system."""
    try:
        # Check backup directory
        backup_dir = Path(Config().BACKUP_DIR)
        backup_dir_ok = backup_dir.exists() and backup_dir.is_dir()  # noqa: ASYNC240

        # Check database connectivity
        db_ok = True
        try:
            db.execute(text("SELECT 1"))
        except (OperationalError, InterfaceError) as e:
            logger.debug(f"Database health check failed: {e}")
            db_ok = False
        except Exception as e:
            logger.debug(f"Database health check failed (unexpected): {e}")
            db_ok = False

        # Check Redis connectivity if configured
        redis_ok = True
        if Config().REDIS_URL:
            try:
                redis_client = disaster_recovery_api.backup_manager.redis_client
                if redis_client:
                    redis_client.ping()
            except (ConnectionError, TimeoutError) as e:
                logger.debug(f"Redis health check failed: {e}")
                redis_ok = False
            except Exception as e:
                logger.debug(f"Redis health check failed (unexpected): {e}")
                redis_ok = False

        # Check S3 connectivity if configured
        s3_ok = True
        if Config().AWS_S3_BACKUP_BUCKET:
            try:
                s3_client = disaster_recovery_api.backup_manager.s3_client
                if s3_client:
                    s3_client.head_bucket(Bucket=Config().AWS_S3_BACKUP_BUCKET)
            except (ConnectionError, TimeoutError, ClientError) as e:
                logger.debug(f"S3 health check failed: {e}")
                s3_ok = False
            except Exception as e:
                logger.debug(f"S3 health check failed (unexpected): {e}")
                s3_ok = False

        status = (
            "healthy" if all([backup_dir_ok, db_ok, redis_ok, s3_ok]) else "degraded"
        )

        return {
            "status": status,
            "backup_directory": "ok" if backup_dir_ok else "error",
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
            "s3": "ok" if s3_ok else "error",
            "timestamp": datetime.now().isoformat(),
        }

    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Health check validation error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
