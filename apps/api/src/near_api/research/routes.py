"""Read-only research history over approved canonical datasets."""
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.engine import Engine

from near_api.auth.principal import get_runtime_engine
from near_api.db.session import user_transaction
from near_api.research.history import ResearchHistoryResponse, build_history

router = APIRouter(prefix="/api/research", tags=["research"])


@router.get("/history", response_model=ResearchHistoryResponse,
            operation_id="getResearchHistory",
            responses={422: {"description": "Unsupported source or range"},
                       503: {"description": "Approved research data unavailable"}})
def get_history(engine: Annotated[Engine, Depends(get_runtime_engine)], response: Response,
                start: date | None = None, end: date | None = None,
                source: Annotated[str, Query(max_length=40)] = "SRC-LLAMA",
                dataset_version: UUID | None = None) -> ResearchHistoryResponse:
    with user_transaction(engine, None) as connection:
        result = build_history(connection, source=source, start=start, end=end,
                               dataset_version=dataset_version)
    # Purchases can resolve a separate latest pointer even with a pinned provider dataset.
    response.headers["Cache-Control"] = "public, max-age=60"
    return result
