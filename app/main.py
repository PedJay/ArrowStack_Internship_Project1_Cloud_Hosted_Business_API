"""BrightMart Inventory & Orders API (simulated business).

Run locally:  uvicorn app.main:app --reload
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db import init_db
from app.logging_config import configure_logging
from app.routers import health, orders, products

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db()
    log.info("startup complete", extra={"extra_fields": {"env": settings.environment}})
    yield


app = FastAPI(
    title="BrightMart Inventory & Orders API",
    version="1.0.0",
    description="Simulated retail business API deployed on AWS (EC2 + Docker + RDS PostgreSQL).",
    lifespan=lifespan,
)
app.include_router(health.router)
app.include_router(products.router)
app.include_router(orders.router)


@app.middleware("http")
async def access_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error", extra={"extra_fields": {"request_id": request_id, "path": request.url.path}})
        response = JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": request_id})
    response.headers["x-request-id"] = request_id
    log.info(
        "request",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            }
        },
    )
    return response


@app.exception_handler(IntegrityError)
async def integrity_error(_request: Request, _exc: IntegrityError) -> JSONResponse:
    # e.g. deleting a product that existing orders reference
    return JSONResponse(status_code=409, content={"detail": "Operation conflicts with existing data"})
