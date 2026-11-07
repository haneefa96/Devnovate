"""
Munshi - FastAPI application entry point
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from munshi.api import (
    actions,
    customers,
    dashboard,
    evaluation,
    explain,
    invoices,
    messages,
    payments,
    risk,
    simulation,
)
from munshi.config import clock, settings
from munshi.db.session import init_db

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("munshi")


class AppError(Exception):
    """Domain exception with documented error code and HTTP status code."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


STATUS_CODE_TO_ERROR_CODE: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "SIM_DISABLED",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL",
    status.HTTP_503_SERVICE_UNAVAILABLE: "MEMORY_UNAVAILABLE",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting Munshi %s (env=%s)", settings.APP_VERSION, settings.APP_ENV)
    init_db()
    logger.info("Database tables initialized successfully")
    from munshi.memory.client import get_hindsight_client
    from munshi.memory.outbox import outbox_processor

    outbox_task = asyncio.create_task(outbox_processor.start())
    try:
        yield
    finally:
        await outbox_processor.stop()
        outbox_task.cancel()
        try:
            await outbox_task
        except asyncio.CancelledError:
            pass
        await get_hindsight_client().aclose()
        logger.info("Munshi shutting down")


app = FastAPI(
    title="Munshi API",
    description="AI collections agent for small Indian B2B suppliers",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "AppError on %s %s: [%s] %s",
        request.method,
        request.url.path,
        exc.code,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": exc.code, "message": exc.message, "details": exc.details}
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = STATUS_CODE_TO_ERROR_CODE.get(exc.status_code, "HTTP_ERROR")
    message = str(exc.detail) if exc.detail else "An error occurred"
    logger.warning(
        "HTTPException %d on %s %s: [%s] %s",
        exc.status_code,
        request.method,
        request.url.path,
        code,
        message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message, "details": {}}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    message = f"Validation failed: {errors[0].get('msg', 'invalid field')}" if errors else "Validation error"
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, message)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": message,
                "details": {"errors": jsonable_encoder(errors)},
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception for %s %s", request.method, request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL",
                "message": "Internal server error",
                "details": {},
            },
        },
    )

_PREFIX = "/api"
app.include_router(dashboard.router,   prefix=_PREFIX)
app.include_router(customers.router,   prefix=_PREFIX)
app.include_router(invoices.router,    prefix=_PREFIX)
app.include_router(actions.router,     prefix=_PREFIX)
app.include_router(messages.router,    prefix=_PREFIX)
app.include_router(payments.router,    prefix=_PREFIX)
app.include_router(risk.router,        prefix=_PREFIX)
app.include_router(simulation.router,  prefix=_PREFIX)
app.include_router(evaluation.router,  prefix=_PREFIX)
app.include_router(explain.router,     prefix=_PREFIX)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "healthy", "timestamp": clock.now().isoformat()}
