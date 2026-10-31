from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def liveness() -> dict:
    """Process is up. Used by the EC2/Docker health check; never touches the DB."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)) -> JSONResponse:
    """Process can serve traffic: database reachable."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - any DB failure means "not ready"
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "unreachable"})
    return JSONResponse(content={"status": "ok", "database": "reachable"})
