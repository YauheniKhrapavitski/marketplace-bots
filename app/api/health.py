from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.config import get_settings
from app.db.session import SessionFactory
from app.workers.scheduler import scheduler_state

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    database = "ok"
    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        database = "error"
    return {
        "status": "ok" if database == "ok" else "degraded",
        "database": database,
        "telegram": "configured" if get_settings().telegram_configured else "missing",
        "scheduler": "running" if scheduler_state.running else "stopped",
    }


@router.get("/ready")
async def ready(response: Response) -> dict[str, str]:
    settings = get_settings()
    database = "ok"
    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        database = "error"
    configured = settings.required_configured
    if database != "ok" or not configured:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if database == "ok" and configured else "not_ready",
        "database": database,
        "configuration": "ok" if configured else "missing",
    }
