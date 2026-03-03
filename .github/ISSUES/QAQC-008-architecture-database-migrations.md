---
created: 2026-03-03
priority: HIGH
qaqc_section: 3.3
estimated_effort: 5 days
target_milestone: Phase 2 - Week 3-4
---

# [ARCHITECTURE] Implement Database Migration Framework (Alembic)

## 🏗️ Architecture Issue - Database Migrations

**Priority:** HIGH  
**Labels:** architecture, database, migrations, qaqc-review, tech-debt  
**QA/QC Review Reference:** Section 3.3 - Missing Database Migrations

---

## 📍 Location

- **Files to Create:**
  - `alembic.ini` - Alembic configuration
  - `migrations/` - Migration scripts directory
  - `migrations/env.py` - Migration environment
  - `migrations/script.py.mako` - Migration template
- **Component:** Database Layer
- **Environment:** All environments

---

## 🐛 Issue Description

The project currently has **no database migration framework**. Database schema changes are managed manually, which creates significant risks:

1. **Production Deployments:** No reliable way to update schemas
2. **Team Collaboration:** Developers may have different schemas
3. **Rollback:** Cannot easily revert schema changes
4. **Version Control:** Schema changes not tracked with code
5. **Testing:** Test databases may not match production

Current state:
```bash
# No migration framework detected
$ find . -name "alembic*" -o -name "migrations" | grep -v node_modules
./src/api/migrations/  # Only manual migration scripts
```

---

## ⚠️ Risk Assessment

- **Severity:** High (production deployment risk)
- **Impact:** Deployment failures, data loss potential
- **Likelihood:** High (will fail on first schema change)
- **Technical Debt:** Severe

---

## 🎯 Acceptance Criteria

- [ ] Alembic configured and working
- [ ] Initial migration created from current schema
- [ ] Migration commands documented
- [ ] CI/CD pipeline includes migration tests
- [ ] Rollback procedure tested
- [ ] Team trained on migration workflow

---

## 🔧 Implementation Notes

### Step 1: Install Alembic

```bash
pip install alembic
```

Add to `pyproject.toml`:
```toml
[project.optional-dependencies]
migrations = [
    "alembic>=1.13.0",
]
```

### Step 2: Initialize Alembic

```bash
# Initialize alembic in project root
alembic init alembic
```

### Step 3: Configure Alembic

**alembic.ini:**
```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

# Database URL (use environment variable)
sqlalchemy.url = driver://user:pass@localhost/dbname

[post_write_hooks]
hooks = black
black.type = console_scripts
black.entrypoint = black
black.options = -q

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

**alembic/env.py:**
```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.api.models import Base
from src.api.database import DATABASE_URL

# this is the Alembic Config object
config = context.config

# Use environment variable for database URL
config.set_main_option(
    "sqlalchemy.url",
    os.getenv("DATABASE_URL", DATABASE_URL)
)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model's MetaData object for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Step 4: Create Initial Migration

```bash
# Generate initial migration from current models
alembic revision --autogenerate -m "Initial schema from existing models"
```

Review the generated migration:
```python
# alembic/versions/001_initial_schema.py
"""Initial schema from existing models

Revision ID: abc123
Revises: 
Create Date: 2026-03-03

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'abc123'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic ###
    op.create_table('tasks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        # ... all columns
        sa.PrimaryKeyConstraint('id')
    )
    # ... all other tables
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic ###
    op.drop_table('tasks')
    # ... all other tables
    # ### end Alembic commands ###
```

### Step 5: Apply Migration

```bash
# Apply all pending migrations
alembic upgrade head
```

### Step 6: Create Migration Workflow Script

```python
# scripts/migrate.py
#!/usr/bin/env python3
"""Database migration management script."""

import subprocess
import sys
import os

def run_command(cmd):
    """Run alembic command."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
        sys.exit(1)
    print(result.stdout)

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/migrate.py <command>")
        print("\nCommands:")
        print("  upgrade     - Apply all pending migrations")
        print("  downgrade   - Rollback last migration")
        print("  current     - Show current migration version")
        print("  history     - Show migration history")
        print("  generate    - Generate new migration (autogenerate)")
        print("  stamp       - Stamp database with version")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "upgrade":
        print("🔄 Applying pending migrations...")
        run_command("alembic upgrade head")
        print("✅ Migrations applied successfully")
    
    elif command == "downgrade":
        print("⏪ Rolling back last migration...")
        run_command("alembic downgrade -1")
        print("✅ Rollback complete")
    
    elif command == "current":
        print("📊 Current migration version:")
        run_command("alembic current")
    
    elif command == "history":
        print("📜 Migration history:")
        run_command("alembic history --verbose")
    
    elif command == "generate":
        message = input("Migration description: ")
        print(f"📝 Generating migration: {message}")
        run_command(f'alembic revision --autogenerate -m "{message}"')
        print("✅ Migration generated")
    
    elif command == "stamp":
        version = input("Version to stamp: ")
        print(f"🏷️  Stamping database with version {version}")
        run_command(f"alembic stamp {version}")
        print("✅ Database stamped")
    
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## 📋 Testing Requirements

### Migration Tests:
```python
# tests/test_migrations.py

def test_upgrade_downgrade_cycle():
    """Test that migrations can be upgraded and downgraded."""
    import subprocess
    
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

def test_all_tables_created():
    """Test that all expected tables are created."""
    from sqlalchemy import inspect
    from src.api.database import engine
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    expected_tables = [
        'tasks', 'bids', 'client_profiles', 
        'arena_competitions', 'escalation_logs',
        # ... all other tables
    ]
    
    for table in expected_tables:
        assert table in tables
```

---

## 📚 References

- **QA/QC Review:** Deep QA/QC Review - March 2026, Section 3.3
- **Alembic Documentation:** https://alembic.sqlalchemy.org/
- **SQLAlchemy:** https://www.sqlalchemy.org/
- **Related Issues:** QAQC-010 (Database indexes)

---

## 🎯 Success Metrics

- [ ] Alembic configured and working
- [ ] Initial migration created and tested
- [ ] Team can create new migrations independently
- [ ] CI/CD runs migrations on test database
- [ ] Zero manual schema changes in production

---

## 📝 Additional Notes

### Developer Workflow:

```bash
# When models change:
1. Edit src/api/models.py
2. Run: python scripts/migrate.py generate
3. Review generated migration
4. Commit migration with code changes
5. On deploy: python scripts/migrate.py upgrade
```

### Production Deployment:

```bash
# In deployment script:
echo "Running database migrations..."
python scripts/migrate.py upgrade
if [ $? -ne 0 ]; then
    echo "Migration failed!"
    exit 1
fi
echo "Migrations complete, starting application..."
```

---

**Created from:** Deep QA/QC Review - March 3, 2026  
**Issue Template:** qaqc-architecture.md
