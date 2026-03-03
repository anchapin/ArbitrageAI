# Database Migrations with Alembic

This directory contains database migration scripts using Alembic.

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

## Creating New Migrations

After making changes to `src/api/models.py`, generate a new migration:

```bash
python scripts/migrate.py generate
```

Enter a description when prompted, e.g., "Add indexes to Bid model"

This will:
1. Auto-generate a migration file in `alembic/versions/`
2. Run ruff to fix linting issues
3. Create upgrade/downgrade functions

## Manual Migration Creation

If autogenerate doesn't work as expected, you can create migrations manually:

```bash
alembic revision -m "Description of changes"
```

Then edit the generated file in `alembic/versions/`.

## Migration Commands Reference

| Command | Description |
|---------|-------------|
| `upgrade` | Apply all pending migrations |
| `downgrade [n]` | Rollback n migrations (default: 1) |
| `current` | Show current migration version |
| `history` | Show migration history |
| `generate` | Generate new migration (autogenerate) |
| `heads` | Show current head revisions |
| `branches` | Show branch information |
| `stamp <revision>` | Stamp database as specific revision |
| `check` | Check for ungenerated migrations |
| `merge <rev1> <rev2>` | Merge two revisions |

## Best Practices

1. **Always test migrations** on a development database before production
2. **Review auto-generated migrations** before applying
3. **Add data migrations** carefully - they can't be easily rolled back
4. **Keep migrations small** and focused on one change
5. **Test rollback** (downgrade) to ensure it works
6. **Never edit** applied migrations - create new ones instead

## Troubleshooting

### Migration Fails
Check the error message and ensure:
- Database is accessible
- No conflicting migrations
- SQL syntax is correct

### Out of Sync
If database is out of sync:
```bash
# Check current state
python scripts/migrate.py current

# If needed, stamp to correct revision
python scripts/migrate.py stamp <revision>
```

### Conflicting Heads
If you see "multiple heads":
```bash
# Merge the heads
python scripts/migrate.py merge <head1> <head2> "Merge heads"
```

## Production Deployment

In production, migrations should be applied as part of the deployment process:

```bash
# 1. Backup database first!
# 2. Apply migrations
python scripts/migrate.py upgrade

# 3. Verify
python scripts/migrate.py current
```

## Configuration

- `alembic.ini` - Main configuration file
- `alembic/env.py` - Migration environment
- `alembic/script.py.mako` - Template for new migrations
- `alembic/versions/` - Migration scripts

## Adding Indexes (Example)

When adding indexes to models in `src/api/models.py`:

```python
# In your model class
__table_args__ = (
    Index("idx_column_name", "column_name"),
    # ... other args
)
```

Then generate migration:
```bash
python scripts/migrate.py generate
```

Enter: "Add index on column_name"

The migration will be auto-generated with the index creation.
