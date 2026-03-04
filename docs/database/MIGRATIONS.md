# Database Migrations Guide

This document provides comprehensive guidance on managing database migrations using Alembic in the ArbitrageAI project.

## Overview

The project uses [Alembic](https://alembic.sqlalchemy.org/) for database schema version control and migrations. This allows for:

- **Version Control**: Track schema changes alongside code
- **Safe Deployments**: Apply schema changes consistently across environments
- **Rollback Capability**: Revert schema changes if needed
- **Team Collaboration**: Ensure all developers have the same schema
- **Production Safety**: Reliable schema updates in production

## Quick Start

### Apply Pending Migrations
```bash
python scripts/migrate.py upgrade
```

### Rollback Last Migration
```bash
python scripts/migrate.py downgrade
```

### Check Current Version
```bash
python scripts/migrate.py current
```

### View Migration History
```bash
python scripts/migrate.py history
```

## Installation

Alembic is included in the project dependencies. If you need to install it separately:

```bash
pip install alembic>=1.13.0
```

## Configuration

### Files

| File | Purpose |
|------|---------|
| `alembic.ini` | Main Alembic configuration |
| `alembic/env.py` | Migration environment setup |
| `alembic/script.py.mako` | Template for new migrations |
| `alembic/versions/` | Migration scripts directory |

### Database URL

The database URL is configured via environment variable:

```bash
export DATABASE_URL=sqlite:///data/tasks.db
# or for PostgreSQL:
export DATABASE_URL=postgresql://user:pass@localhost:5432/arbitrageai
```

If not set, it defaults to `sqlite:///data/tasks.db`.

## Migration Commands

### Using the Migration Script

The project provides a convenient wrapper script at `scripts/migrate.py`:

| Command | Description | Example |
|---------|-------------|---------|
| `upgrade` | Apply all pending migrations | `python scripts/migrate.py upgrade` |
| `downgrade [n]` | Rollback n migrations (default: 1) | `python scripts/migrate.py downgrade` |
| `downgrade 2` | Rollback 2 migrations | `python scripts/migrate.py downgrade 2` |
| `current` | Show current migration version | `python scripts/migrate.py current` |
| `history` | Show migration history | `python scripts/migrate.py history` |
| `generate` | Generate new migration (autogenerate) | `python scripts/migrate.py generate` |
| `heads` | Show current head revisions | `python scripts/migrate.py heads` |
| `branches` | Show branch information | `python scripts/migrate.py branches` |
| `stamp <revision>` | Stamp database as specific revision | `python scripts/migrate.py stamp head` |
| `check` | Check for ungenerated model changes | `python scripts/migrate.py check` |
| `merge <rev1> <rev2>` | Merge two revisions | `python scripts/migrate.py merge abc123 def456 "Merge heads"` |
| `help` | Show help message | `python scripts/migrate.py help` |

### Direct Alembic Commands

You can also use Alembic directly:

```bash
alembic upgrade head
alembic downgrade -1
alembic current
alembic history --verbose
alembic revision --autogenerate -m "Description"
```

## Creating New Migrations

### Workflow

1. **Modify Models**: Edit the model files in `src/api/`:
   - `src/api/task_models.py`
   - `src/api/user_models.py`
   - `src/api/marketplace_models.py`
   - `src/api/financial_models.py`

2. **Generate Migration**:
   ```bash
   python scripts/migrate.py generate
   ```

3. **Enter Description**: When prompted, enter a clear description:
   ```
   Migration description: Add new column to Task model
   ```

4. **Review Migration**: Check the generated file in `alembic/versions/`:
   ```python
   def upgrade() -> None:
       op.add_column('tasks', sa.Column('new_column', sa.String(), nullable=True))

   def downgrade() -> None:
       op.drop_column('tasks', 'new_column')
   ```

5. **Test Migration**:
   ```bash
   # Apply migration
   python scripts/migrate.py upgrade

   # Verify
   python scripts/migrate.py current

   # Test rollback
   python scripts/migrate.py downgrade

   # Re-apply
   python scripts/migrate.py upgrade
   ```

6. **Commit**: Add both the model changes and migration file to version control.

### Example: Adding a Column

```python
# In src/api/task_models.py
class Task(Base):
    # ... existing fields ...
    priority = Column(Integer, default=1, nullable=False)
```

Generate migration:
```bash
python scripts/migrate.py generate
# Enter: "Add priority column to Task model"
```

Review generated migration:
```python
"""Add priority column to Task model

Revision ID: abc123def45
Revises: 58948b63e4a7
Create Date: 2026-03-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision: str = "abc123def45"
down_revision: str | None = "58948b63e4a7"


def upgrade() -> None:
    op.add_column('tasks', sa.Column('priority', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('tasks', 'priority')
```

### Example: Adding an Index

```python
# In src/api/task_models.py
class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # ... existing indexes ...
        Index("idx_task_priority", "priority"),
    )
```

Generate migration:
```bash
python scripts/migrate.py generate
# Enter: "Add index on Task.priority"
```

### Example: Adding a Table

```python
# In src/api/financial_models.py
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True)
    action = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

Generate migration:
```bash
python scripts/migrate.py generate
# Enter: "Create audit_logs table"
```

## Migration Best Practices

### DO

1. **Test migrations** on a development database before production
2. **Review auto-generated migrations** before applying
3. **Keep migrations small** and focused on one change
4. **Test rollback** (downgrade) to ensure it works
5. **Use descriptive messages** for migrations
6. **Commit migrations** with the code changes they support
7. **Backup production databases** before applying migrations
8. **Use server_default** for new non-nullable columns on existing tables

### DON'T

1. **Never edit** applied migrations - create new ones instead
2. **Don't delete** migration files from version control
3. **Avoid data migrations** in the same file as schema changes
4. **Don't use** `DROP TABLE` without careful consideration
5. **Avoid** long-running migrations in production

## Production Deployment

### Pre-Deployment Checklist

- [ ] Backup the production database
- [ ] Test migrations on staging environment
- [ ] Review all migration scripts
- [ ] Ensure rollback procedures are documented
- [ ] Schedule deployment during low-traffic period

### Deployment Script

```bash
#!/bin/bash
# deploy_migrations.sh

echo "Starting database migration..."

# Backup database
echo "Creating database backup..."
cp data/tasks.db data/tasks.db.backup.$(date +%Y%m%d_%H%M%S)

# Apply migrations
echo "Applying migrations..."
python scripts/migrate.py upgrade

if [ $? -ne 0 ]; then
    echo "Migration failed! Check logs."
    exit 1
fi

# Verify migration
echo "Verifying migration..."
python scripts/migrate.py current

echo "Migration completed successfully!"
```

### CI/CD Integration

Add to your CI/CD pipeline:

```yaml
# Example GitHub Actions step
- name: Run Database Migrations
  run: |
    python scripts/migrate.py upgrade
  env:
    DATABASE_URL: ${{ secrets.PRODUCTION_DATABASE_URL }}
```

## Troubleshooting

### Migration Fails

**Error**: `Migration failed` or SQL errors

**Solutions**:
1. Check the error message for specific SQL issues
2. Ensure database is accessible
3. Verify no conflicting migrations exist
4. Check for syntax errors in the migration file

### Out of Sync Database

**Error**: `Target database is not up to date`

**Solutions**:
```bash
# Check current state
python scripts/migrate.py current

# Apply pending migrations
python scripts/migrate.py upgrade

# If needed, stamp to correct revision (use with caution)
python scripts/migrate.py stamp <revision>
```

### Multiple Heads

**Error**: `Multiple heads are present`

**Solutions**:
```bash
# Check heads
python scripts/migrate.py heads

# Merge the heads
python scripts/migrate.py merge <head1> <head2> "Merge heads"
```

### Autogenerate Not Detecting Changes

**Issue**: Migration generated but empty

**Solutions**:
1. Ensure models are imported correctly in `alembic/env.py`
2. Check that `target_metadata = Base.metadata` is set
3. Verify the database URL is correct
4. Try running with `--autogenerate` flag explicitly

### Rollback Fails

**Error**: `downgrade` fails

**Solutions**:
1. Review the downgrade function in the migration
2. Ensure all operations are reversible
3. Check for data dependencies
4. May need to manually fix the migration file

## Testing Migrations

### Manual Testing

```bash
# Create test database
export DATABASE_URL=sqlite:///data/test_tasks.db

# Apply all migrations
python scripts/migrate.py upgrade

# Verify tables created
sqlite3 data/test_tasks.db ".tables"

# Test downgrade
python scripts/migrate.py downgrade

# Verify tables removed
sqlite3 data/test_tasks.db ".tables"

# Re-apply
python scripts/migrate.py upgrade
```

### Automated Tests

Add migration tests to your test suite:

```python
# tests/test_migrations.py
import subprocess

def test_upgrade_downgrade_cycle():
    """Test that migrations can be upgraded and downgraded."""
    # Upgrade to head
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0

    # Downgrade to base
    result = subprocess.run(
        ["alembic", "downgrade", "base"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0

    # Upgrade again
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
```

## Current Migrations

### Migration History

| Revision | Description | Date |
|----------|-------------|------|
| `001_add_performance_indexes` | Add performance indexes for frequently queried fields | 2026-03-03 |
| `58948b63e4a7` | Initial schema from existing models | 2026-03-03 |

### Tables Managed by Migrations

- `tasks` - Core task management
- `task_executions` - Task execution state
- `task_planning` - Task planning and research
- `task_reviews` - Task review and feedback
- `task_arenas` - Arena competition results
- `task_outputs` - Task output results
- `scheduled_tasks` - Scheduled task definitions
- `schedule_history` - Schedule execution history
- `client_profiles` - Client preferences
- `user_quotas` - User quota configuration
- `quota_usage` - Monthly quota usage
- `rate_limit_logs` - Rate limit violations
- `bids` - Marketplace bids
- `arena_competitions` - Agent arena competitions
- `distributed_locks` - Distributed locking
- `simulation_bids` - Simulation bids for training
- `escalation_logs` - Human escalation logs
- `threshold_petitions` - Threshold adjustment petitions
- `cost_entries` - Cost tracking
- `confidence_entries` - Confidence tracking
- `confidence_adjustments` - Confidence adjustments
- `virtual_wallets` - Virtual wallet management
- `webhook_secrets` - Webhook secrets
- `learning_entries` - Learning system entries

## Developer Workflow

### Daily Development

```bash
# Start of day - ensure database is up to date
python scripts/migrate.py upgrade

# Make model changes
# Edit src/api/*.py files

# Generate migration
python scripts/migrate.py generate

# Test migration
python scripts/migrate.py upgrade
python scripts/migrate.py downgrade
python scripts/migrate.py upgrade

# Commit changes
git add src/api/ alembic/versions/
git commit -m "feat: add new feature with migration"
```

### Code Review Checklist

- [ ] Model changes are backward compatible
- [ ] Migration file is included in commit
- [ ] Migration has been tested (upgrade/downgrade)
- [ ] Migration message is descriptive
- [ ] No data loss in downgrade path

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://www.sqlalchemy.org/)
- [Migration Best Practices](https://alembic.sqlalchemy.org/en/latest/batch.html)
- [Issue QAQC-008](../../.github/ISSUES/QAQC-008-architecture-database-migrations.md)

## Support

For issues or questions about migrations:

1. Check this documentation first
2. Review the Alembic documentation
3. Check existing issues in the repository
4. Contact the development team

---

**Last Updated**: March 3, 2026
**Version**: 1.0
**Maintained By**: Development Team
