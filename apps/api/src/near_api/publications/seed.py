"""Operator seeding of public research publications (NI-045).

Creating publications is an operator CLI flow, never a browser POST API
(API_SPECIFICATION): :mod:`near_api.publications.seed` is the ONLY writer of
``app.research_publications`` and runs exclusively with the dedicated
unprivileged ``near_operator`` credential (``python -m near_api.publications.seed``).
The runtime API only ever reads published rows through ``near_app`` and
imports nothing from this module, so endpoint access can never create a
publication.

Fail-closed seed gate (the database CHECK constraints are defense in depth,
not the gate):

- the ``content`` file MUST parse as a canonical editor document through
  :func:`near_api.documents.schema.parse_document` and fit in a copy with
  its attribution paragraph. Structured pins must resolve to public inputs;
  owner-scoped snapshots cannot be published;
- ``content_sha256`` is the canonical content hash the API serves, computed
  over the canonical rendering;
- every ``evidence_manifest`` entry MUST be a typed public reference:
  ``model_run`` ids must reference PUBLISHED ``app.model_runs`` rows and
  ``citation`` ids must reference ``scope='public'`` artifacts. Model runs
  referenced in the content or manifest are bound into
  ``app.publication_model_runs``;
- the slug grammar is the one the public route and the idempotency route-key
  bound accept.

Idempotent reseeding: the (slug, version) pair is unique. Re-seeding the
IDENTICAL release (same title, same canonical content hash, same manifest)
is a no-op; any divergence is a typed conflict — published releases are
immutable, a correction seeds a new version or deletes the row first.

Example::

    uv run --project apps/api python -m near_api.publications.seed \\
        --database-url postgresql+psycopg://near_operator:...@host/db \\
        --slug near-thesis-2026-11 --version 1 --title "..." \\
        --content-file path/to/canonical-content.json \\
        --evidence-manifest-file path/to/evidence-manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.engine import Connection, Engine

from near_api.datasets.delivery import DeliveryInvalidFilter
from near_api.db.models import Artifact, ModelRun
from near_api.documents.context_resolver import (
    load_chart_definition,
    require_approved_dataset,
    require_metric_coverage,
    validate_selection_against_definition,
    verify_chart_context,
    verify_model_result_pins,
)
from near_api.documents.schema import (
    CanonicalDocument,
    DocumentSchemaError,
    canonical_bytes,
    parse_document,
)
from near_api.evidence.targets import validate_public_targets
from near_api.insights.schemas import ResolvedContext
from near_api.ingestion.archive import (
    OperatorDatabaseError,
    _assert_operator,
    create_operator_engine,
)
from near_api.publications.duplicate import (
    ATTRIBUTION_TEXT,
    attribution_paragraph,
    parse_publication_content,
)
from near_api.publications.schemas import (
    MAX_MANIFEST_ENTRIES,
    SLUG_PATTERN,
    PublicationEvidenceRef,
)
from near_api.schemas.chart_selection import ChartSelection

SLUG_RE = re.compile(SLUG_PATTERN)


class PublicationSeedError(ValueError):
    """A publication seed input failed the fail-closed gate."""


class PublicationSeedConflict(RuntimeError):
    """The (slug, version) release exists with different content."""


@dataclass(frozen=True)
class SeededPublication:
    id: UUID
    slug: str
    version: int
    content_sha256: str
    already_published: bool


def seed_publication(database_url: str, *, slug: str, version: int, title: str,
                     content: dict, evidence_manifest: list) -> SeededPublication:
    """Verify and insert one publication release (write-once, idempotent).

    The caller must have approved the release for publication; this store
    performs no editorial review of its own beyond the fail-closed checks
    above.
    """
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        raise PublicationSeedError("slug must match ^[a-z0-9][a-z0-9-]{0,79}$")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise PublicationSeedError("version must be a positive integer")
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise PublicationSeedError("title must be 1-200 characters")
    if not isinstance(evidence_manifest, list) \
            or len(evidence_manifest) > MAX_MANIFEST_ENTRIES:
        raise PublicationSeedError(
            f"evidence_manifest must be a list of at most {MAX_MANIFEST_ENTRIES} entries")

    canonical = parse_publication_content(content)
    attribution = ATTRIBUTION_TEXT.format(title=title, slug=slug, version=version)
    parse_document({**canonical.canonical, "content": [
        attribution_paragraph(attribution), *canonical.canonical["content"],
    ]})
    content_json = canonical_bytes(canonical.canonical).decode("utf-8")

    manifest_refs: list[PublicationEvidenceRef] = []
    for index, entry in enumerate(evidence_manifest):
        try:
            manifest_refs.append(PublicationEvidenceRef.model_validate(entry))
        except ValidationError as error:
            raise PublicationSeedError(
                f"evidence_manifest[{index}] is not a typed public evidence "
                f"reference: {error.error_count()} validation error(s)") from error

    engine = create_operator_engine(database_url)
    try:
        with engine.begin() as connection:
            _assert_operator(connection)
            _verify_manifest_targets(connection, manifest_refs)
            manifest_json = json.dumps(evidence_manifest, ensure_ascii=False,
                                       sort_keys=True)
            existing = connection.execute(text(
                "SELECT id, title, content_sha256, evidence_manifest::text AS manifest "
                "FROM app.research_publications WHERE slug = :slug AND version = :version"
            ), {"slug": slug, "version": version}).mappings().first()
            if existing is not None:
                same = (existing["title"] == title
                        and existing["content_sha256"] == canonical.content_sha256
                        and _manifest_equivalent(existing["manifest"], manifest_refs))
                if not same:
                    raise PublicationSeedConflict(
                        f"Publication {slug} v{version} already exists with different "
                        "content; published releases are immutable — seed a new version")
            _verify_content_pins(connection, canonical)
            if existing is not None:
                return SeededPublication(id=existing["id"], slug=slug, version=version,
                                         content_sha256=existing["content_sha256"],
                                         already_published=True)
            publication_id = uuid4()
            connection.execute(text("""
                INSERT INTO app.research_publications
                    (id, slug, version, title, content, evidence_manifest, content_sha256)
                VALUES (:id, :slug, :version, :title,
                        CAST(:content AS jsonb), CAST(:manifest AS jsonb), :sha256)
            """), {
                "id": str(publication_id), "slug": slug, "version": version,
                "title": title, "content": content_json, "manifest": manifest_json,
                "sha256": canonical.content_sha256,
            })
            run_ids = {ref.id for ref in manifest_refs if ref.kind == "model_run"}
            run_ids.update(model.model_run_id for model in canonical.model_results)
            run_ids.update(item.target_id for item in canonical.evidence
                           if item.target_kind == "model_run")
            for run_id in sorted(run_ids):
                connection.execute(text(
                    "INSERT INTO app.publication_model_runs (publication_id, model_run_id) "
                    "VALUES (:publication, :run)"),
                    {"publication": str(publication_id), "run": str(run_id)})
            return SeededPublication(id=publication_id, slug=slug, version=version,
                                     content_sha256=canonical.content_sha256,
                                     already_published=False)
    finally:
        engine.dispose()


def _manifest_equivalent(stored_manifest_text: str,
                         refs: list[PublicationEvidenceRef]) -> bool:
    try:
        stored = json.loads(stored_manifest_text)
    except ValueError:
        return False
    if not isinstance(stored, list) or len(stored) != len(refs):
        return False
    try:
        parsed = [PublicationEvidenceRef.model_validate(entry) for entry in stored]
    except ValidationError:
        return False
    return sorted((ref.kind, str(ref.id), ref.label or "") for ref in parsed) == \
        sorted((ref.kind, str(ref.id), ref.label or "") for ref in refs)


def _verify_content_pins(connection: Connection, canonical: CanonicalDocument) -> None:
    """Resolve public pins without consulting the latest pointers or private tables."""
    for chart in canonical.live_charts:
        definition = load_chart_definition(connection, chart.chart_definition_version_id,
                                           error_path="liveChart.chart_definition_version_id")
        selection = ChartSelection.model_validate(chart.selection)
        validate_selection_against_definition(definition, selection.start, selection.end,
                                              selection.filters)
        require_approved_dataset(connection, chart.observed_dataset_version_id,
                                 "liveChart.observed_dataset_version_id")
        require_metric_coverage(connection, definition, chart.observed_dataset_version_id,
                                error_path="liveChart.observed_dataset_version_id")
    for table in canonical.data_tables:
        if table.dataset_version_id is not None:
            require_approved_dataset(connection, table.dataset_version_id,
                                     "dataTable.dataset_version_id")
    for insight in canonical.insights:
        context = ResolvedContext.model_validate(insight.context)
        verify_chart_context(connection, context, resolved_at=datetime.now(UTC))
    for model in canonical.model_results:
        verify_model_result_pins(connection, model, error_path="modelResult")
    validate_public_targets(connection, canonical)


def _verify_manifest_targets(connection: Connection,
                             refs: list[PublicationEvidenceRef]) -> None:
    """Every manifest reference must exist in its public immutable catalog."""
    run_ids = [ref.id for ref in refs if ref.kind == "model_run"]
    citation_ids = [ref.id for ref in refs if ref.kind == "citation"]
    if run_ids:
        published = {str(row) for row in connection.scalars(
            select(ModelRun.run_id).where(ModelRun.status == "published",
                                          ModelRun.run_id.in_(run_ids)))}
        missing = sorted(str(item) for item in run_ids if str(item) not in published)
        if missing:
            raise PublicationSeedError(
                "manifest references model runs that are not published: "
                + ", ".join(missing))
    if citation_ids:
        public = {str(row) for row in connection.scalars(
            select(Artifact.id).where(Artifact.scope == "public",
                                      Artifact.id.in_(citation_ids)))}
        missing = sorted(str(item) for item in citation_ids if str(item) not in public)
        if missing:
            raise PublicationSeedError(
                "manifest references citations that are not public artifacts: "
                + ", ".join(missing))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m near_api.publications.seed", description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", required=True,
                        help="near_operator psycopg credential (operator role only)")
    parser.add_argument("--slug", required=True,
                        help="public slug ^[a-z0-9][a-z0-9-]{0,79}$")
    parser.add_argument("--version", required=True, type=int,
                        help="release version (>= 1)")
    parser.add_argument("--title", required=True, help="public release title (1-200 chars)")
    parser.add_argument("--content-file", required=True, type=Path,
                        help="JSON file with the canonical editor document projection")
    parser.add_argument("--evidence-manifest-file", type=Path, default=None,
                        help="optional JSON file with the public evidence manifest list")
    args = parser.parse_args(argv)

    try:
        content = json.loads(args.content_file.read_text(encoding="utf-8"))
        manifest = json.loads(args.evidence_manifest_file.read_text(encoding="utf-8")) \
            if args.evidence_manifest_file else []
        result = seed_publication(args.database_url, slug=args.slug,
                                  version=args.version, title=args.title,
                                  content=content, evidence_manifest=manifest)
    except (PublicationSeedError, PublicationSeedConflict, OperatorDatabaseError,
            DocumentSchemaError, DeliveryInvalidFilter, ValidationError,
            json.JSONDecodeError, OSError) as error:
        print(f"Publication seed refused: {error}", file=sys.stderr)
        return 4
    state = "already published (identical release)" if result.already_published else "published"
    print(f"Publication {result.slug} v{result.version} {state}: "
          f"{result.id} content_sha256={result.content_sha256}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
