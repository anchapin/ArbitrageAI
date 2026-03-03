#!/usr/bin/env python3
"""
Database Migration Management Script

This script provides a convenient interface for managing database migrations
using Alembic. It wraps common Alembic commands with helpful output and
error handling.

Usage:
    python scripts/migrate.py <command>

Commands:
    upgrade     - Apply all pending migrations
    downgrade   - Rollback last migration
    current     - Show current migration version
    history     - Show migration history
    generate    - Generate new migration (autogenerate from models)
    heads       - Show current head revisions
    branches    - Show branch information
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd: str, description: str) -> bool:
    """Run a shell command and return success status."""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}\n")

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)

    if result.returncode != 0:
        print(f"\n❌ Error: {result.stderr}")
        return False

    return True


def main():
    """Main entry point for migration management."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    success = True

    if command == "upgrade":
        print("\n🚀 Applying pending migrations...")
        success = run_command(
            "alembic upgrade head",
            "Applying all pending migrations"
        )
        if success:
            print("\n✅ Migrations applied successfully!")

    elif command == "downgrade":
        steps = sys.argv[2] if len(sys.argv) > 2 else "1"
        print(f"\n⏪ Rolling back {steps} migration(s)...")
        success = run_command(
            f"alembic downgrade -{steps}",
            f"Rolling back {steps} migration(s)"
        )
        if success:
            print(f"\n✅ Rollback complete!")

    elif command == "current":
        print("\n📊 Current migration version:")
        success = run_command(
            "alembic current",
            "Checking current migration version"
        )

    elif command == "history":
        print("\n📜 Migration history:")
        success = run_command(
            "alembic history --verbose",
            "Loading migration history"
        )

    elif command == "generate":
        message = input("\n📝 Migration description: ")
        print(f"\n✨ Generating migration: {message}")
        success = run_command(
            f'alembic revision --autogenerate -m "{message}"',
            "Generating new migration"
        )
        if success:
            print("\n✅ Migration generated! Please review the generated file.")

    elif command == "heads":
        print("\n🎯 Current head revisions:")
        success = run_command(
            "alembic heads",
            "Checking head revisions"
        )

    elif command == "branches":
        print("\n🌿 Branch information:")
        success = run_command(
            "alembic branches",
            "Loading branch information"
        )

    elif command == "stamp":
        if len(sys.argv) < 3:
            print("\n❌ Usage: python scripts/migrate.py stamp <revision>")
            print("Example: python scripts/migrate.py stamp head")
            sys.exit(1)

        revision = sys.argv[2]
        print(f"\n🏷️  Stamping database as revision: {revision}")
        success = run_command(
            f"alembic stamp {revision}",
            f"Stamping database as {revision}"
        )

    elif command == "check":
        print("\n🔍 Checking for ungenerated migrations...")
        success = run_command(
            "alembic check",
            "Checking for ungenerated migrations"
        )

    elif command == "merge":
        if len(sys.argv) < 3:
            print("\n❌ Usage: python scripts/migrate.py merge <rev1> <rev2> [message]")
            sys.exit(1)

        rev1 = sys.argv[2]
        rev2 = sys.argv[3]
        message = sys.argv[4] if len(sys.argv) > 4 else "Merge migrations"

        print(f"\n🔀 Merging revisions {rev1} and {rev2}")
        success = run_command(
            f'alembic merge -m "{message}" {rev1} {rev2}',
            "Merging revisions"
        )

    elif command == "help":
        print(__doc__)

    else:
        print(f"\n❌ Unknown command: {command}")
        print("\nAvailable commands: upgrade, downgrade, current, history, generate, heads, branches, stamp, check, merge, help")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
