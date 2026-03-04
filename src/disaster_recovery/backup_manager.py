"""
Backup Manager Module.

Manages backup operations for the platform including full, incremental,
and point-in-time backups.
"""

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException
import redis
from redis.exceptions import RedisError
import schedule
from sqlalchemy import create_engine
from traceloop.sdk.decorators import task

from src.config import Config
from src.utils.logger import get_logger

from .models import BackupMetadata, BackupStatus, BackupType

logger = get_logger(__name__)


class BackupManager:
    """Manages backup operations for the platform."""

    def __init__(self, config: Config):
        """Initialize the backup manager."""
        self.config = config
        self.backup_dir = Path(config.BACKUP_DIR)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.s3_client = None
        if config.AWS_S3_BACKUP_BUCKET:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
                region_name=config.AWS_REGION,
            )

        self.redis_client = None
        if config.REDIS_URL:
            self.redis_client = redis.from_url(config.REDIS_URL)

        self.db_engine = create_engine(config.DATABASE_URL)
        self._setup_schedules()

    def _setup_schedules(self):
        """Setup automated backup schedules."""
        schedule.every().day.at("02:00").do(self.create_full_backup)
        schedule.every().hour.do(self.create_incremental_backup)
        schedule.every().sunday.at("03:00").do(self.create_point_in_time_backup)

    @task(name="create_full_backup")
    async def create_full_backup(self, force: bool = False) -> BackupMetadata:
        """Create a full backup of the system."""
        backup_id = f"full_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = self.backup_dir / f"{backup_id}.tar.gz"

        try:
            logger.info(f"Starting full backup: {backup_id}")

            metadata = BackupMetadata(
                backup_id=backup_id,
                backup_type=BackupType.FULL,
                timestamp=datetime.now(),
                size=0,
                checksum="",
                location=str(backup_path),
                status=BackupStatus.IN_PROGRESS,
                retention_days=self.config.BACKUP_RETENTION_DAYS,
                compression_enabled=True,
                encryption_enabled=self.config.ENCRYPTION_ENABLED,
                database_version="1.0.0",
                schema_version="1.0.0",
            )

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                await self._backup_database(temp_path / "database.sqlite")
                await self._backup_configuration(temp_path / "config")
                await self._backup_logs(temp_path / "logs")
                await self._backup_uploads(temp_path / "uploads")

                await self._create_archive(temp_path, backup_path)

                metadata.checksum = await self._calculate_checksum(backup_path)
                metadata.size = backup_path.stat().st_size

                if self.s3_client and self.config.AWS_S3_BACKUP_BUCKET:
                    await self._upload_to_s3(backup_path, backup_id)

                metadata.status = BackupStatus.COMPLETED
                await self._store_backup_metadata(metadata)
                await self._cleanup_old_backups()

                logger.info(f"Full backup completed: {backup_id}")
                return metadata

        except Exception as e:
            logger.error(f"Full backup failed: {e}")
            metadata.status = BackupStatus.FAILED
            await self._store_backup_metadata(metadata)
            raise HTTPException(status_code=500, detail=f"Backup failed: {e!s}") from e

    @task(name="create_incremental_backup")
    async def create_incremental_backup(self) -> BackupMetadata:
        """Create an incremental backup."""
        backup_id = f"incremental_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = self.backup_dir / f"{backup_id}.tar.gz"

        try:
            logger.info(f"Starting incremental backup: {backup_id}")

            last_full_backup = await self._get_last_backup(BackupType.FULL)
            if not last_full_backup:
                return await self.create_full_backup()

            metadata = BackupMetadata(
                backup_id=backup_id,
                backup_type=BackupType.INCREMENTAL,
                timestamp=datetime.now(),
                size=0,
                checksum="",
                location=str(backup_path),
                status=BackupStatus.IN_PROGRESS,
                retention_days=self.config.BACKUP_RETENTION_DAYS,
                compression_enabled=True,
                encryption_enabled=self.config.ENCRYPTION_ENABLED,
                database_version="1.0.0",
                schema_version="1.0.0",
            )

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                await self._backup_incremental_data(temp_path, last_full_backup.timestamp)
                await self._create_archive(temp_path, backup_path)

                metadata.checksum = await self._calculate_checksum(backup_path)
                metadata.size = backup_path.stat().st_size
                metadata.status = BackupStatus.COMPLETED
                await self._store_backup_metadata(metadata)

                logger.info(f"Incremental backup completed: {backup_id}")
                return metadata

        except Exception as e:
            logger.error(f"Incremental backup failed: {e}")
            metadata.status = BackupStatus.FAILED
            await self._store_backup_metadata(metadata)
            raise HTTPException(status_code=500, detail=f"Incremental backup failed: {e!s}") from e

    @task(name="create_point_in_time_backup")
    async def create_point_in_time_backup(self, timestamp: datetime | None = None) -> BackupMetadata:
        """Create a point-in-time backup."""
        if not timestamp:
            timestamp = datetime.now()

        backup_id = f"point_in_time_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        backup_path = self.backup_dir / f"{backup_id}.tar.gz"

        try:
            logger.info(f"Starting point-in-time backup: {backup_id}")

            metadata = BackupMetadata(
                backup_id=backup_id,
                backup_type=BackupType.POINT_IN_TIME,
                timestamp=timestamp,
                size=0,
                checksum="",
                location=str(backup_path),
                status=BackupStatus.IN_PROGRESS,
                retention_days=self.config.BACKUP_RETENTION_DAYS * 3,
                compression_enabled=True,
                encryption_enabled=self.config.ENCRYPTION_ENABLED,
                database_version="1.0.0",
                schema_version="1.0.0",
            )

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                await self._create_point_in_time_snapshot(temp_path, timestamp)
                await self._create_archive(temp_path, backup_path)

                metadata.checksum = await self._calculate_checksum(backup_path)
                metadata.size = backup_path.stat().st_size
                metadata.status = BackupStatus.COMPLETED
                await self._store_backup_metadata(metadata)

                logger.info(f"Point-in-time backup completed: {backup_id}")
                return metadata

        except Exception as e:
            logger.error(f"Point-in-time backup failed: {e}")
            metadata.status = BackupStatus.FAILED
            await self._store_backup_metadata(metadata)
            raise HTTPException(status_code=500, detail=f"Point-in-time backup failed: {e!s}") from e

    async def _backup_database(self, backup_path: Path):
        """Backup the database."""
        try:
            db_path = Path(self.config.DATABASE_URL.replace("sqlite:///", ""))
            if db_path.exists():
                shutil.copy2(db_path, backup_path)
                logger.info("Database backup completed")
            else:
                logger.warning("Database file not found, creating empty backup")
                backup_path.touch()
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            raise

    async def _backup_configuration(self, backup_dir: Path):
        """Backup configuration files."""
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            config_files = ["config.py", ".env", "docker-compose.yml", "Dockerfile"]

            for config_file in config_files:
                src = Path(config_file)
                if src.exists():
                    shutil.copy2(src, backup_dir / src.name)

            marketplaces_dir = Path("data/marketplaces.json")
            if marketplaces_dir.exists():
                shutil.copy2(marketplaces_dir, backup_dir / "marketplaces.json")

            logger.info("Configuration backup completed")
        except Exception as e:
            logger.error(f"Configuration backup failed: {e}")
            raise

    async def _backup_logs(self, backup_dir: Path):
        """Backup log files."""
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            log_dir = Path("logs")
            if log_dir.exists():
                for log_file in log_dir.glob("*.log"):
                    if log_file.stat().st_mtime > (time.time() - 86400):
                        shutil.copy2(log_file, backup_dir / log_file.name)
            logger.info("Log backup completed")
        except Exception as e:
            logger.error(f"Log backup failed: {e}")
            raise

    async def _backup_uploads(self, backup_dir: Path):
        """Backup user uploads."""
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            uploads_dir = Path("uploads")
            if uploads_dir.exists():
                shutil.copytree(uploads_dir, backup_dir / "uploads", dirs_exist_ok=True)
            logger.info("Uploads backup completed")
        except Exception as e:
            logger.error(f"Uploads backup failed: {e}")
            raise

    async def _backup_incremental_data(self, backup_dir: Path, since: datetime):
        """Backup only data changed since the specified time."""
        try:
            await self._backup_database_changes(backup_dir / "database_changes.sqlite", since)
            await self._backup_new_files(backup_dir / "new_files", since)
            logger.info("Incremental data backup completed")
        except Exception as e:
            logger.error(f"Incremental data backup failed: {e}")
            raise

    async def _backup_database_changes(self, backup_path: Path, since: datetime):
        """Backup database changes since timestamp."""
        await self._backup_database(backup_path)

    async def _backup_new_files(self, backup_dir: Path, since: datetime):
        """Backup files modified since timestamp."""
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            directories = ["uploads", "logs", "data"]

            for directory in directories:
                dir_path = Path(directory)
                if dir_path.exists():
                    for file_path in dir_path.rglob("*"):
                        if file_path.is_file() and file_path.stat().st_mtime > since.timestamp():
                            relative_path = file_path.relative_to(directory)
                            dest_path = backup_dir / directory / relative_path
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(file_path, dest_path)
            logger.info("New files backup completed")
        except Exception as e:
            logger.error(f"New files backup failed: {e}")
            raise

    async def _create_point_in_time_snapshot(self, backup_dir: Path, timestamp: datetime):
        """Create a point-in-time snapshot."""
        try:
            await self._backup_database(backup_dir / "database_snapshot.sqlite")
            await self._backup_transaction_logs(backup_dir / "transaction_logs")
            timestamp_file = backup_dir / "timestamp.txt"
            timestamp_file.write_text(timestamp.isoformat())
            logger.info("Point-in-time snapshot completed")
        except Exception as e:
            logger.error(f"Point-in-time snapshot failed: {e}")
            raise

    async def _backup_transaction_logs(self, backup_dir: Path):
        """Backup database transaction logs."""
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            db_path = Path(self.config.DATABASE_URL.replace("sqlite:///", ""))
            wal_path = db_path.with_suffix(db_path.suffix + "-wal")
            if wal_path.exists():
                shutil.copy2(wal_path, backup_dir / "database-wal")
            logger.info("Transaction logs backup completed")
        except Exception as e:
            logger.error(f"Transaction logs backup failed: {e}")
            raise

    async def _create_archive(self, source_dir: Path, archive_path: Path):
        """Create compressed archive of backup data."""
        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(source_dir, arcname=".")
            logger.info(f"Archive created: {archive_path}")
        except Exception as e:
            logger.error(f"Archive creation failed: {e}")
            raise

    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Checksum calculation failed: {e}")
            raise

    async def _upload_to_s3(self, file_path: Path, backup_id: str):
        """Upload backup to S3."""
        try:
            s3_key = f"backups/{backup_id}/{file_path.name}"
            self.s3_client.upload_file(str(file_path), self.config.AWS_S3_BACKUP_BUCKET, s3_key)
            logger.info(f"Backup uploaded to S3: {s3_key}")
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise

    async def _store_backup_metadata(self, metadata: BackupMetadata):
        """Store backup metadata."""
        try:
            from dataclasses import asdict
            metadata_file = self.backup_dir / f"{metadata.backup_id}_metadata.json"
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(asdict(metadata), f, default=str, indent=2)

            if self.redis_client:
                await self._store_metadata_in_redis(metadata)
        except Exception as e:
            logger.error(f"Metadata storage failed: {e}")
            raise

    async def _store_metadata_in_redis(self, metadata: BackupMetadata):
        """Store backup metadata in Redis."""
        try:
            from dataclasses import asdict
            key = f"backup:metadata:{metadata.backup_id}"
            self.redis_client.setex(
                key,
                86400 * metadata.retention_days,
                json.dumps(asdict(metadata), default=str),
            )
        except RedisError as e:
            logger.error(f"Redis metadata storage failed: {e}")

    async def _get_last_backup(self, backup_type: BackupType) -> BackupMetadata | None:
        """Get the most recent backup of specified type."""
        try:
            if self.redis_client:
                keys = self.redis_client.keys("backup:metadata:*")
                for key in keys:
                    metadata_str = self.redis_client.get(key)
                    if metadata_str:
                        metadata_dict = json.loads(metadata_str)
                        if metadata_dict.get("backup_type") == backup_type.value:
                            return BackupMetadata(**metadata_dict)

            metadata_files = list(self.backup_dir.glob("*_metadata.json"))
            latest_backup = None
            latest_time = None

            for metadata_file in metadata_files:
                try:
                    with open(metadata_file, encoding="utf-8") as f:
                        metadata_dict = json.load(f)
                        if metadata_dict.get("backup_type") == backup_type.value:
                            backup_time = datetime.fromisoformat(metadata_dict["timestamp"])
                            if not latest_time or backup_time > latest_time:
                                latest_time = backup_time
                                latest_backup = BackupMetadata(**metadata_dict)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Invalid metadata file: {metadata_file} - {e}")
                    continue

            return latest_backup
        except Exception as e:
            logger.error(f"Failed to get last backup: {e}")
            return None

    async def _cleanup_old_backups(self):
        """Clean up expired backups."""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.BACKUP_RETENTION_DAYS)

            for backup_file in self.backup_dir.glob("*.tar.gz"):
                if backup_file.stat().st_mtime < cutoff_date.timestamp():
                    backup_file.unlink()
                    logger.info(f"Removed expired backup: {backup_file}")

            for metadata_file in self.backup_dir.glob("*_metadata.json"):
                try:
                    with open(metadata_file, encoding="utf-8") as f:
                        metadata = json.load(f)
                        backup_date = datetime.fromisoformat(metadata["timestamp"])
                        if backup_date < cutoff_date:
                            metadata_file.unlink()
                            logger.info(f"Removed expired metadata: {metadata_file}")
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Invalid metadata file: {metadata_file} - {e}")
                    metadata_file.unlink()

            if self.redis_client:
                keys = self.redis_client.keys("backup:metadata:*")
                for key in keys:
                    metadata_str = self.redis_client.get(key)
                    if metadata_str:
                        try:
                            metadata_dict = json.loads(metadata_str)
                            backup_date = datetime.fromisoformat(metadata_dict["timestamp"])
                            if backup_date < cutoff_date:
                                self.redis_client.delete(key)
                                logger.info(f"Removed expired Redis metadata: {key}")
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning(f"Invalid Redis metadata: {key} - {e}")
                            self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")

    async def list_backups(self, backup_type: BackupType | None = None) -> list[BackupMetadata]:
        """List available backups."""
        try:
            backups = []

            if self.redis_client:
                keys = self.redis_client.keys("backup:metadata:*")
                for key in keys:
                    metadata_str = self.redis_client.get(key)
                    if metadata_str:
                        metadata_dict = json.loads(metadata_str)
                        if not backup_type or metadata_dict.get("backup_type") == backup_type.value:
                            backups.append(BackupMetadata(**metadata_dict))

            metadata_files = list(self.backup_dir.glob("*_metadata.json"))
            for metadata_file in metadata_files:
                try:
                    with open(metadata_file, encoding="utf-8") as f:
                        metadata_dict = json.load(f)
                        backup_id = metadata_dict["backup_id"]
                        if not any(b.backup_id == backup_id for b in backups):
                            if not backup_type or metadata_dict.get("backup_type") == backup_type.value:
                                backups.append(BackupMetadata(**metadata_dict))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Invalid metadata file: {metadata_file} - {e}")
                    continue

            backups.sort(key=lambda x: x.timestamp, reverse=True)
            return backups
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []

    async def validate_backup(self, backup_id: str) -> dict[str, Any]:
        """Validate backup integrity."""
        try:
            metadata = await self._get_backup_metadata(backup_id)
            if not metadata:
                return {"valid": False, "error": "Backup not found"}

            results = {"backup_id": backup_id, "valid": True, "checks": {}}

            backup_file = Path(metadata.location)
            if not backup_file.exists():
                results["valid"] = False
                results["checks"]["file_exists"] = False
                return results

            results["checks"]["file_exists"] = True

            file_size = backup_file.stat().st_size
            results["checks"]["file_size"] = file_size == metadata.size

            calculated_checksum = await self._calculate_checksum(backup_file)
            results["checks"]["checksum"] = calculated_checksum == metadata.checksum

            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    with tarfile.open(backup_file, "r:gz") as tar:
                        tar.extractall(temp_path)  # noqa: S202 - Safe: extracting to isolated temp directory
                    extracted_files = list(temp_path.rglob("*"))
                    results["checks"]["archive_integrity"] = len(extracted_files) > 0
            except Exception as e:
                results["valid"] = False
                results["checks"]["archive_integrity"] = False
                results["checks"]["archive_error"] = str(e)

            return results
        except Exception as e:
            logger.error(f"Backup validation failed: {e}")
            return {"valid": False, "error": str(e)}

    async def _get_backup_metadata(self, backup_id: str) -> BackupMetadata | None:
        """Get backup metadata by ID."""
        try:
            if self.redis_client:
                key = f"backup:metadata:{backup_id}"
                metadata_str = self.redis_client.get(key)
                if metadata_str:
                    return BackupMetadata(**json.loads(metadata_str))

            metadata_file = self.backup_dir / f"{backup_id}_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, encoding="utf-8") as f:
                    return BackupMetadata(**json.load(f))
            return None
        except Exception as e:
            logger.error(f"Failed to get backup metadata: {e}")
            return None
