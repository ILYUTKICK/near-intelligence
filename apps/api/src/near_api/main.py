"""FastAPI application factory (NI-002 runtime skeleton).

Boot starts only the HTTP service. No collector, ingestion job, scheduler or
model runs from this module; data boundaries are enforced by later tasks.
"""

from datetime import datetime, timezone

from fastapi import FastAPI, Request

from near_api import __version__
from near_api.contracts import error_response, install_contracts
from near_api.schemas.common import ErrorResponse, HealthResponse
from near_api.settings import SettingsError, get_settings
from near_api.workspace.routes import router as workspace_router

app = FastAPI(
    title="NEAR Intelligence API",
    version=__version__,
    # Public catalog/data endpoints arrive in their own tasks (NI-032, NI-054).
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)
install_contracts(app)

# Private workspace routes (NI-022): authenticate via get_principal and emit
# no-store on every response. Route modules open no connection at import time.
app.include_router(workspace_router)


@app.get("/health", response_model=HealthResponse, operation_id="getHealth",
         responses={503: {"model": ErrorResponse, "description": "Invalid server configuration"}})
def health(request: Request):
    """Process liveness mirroring the web service /health JSON shape."""
    try:
        settings = get_settings()
    except SettingsError as error:
        return error_response(request, 503, "CONFIGURATION_ERROR", str(error))
    return HealthResponse(status="ok", service="api", appEnv=settings.APP_ENV,
                          checkedAt=datetime.now(timezone.utc))
