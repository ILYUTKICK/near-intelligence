"""Install common schemas and sanitized error handling without network/config I/O."""

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic.json_schema import models_json_schema
from starlette.exceptions import HTTPException

from near_api.db.security import ResourceNotFound
from near_api.insights.schemas import INSIGHT_CONTRACT_MODELS
from near_api.schemas.common import ApiError, CONTRACT_MODELS, ErrorDetail, ErrorResponse
from near_api.schemas.integrity import INTEGRITY_CONTRACT_MODELS

_HTTP_ERRORS = {
    400: ("BAD_REQUEST", "Invalid request"),
    401: ("AUTHENTICATION_REQUIRED", "Authentication is required"),
    403: ("FORBIDDEN", "Operation is not permitted"),
    404: ("NOT_FOUND", "Resource was not found"),
    409: ("CONFLICT", "Request conflicts with the current state"),
    410: ("EXPIRED", "Resource has expired"),
    413: ("PAYLOAD_TOO_LARGE", "Request is too large"),
    422: ("VALIDATION_ERROR", "Request failed validation"),
    428: ("PRECONDITION_REQUIRED", "A request precondition is required"),
    429: ("RATE_LIMITED", "Request limit reached"),
    500: ("INTERNAL_ERROR", "An internal error occurred"),
    503: ("DEPENDENCY_UNAVAILABLE", "A required service is unavailable"),
}


def error_response(request: Request, status: int, code: str, message: str,
                   *, details: tuple[ErrorDetail, ...] | None = None) -> JSONResponse:
    body = ErrorResponse(error=ApiError(
        code=code, message=message, request_id=getattr(request.state, "request_id", uuid4()),
        details=details, retryable=status in {429, 503},
    ))
    return JSONResponse(status_code=status, content=body.model_dump(mode="json", exclude_none=True),
                        headers={"Cache-Control": "no-store", "X-Request-ID": str(body.error.request_id)})


def install_contracts(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_identity(request: Request, call_next):
        request.state.request_id = uuid4()
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(request.state.request_id)
        if request.url.path == "/api/saved-charts" or request.url.path.startswith("/api/saved-charts/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        errors = error.errors()
        malformed = any(item["type"] == "json_invalid" for item in errors)
        # Never serialize Pydantic msg/input/ctx or arbitrary user-supplied keys.
        # Coarse locations remain safe even for unknown nested object fields.
        details = []
        for item in errors[:20]:
            section = item.get("loc", ("request",))[0]
            path = section if section in {"body", "query", "path", "header"} else "request"
            reason = {"missing": "required", "extra_forbidden": "unknown_field",
                      "json_invalid": "malformed_json"}.get(item["type"], "invalid_value")
            detail = ErrorDetail(path=path, reason=reason)
            if detail not in details:
                details.append(detail)
        return error_response(request, 400 if malformed else 422,
                              "BAD_REQUEST" if malformed else "VALIDATION_ERROR",
                              "Malformed JSON" if malformed else "Request failed validation",
                              details=tuple(details))

    @app.exception_handler(ResourceNotFound)
    async def not_owned_or_missing(request: Request, error: ResourceNotFound):
        # Absent and not-owned resources share one generic response (NI-019
        # ResourceNotFound semantics): no exception detail, no existence leak.
        return error_response(request, 404, *_HTTP_ERRORS[404])

    @app.exception_handler(HTTPException)
    async def http_failure(request: Request, error: HTTPException):
        code, message = _HTTP_ERRORS.get(error.status_code, ("HTTP_ERROR", "Request failed"))
        response = error_response(request, error.status_code, code, message)
        # Preserve only bounded numeric Retry-After, never arbitrary exception headers.
        retry = (error.headers or {}).get("Retry-After", "")
        if error.status_code in {429, 503} and retry.isascii() and retry.isdigit() and len(retry) <= 6:
            response.headers["Retry-After"] = retry
        if error.status_code == 401:
            response.headers["WWW-Authenticate"] = "Bearer"
        allowed = (error.headers or {}).get("Allow", "")
        if error.status_code == 405 and allowed and set(allowed.replace(" ", "").split(",")) <= {
            "GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT",
        }:
            response.headers["Allow"] = allowed
        return response

    @app.exception_handler(Exception)
    async def unexpected_failure(request: Request, error: Exception):
        return error_response(request, 500, "INTERNAL_ERROR", "An internal error occurred")

    def openapi():
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes,
                                 openapi_version=app.openapi_version)
            # Keep reusable annotation models visible before their routes ship.
            # Route responses such as Insight come directly from FastAPI.
            _, common = models_json_schema(
                [(model, "validation")
                 for model in (*CONTRACT_MODELS, *INSIGHT_CONTRACT_MODELS,
                               *INTEGRITY_CONTRACT_MODELS)],
                ref_template="#/components/schemas/{model}")
            common = jsonable_encoder(common, exclude_none=True)
            definitions = schema.setdefault("components", {}).setdefault("schemas", {})
            for name, definition in common.get("$defs", {}).items():
                if name in definitions and definitions[name] != definition:
                    raise RuntimeError(f"Conflicting OpenAPI schema: {name}")
                definitions[name] = definition
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi
