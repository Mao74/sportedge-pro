"""RFC 9457 problem-details: exception type + handlers.

Every 4xx/5xx the API emits is an ``application/problem+json`` body with
the canonical fields ``type``, ``title``, ``status``, ``detail``, ``instance``
plus arbitrary extra members. Pydantic ``ValidationError`` is mapped to a
422 with a structured ``errors`` extension.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

PROBLEM_JSON = "application/problem+json"


class ProblemDetailException(Exception):
    """Raise this anywhere in the API to produce a problem-details response."""

    def __init__(
        self,
        *,
        status: int,
        title: str,
        detail: str | None = None,
        type_uri: str = "about:blank",
        extras: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.title = title
        self.detail = detail
        self.type_uri = type_uri
        self.extras = extras or {}

    def to_dict(self, instance: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": self.type_uri,
            "title": self.title,
            "status": self.status,
        }
        if self.detail is not None:
            body["detail"] = self.detail
        if instance is not None:
            body["instance"] = instance
        body.update(self.extras)
        return body


# --- Convenience constructors ----------------------------------------------


def bad_request(detail: str, **extras: Any) -> ProblemDetailException:
    return ProblemDetailException(
        status=status.HTTP_400_BAD_REQUEST, title="Bad Request",
        detail=detail, extras=extras,
    )


def unauthorized(detail: str = "Authentication required.", **extras: Any) -> ProblemDetailException:
    return ProblemDetailException(
        status=status.HTTP_401_UNAUTHORIZED, title="Unauthorized",
        detail=detail, extras=extras,
    )


def forbidden(detail: str, **extras: Any) -> ProblemDetailException:
    return ProblemDetailException(
        status=status.HTTP_403_FORBIDDEN, title="Forbidden",
        detail=detail, extras=extras,
    )


def not_found(detail: str, **extras: Any) -> ProblemDetailException:
    return ProblemDetailException(
        status=status.HTTP_404_NOT_FOUND, title="Not Found",
        detail=detail, extras=extras,
    )


def conflict(detail: str, **extras: Any) -> ProblemDetailException:
    return ProblemDetailException(
        status=status.HTTP_409_CONFLICT, title="Conflict",
        detail=detail, extras=extras,
    )


def unprocessable(detail: str, **extras: Any) -> ProblemDetailException:
    return ProblemDetailException(
        status=status.HTTP_422_UNPROCESSABLE_ENTITY, title="Unprocessable Entity",
        detail=detail, extras=extras,
    )


# --- Handlers ---------------------------------------------------------------


def _problem_response(exc: ProblemDetailException, instance: str) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content=exc.to_dict(instance=instance),
        media_type=PROBLEM_JSON,
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemDetailException)
    async def _handle_problem(request: Request, exc: ProblemDetailException) -> JSONResponse:
        return _problem_response(exc, str(request.url.path))

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # jsonable_encoder converts Pydantic context objects (e.g. nested
        # ValueError instances) into JSON-safe representations.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "type": "about:blank",
                "title": "Unprocessable Entity",
                "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "detail": "Request validation failed.",
                "instance": str(request.url.path),
                "errors": jsonable_encoder(exc.errors()),
            },
            media_type=PROBLEM_JSON,
        )

    @app.exception_handler(ValidationError)
    async def _handle_pydantic(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "type": "about:blank",
                "title": "Unprocessable Entity",
                "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "detail": "Validation failed.",
                "instance": str(request.url.path),
                "errors": jsonable_encoder(exc.errors()),
            },
            media_type=PROBLEM_JSON,
        )
