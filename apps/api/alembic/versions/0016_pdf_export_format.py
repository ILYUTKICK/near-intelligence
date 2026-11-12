"""NI-059: admit the PDF export format alongside the Markdown ZIP bundle.

Lifts the ``app.export_jobs`` format CHECK from ``format = 'markdown_zip'`` to
``format IN ('markdown_zip', 'pdf')`` — the only schema change PDF export
needs. Everything else about a PDF job is identical to a Markdown ZIP job by
construction: the same frozen NI-056 plan (``plan``/``plan_sha256``), the same
lifecycle/lease/TTL/attempt machinery, and the same owner-scoped artifact
columns (``bundle``/``bundle_sha256``/``bundle_byte_size``) — for a PDF job
those columns carry the rendered PDF bytes with their identity, not a ZIP.

The column is named ``bundle`` for both formats; the stored media type is
recorded by the job's ``format`` column itself (routes map ``pdf`` to
``application/pdf`` and ``markdown_zip`` to ``application/zip``), and no
other naming change is made — renaming a live column for cosmetics would be
an unacceptable risk for zero behavior change.

Revision note: this migration's ``down_revision`` is ``0012_export_jobs``
(the export-jobs base). Migrations 0013/0014/0015 belong to parallel tasks
and are linearized at integration; until they land, 0016 sits directly on
0012 exactly as recorded here.
"""

from alembic import op

revision = "0016_pdf_export_format"
down_revision = "0015_publications"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        ALTER TABLE app.export_jobs
            DROP CONSTRAINT ck_export_jobs_format;
        ALTER TABLE app.export_jobs
            ADD CONSTRAINT ck_export_jobs_format
            CHECK (format IN ('markdown_zip', 'pdf'));
    """)


def downgrade():
    op.execute(r"""
        ALTER TABLE app.export_jobs
            DROP CONSTRAINT ck_export_jobs_format;
        ALTER TABLE app.export_jobs
            ADD CONSTRAINT ck_export_jobs_format
            CHECK (format = 'markdown_zip');
    """)
