"""
AI Office IT Help Desk — Database Initialization & Migration Script
Connects to PostgreSQL, applies Alembic migrations, and seeds foundational data.
"""

import asyncio
import os
import sys
import subprocess
from sqlalchemy import text

# Reconfigure stdout for UTF-8 compatibility
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix Windows event loop if running on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.db.session import engine, AsyncSessionLocal
from app.db.seed import seed_initial_data


async def wait_for_db(max_retries: int = 10, delay_seconds: int = 2):
    """Waits until PostgreSQL responds to queries."""
    print("[*] Checking PostgreSQL database connection...")
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print("    [OK] Database connection successful.")
            return True
        except Exception as exc:
            print(f"    [WAIT] Attempt {attempt}/{max_retries} failed: {exc}. Retrying in {delay_seconds}s...")
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("Could not connect to PostgreSQL after multiple retries.")


def run_migrations():
    """Runs Alembic migrations to bring database schema to head."""
    print("[*] Applying Alembic database migrations...")
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
    result = subprocess.run(cmd, cwd=backend_dir, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    [ERROR] Alembic migration failed:\n{result.stderr}")
        raise RuntimeError("Migration error")
    print(f"    [OK] Alembic migrations applied successfully.")


async def main():
    print("=" * 70)
    print("  AI OFFICE IT HELP DESK — DATABASE INITIALIZATION")
    print("=" * 70)

    # 1. Wait for database
    await wait_for_db()

    # 2. Run migrations
    run_migrations()

    # 3. Seed initial data
    print("[*] Seeding foundational data (Teams, Categories, SLAs)...")
    await seed_initial_data()
    print("    [OK] Seed data verification complete.")

    print("\n[SUCCESS] Database initialization completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
