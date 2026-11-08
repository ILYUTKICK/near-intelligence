"""`GET /api/home` — the first private HTTP route (NI-022).

Authorization flows exclusively through `get_principal` (NI-018): 401 without
or with an invalid session, 403 fail closed for a disabled local account.
The database connection uses the transaction-local verified identity
(`principal_transaction`, NI-019) and the aggregation pages the owner
predicate before LIMIT/OFFSET, so responses and counts are owner-scoped by
construction. Every response of this private route is `Cache-Control:
no-store`; no private response is ever cacheable.

A deleted (or never-owned) target referenced from the recent lists is simply
absent from the aggregated rows; if any helper raises `ResourceNotFound`, the
contracts layer answers with the one standardized generic 404 shape.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.engine import Engine

from near_api.auth.principal import Principal, get_principal, get_runtime_engine
from near_api.db.security import principal_transaction
from near_api.schemas.common import ErrorResponse
from near_api.schemas.home import HomeResponse
from near_api.workspace.aggregation import home_overview

router = APIRouter(prefix="/api", tags=["workspace"])

PrincipalDependency = Annotated[Principal, Depends(get_principal)]
RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

_PRIVATE_ERROR_RESPONSES = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in (
        (401, "Missing or invalid session"),
        (403, "Verified account is disabled"),
        (404, "Referenced target does not exist for this owner"),
    )
}


@router.get("/home", response_model=HomeResponse, operation_id="getWorkspaceHome",
            summary="Owner-scoped workspace home aggregation",
            responses=_PRIVATE_ERROR_RESPONSES)
def workspace_home(principal: PrincipalDependency, engine: RuntimeEngineDependency,
                   response: Response) -> HomeResponse:
    """Return the verified principal's recent documents and scoped totals.

    Private lists use current owner-scoped projections. Each approved public
    indicator resolves independently; source failures do not hide research.
    """
    with principal_transaction(engine, principal) as connection:
        overview = home_overview(connection, principal)
    # Private payload: no-store overrides any client/proxy caching directive.
    response.headers["Cache-Control"] = "no-store"
    return overview.to_home_response()
