from __future__ import annotations

from typing import Any

from app.core.errors import AppError, map_exception_to_error


def success_response(
    *,
    step: str,
    data: Any = None,
    **extra: Any,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "ok": True,
        "status": "success",
        "step": step,
    }

    if data is not None:
        response["data"] = data

    response.update(extra)
    return response


def error_response(
    *,
    step: str,
    error: Exception | str,
    **extra: Any,
) -> dict[str, Any]:
    mapped_error = (
        map_exception_to_error(error, step=step)
        if isinstance(error, Exception)
        else AppError(
            error_code="UNKNOWN_ERROR",
            message=str(error),
            details={},
            step=step,
        )
    )

    response: dict[str, Any] = {
        "ok": False,
        "status": "error",
        "step": step,
        "error_code": mapped_error.error_code,
        "message": mapped_error.message,
        "details": mapped_error.details,
    }

    response.update(extra)
    return response


def step_result(
    *,
    step: str,
    status: str,
    message: str | None = None,
    data: Any = None,
    error: Exception | None = None,
    **extra: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "step": step,
        "status": status,
    }

    if message is not None:
        result["message"] = message

    if data is not None:
        result["data"] = data

    if error is not None:
        mapped_error = map_exception_to_error(error, step=step)
        result["error_code"] = mapped_error.error_code
        result["error_message"] = mapped_error.message
        result["error_details"] = mapped_error.details

    result.update(extra)
    return result
