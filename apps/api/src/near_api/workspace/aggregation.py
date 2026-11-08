"""Bounded owner-scoped continuation with independent approved-data context.

Only current canonical revision projections enter home. Public indicators reuse
NI-032 delivery in isolated savepoints: a source/catalog failure cannot discard
private research. No providers, collection or financial aggregation run here.
"""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import Connection, func, select
from sqlalchemy.exc import SQLAlchemyError

from near_api.auth.principal import Principal
from near_api.charts import saved
from near_api.datasets import delivery
from near_api.db.models import Document, DocumentBlock, Insight
from near_api.db.security import owner_scope, scoped_page
from near_api.schemas.home import (
    RECENT_LIST_CAP, DocumentProgress, DocumentSummary, HomeCounts, HomeIndicator,
    HomeInsightSummary, HomeResponse,
)
from near_api.schemas.saved_charts import SavedChartResponse

_DOCUMENT_COLUMNS = (
    Document.id, Document.title, Document.revision, Document.schema_version,
    Document.current_version_id, Document.created_at, Document.updated_at,
)
# A deliberately small research context; these are registered chart identifiers,
# never alternate metric definitions or results. Registry titles replace fallback
# labels as soon as the definition resolves.
INDICATORS = (
    ("intents-volume", "Provider-reported Intents gross volume"),
    ("gross-fees", "Provider-reported Intents gross fees"),
    ("observed-conversions", "Observed NEAR purchases"),
)


@dataclass(frozen=True)
class HomeOverview:
    recent_documents: tuple[DocumentSummary, ...]
    documents_total: int
    recent_charts: tuple[SavedChartResponse, ...] = ()
    recent_insights: tuple[HomeInsightSummary, ...] = ()
    indicators: tuple[HomeIndicator, ...] = ()

    def to_home_response(self) -> HomeResponse:
        return HomeResponse(
            recent_documents=self.recent_documents,
            counts=HomeCounts(documents=self.documents_total),
            recent_charts=self.recent_charts, recent_insights=self.recent_insights,
            indicators=self.indicators,
        )


def _excerpt(body: list | dict) -> str:
    """Plain-text navigation preview from validated stored rich text, bounded."""
    fragments: list[str] = []

    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            if value.get("type") == "text" and isinstance(value.get("text"), str):
                fragments.append(value["text"])
            else:
                visit(value.get("content", []))
                if value.get("type") == "paragraph":
                    fragments.append(" ")

    visit(body)
    return " ".join("".join(fragments).split())[:280]


def _indicator(connection: Connection, chart_id: str, fallback_title: str) -> HomeIndicator:
    title = fallback_title
    chart_version = None
    try:
        # A SQL error aborts only this savepoint; remaining indicators and the
        # already loaded private lists remain usable in the outer transaction.
        with connection.begin_nested():
            definition = delivery.load_chart_definition(connection, chart_id, None)
            title = definition.title
            chart_version = definition.version
            if definition.data_status != "available":
                return HomeIndicator(chart_id=chart_id, title=title, chart_version=chart_version, status="unavailable",
                                     series=None, reason=definition.unavailable_reason)
            _row, bindings, _metrics = delivery.load_chart_view_inputs(connection, chart_id, definition.version)
            required = tuple(metric_id for metric_id, role in bindings if role.startswith("required"))
            dataset_id = delivery.resolve_latest_version(connection, required)
            dataset, _content = delivery.load_approved_dataset(connection, dataset_id)
            end = dataset["end_date"]
            view = delivery.build_chart_view(
                connection, chart_id=chart_id, version=definition.version,
                start=end - timedelta(days=1), end=end, dataset_version=dataset_id, filters={})
            if not view.series:
                raise delivery.DeliveryDataNotReady("No registered series is available")
            return HomeIndicator(chart_id=chart_id, title=title, chart_version=chart_version, status="available",
                                 series=view.series[0], reason=None)
    except delivery.DeliveryError:
        reason = "Approved data is unavailable for this indicator. Explore its definition and sources."
    except SQLAlchemyError:
        reason = "This indicator could not be loaded. Your research remains available."
    return HomeIndicator(chart_id=chart_id, title=title, chart_version=chart_version, status="unavailable", series=None, reason=reason)


def home_overview(connection: Connection, principal: Principal) -> HomeOverview:
    """Owner predicates precede every limit; query count is independent of rows.

    Two document-page queries, one batched projection query (even for no docs),
    two saved-chart queries, one current-insight query, and at most three bounded
    canonical public resolutions. Historical versions never inflate progress.
    """
    page = scoped_page(connection, select(*_DOCUMENT_COLUMNS).order_by(
        Document.updated_at.desc(), Document.id), owner_scope(Document.owner_id, principal.id),
        limit=RECENT_LIST_CAP, offset=0)
    version_ids = [row["current_version_id"] for row in page.items if row["current_version_id"]]
    counters = connection.execute(select(
        DocumentBlock.document_version_id, DocumentBlock.block_type, func.count().label("count")
    ).where(owner_scope(DocumentBlock.owner_id, principal.id),
            DocumentBlock.document_version_id.in_(version_ids),
            DocumentBlock.block_type.in_(("heading", "liveChart", "insight")))
      .group_by(DocumentBlock.document_version_id, DocumentBlock.block_type)).mappings().all()
    progress: dict = {}
    field_by_type = {"heading": "headings", "liveChart": "charts", "insight": "insights"}
    for row in counters:
        progress.setdefault(row["document_version_id"], {"headings": 0, "charts": 0, "insights": 0})[
            field_by_type[row["block_type"]]] = row["count"]
    documents = tuple(DocumentSummary(**row, progress=DocumentProgress(**progress.get(
        row["current_version_id"], {"headings": 0, "charts": 0, "insights": 0}))) for row in page.items)
    charts, _total = saved.list_saved(connection, principal.id, limit=RECENT_LIST_CAP)
    insights = connection.execute(select(
        Insight.insight_id, Insight.document_id, Document.title.label("document_title"),
        Insight.block_id, Insight.type, Insight.classification, Insight.modified_at, Insight.body,
    ).join(Document, (Document.id == Insight.document_id) &
           (Document.current_version_id == Insight.document_version_id))
      .where(owner_scope(Insight.owner_id, principal.id), owner_scope(Document.owner_id, principal.id))
      .order_by(Insight.modified_at.desc(), Insight.document_id, Insight.insight_id)
      .limit(RECENT_LIST_CAP)).mappings().all()
    return HomeOverview(
        recent_documents=documents, documents_total=page.total, recent_charts=charts,
        recent_insights=tuple(HomeInsightSummary(**{key: row[key] for key in HomeInsightSummary.model_fields
                                                    if key != "excerpt"}, excerpt=_excerpt(row["body"]))
                              for row in insights),
        indicators=tuple(_indicator(connection, chart_id, title) for chart_id, title in INDICATORS),
    )
