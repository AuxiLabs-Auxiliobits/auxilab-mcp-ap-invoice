from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError


@dataclass(slots=True)
class AppError(Exception):
    error_code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    step: str | None = None

    def __str__(self) -> str:
        return self.message


def app_error(
    error_code: str,
    message: str,
    *,
    step: str | None = None,
    details: dict[str, Any] | None = None,
) -> AppError:
    return AppError(
        error_code=error_code,
        message=message,
        step=step,
        details=details or {},
    )


def map_exception_to_error(exc: Exception, *, step: str | None = None) -> AppError:
    if isinstance(exc, AppError):
        if step and exc.step is None:
            exc.step = step
        return exc

    if isinstance(exc, FileNotFoundError):
        return app_error(
            "FILE_NOT_FOUND",
            str(exc),
            step=step,
        )

    if isinstance(exc, ValidationError):
        return app_error(
            "VALIDATION_ERROR",
            "Validation failed.",
            step=step,
            details={"errors": exc.errors()},
        )

    if isinstance(exc, SQLAlchemyError):
        return app_error(
            "DATABASE_ERROR",
            "Database operation failed.",
            step=step,
            details={"exception_type": exc.__class__.__name__},
        )

    if isinstance(exc, ValueError):
        return app_error(
            "INVALID_INPUT",
            str(exc),
            step=step,
        )

    return app_error(
        "UNKNOWN_ERROR",
        str(exc),
        step=step,
        details={"exception_type": exc.__class__.__name__},
    )

