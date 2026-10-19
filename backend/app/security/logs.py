"""Structured (JSON-lines) logging with redaction, and generic error responses.

Every record leaving the process goes through `RedactingFilter`, which scrubs the
message, the `extra` fields and any traceback text (see redaction.py). Uvicorn's own
access log is replaced by `log_requests`, which records the path without its query
string: the OAuth callback carries the authorization code there.

Error bodies are generic: request validation errors keep where and why a field failed
but never echo the submitted value, and unexpected exceptions become a plain 500.
"""
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.security.redaction import redact, redact_text

log = logging.getLogger("medvault.http")

# Attributes every LogRecord has; anything else came from `extra=`.
_STANDARD = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "taskName"}


def _extras(record: logging.LogRecord) -> dict:
    return {k: v for k, v in vars(record).items() if k not in _STANDARD}


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = None
        for key, value in redact(_extras(record)).items():
            setattr(record, key, value)
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact_text(record.exc_text)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **_extras(record),
        }
        if record.exc_text:
            payload["exc"] = record.exc_text
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers = []
    access.propagate = False
    access.disabled = True


async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"loc": list(e.get("loc", ())), "msg": redact_text(str(e.get("msg", ""))), "type": e.get("type")}
        for e in exc.errors()
    ]
    return JSONResponse({"detail": errors}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    log.error(
        "unhandled error",
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={"method": request.method, "path": request.url.path},
    )
    return JSONResponse(
        {"detail": "Something went wrong. Please try again."},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def install(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled_error)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        log.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response
