#!/usr/bin/env python3
"""
Database migration management script for the blockchain financial platform.

This script provides simple commands to manage database migrations using Alembic.
"""

import sys
import subprocess
import os
from pathlib import Path

def run_command(command, description):
    """Run a shell command and handle errors."""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        print(f"✅ {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed!")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False

def activate_venv():
    """Activate virtual environment if it exists."""
    venv_path = Path("venv/bin/activate")
    if venv_path.exists():
        return "source venv/bin/activate && "
    return ""

def main():
    """Main migration management function."""
    if len(sys.argv) < 2:
        print("""
🗄️  Database Migration Manager

Usage: python migrate.py <command>

Available commands:
  init        - Initialize the database with all tables
  create      - Create a new migration (auto-generate from model changes)
  upgrade     - Apply all pending migrations to the database
  downgrade   - Rollback the last migration
  current     - Show current migration version
  history     - Show migration history
  status      - Show current database status

Examples:
  python migrate.py init                    # First time setup
  python migrate.py create "add user table" # Create new migration
  python migrate.py upgrade                 # Apply migrations
  python migrate.py current                 # Check current version
        """)
        return

    command = sys.argv[1].lower()
    venv_prefix = activate_venv()

    if command == "init":
        print("🚀 Initializing database with all tables...")
        if run_command(f"{venv_prefix}alembic upgrade head", "Database initialization"):
            print("\n✅ Database is ready! All tables have been created.")
        else:
            print("\n❌ Database initialization failed. Check your database connection.")

    elif command == "create":
        if len(sys.argv) < 3:
            print("❌ Please provide a migration message.")
            print("Example: python migrate.py create 'add user email field'")
            return
        
        message = sys.argv[2]
        run_command(
            f"{venv_prefix}alembic revision --autogenerate -m \"{message}\"",
            f"Creating migration: {message}"
        )

    elif command == "upgrade":
        run_command(f"{venv_prefix}alembic upgrade head", "Applying migrations")

    elif command == "downgrade":
        print("⚠️  This will rollback the last migration. Are you sure? (y/N)")
        if input().lower() == 'y':
            run_command(f"{venv_prefix}alembic downgrade -1", "Rolling back last migration")
        else:
            print("Migration rollback cancelled.")

    elif command == "current":
        run_command(f"{venv_prefix}alembic current", "Checking current migration version")

    elif command == "history":
        run_command(f"{venv_prefix}alembic history", "Showing migration history")

    elif command == "status":
        print("📊 Database Status:")
        run_command(f"{venv_prefix}alembic current", "Current version")
        run_command(f"{venv_prefix}alembic heads", "Latest available version")

    else:
        print(f"❌ Unknown command: {command}")
        print("Run 'python migrate.py' to see available commands.")

if __name__ == "__main__":
    main()