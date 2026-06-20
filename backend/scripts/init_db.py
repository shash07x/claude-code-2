"""Create all database tables (dev bootstrap without Alembic).

Usage (from the backend/ directory):
    python -m scripts.init_db
"""
import asyncio

from app.core.database import create_all


async def main() -> None:
    await create_all()
    print("Database tables created.")


if __name__ == "__main__":
    asyncio.run(main())
