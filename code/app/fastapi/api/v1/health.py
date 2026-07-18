from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.database import SessionLocal

router = APIRouter(tags=["health"])


@router.get("/")
def root() -> dict:
    return {
        "name": "PriceMonitor API",
        "description": "Price tracking for Amazon India and Flipkart. Get notified when prices drop.",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
    
@router.get("/health")
def health_check(response: Response) -> dict:
    """
    Lightweight health probe for Railway uptime monitoring.
    Checks database connectivity with SELECT 1.
    Returns 200 if healthy, 503 if database unreachable.
    """
    db_status = "ok"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "unreachable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "version": "1.0.0",
    }