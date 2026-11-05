"""FastAPI application factory (NI-002 runtime skeleton).

Boot starts only the HTTP service. No collector, ingestion job, scheduler or
model runs from this module; data boundaries are enforced by later tasks.
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from near_api import __version__
from near_api.settings import SettingsError, get_settings

app = FastAPI(
    title="NEAR Intelligence API",
    version=__version__,
    # Public catalog/data endpoints arrive in their own tasks (NI-032, NI-054).
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
def health() -> JSONResponse:
    """Process liveness mirroring the web service /health JSON shape."""
    try:
        settings = get_settings()
    except SettingsError as error:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "error": str(error)},
        )
    return JSONResponse(
        content={
            "status": "ok",
            "service": "api",
            "appEnv": settings.APP_ENV,
            "checkedAt": datetime.now(timezone.utc).isoformat(),
        }
    )
