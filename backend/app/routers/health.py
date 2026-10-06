"""Health check endpoints."""

from fastapi import APIRouter
from sqlalchemy import text

from app.database import async_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Basic liveness check — no dependencies required."""
    return {"status": "healthy", "service": "karthik-ai-backend"}


@router.get("/health/db")
async def db_health_check():
    """Database connectivity check — requires PostgreSQL to be running."""
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}
