"""FastAPI application factory (NI-002 runtime skeleton).

Boot starts only the HTTP service. No collector, ingestion job, scheduler or
model runs from this module; data boundaries are enforced by later tasks.
"""

from datetime import datetime, timezone

from fastapi import FastAPI, Request

from near_api import __version__
from near_api.ai.routes import router as ai_router
from near_api.charts.routes import router as charts_router
from near_api.charts.saved_routes import router as saved_charts_router
from near_api.charts.snapshot_routes import router as snapshots_router
from near_api.contracts import error_response, install_contracts
from near_api.datasets.delivery import DeliveryError, delivery_error_shape
from near_api.datasets.routes import router as datasets_router
from near_api.documents.chart_blocks import router as chart_blocks_router
from near_api.documents.model_blocks import router as model_blocks_router
from near_api.documents.routes import router as documents_router
from near_api.evidence.link_routes import router as evidence_router
from near_api.evidence.routes import router as hypotheses_router
from near_api.exports.routes import router as exports_router
from near_api.insights.routes import router as insights_router
from near_api.integrity.routes import router as integrity_router
from near_api.metrics.routes import router as metrics_router
from near_api.models.routes import router as models_router
from near_api.publications.routes import router as publications_router
from near_api.schemas.common import ErrorResponse, HealthResponse
from near_api.settings import SettingsError, get_settings
from near_api.shares.routes import router as shares_router
from near_api.users.routes import router as me_router
from near_api.workspace.routes import router as workspace_router

app = FastAPI(
    title="NEAR Intelligence API",
    version=__version__,
    # Public model endpoints (NI-054) and public publication reads (NI-045)
    # serve published operator-seeded rows only.
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)
install_contracts(app)


@app.exception_handler(DeliveryError)
async def delivery_failure(request: Request, error: DeliveryError):
    """Map public delivery failures (NI-032) onto the shared error envelope.

    Not-found outcomes stay generic (no existence leak for non-approved
    versions); not-ready outcomes are typed and retryable.
    """
    status, code, message = delivery_error_shape(error)
    return error_response(request, status, code, message)


# Private workspace routes (NI-022) and document revision routes (NI-036):
# authenticate via get_principal and emit no-store on every response. Public
# delivery routes (NI-032) read the scientific zone through the unprivileged
# near_app role without any identity. Route modules open no connection at
# import time.
app.include_router(workspace_router)
app.include_router(documents_router)
app.include_router(chart_blocks_router)
app.include_router(model_blocks_router)
app.include_router(exports_router)
app.include_router(shares_router)
app.include_router(insights_router)
app.include_router(hypotheses_router)
app.include_router(evidence_router)
app.include_router(integrity_router)
app.include_router(ai_router)
app.include_router(me_router)
app.include_router(metrics_router)
app.include_router(charts_router)
app.include_router(saved_charts_router)
app.include_router(snapshots_router)
app.include_router(datasets_router)
app.include_router(models_router)
app.include_router(publications_router)


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
