"""NI-080: join the independently applied PDF and organization branches.

Both parent revisions shipped in separate PRs from 0012_export_jobs. Keep
those revision identities and operations unchanged: upgrading an environment
that already applied either parent must apply only its missing sibling.
This no-op merge makes the combined graph's ``head`` unambiguous.
"""

revision = "0018_merge_pdf_organization"
down_revision = ("0014_document_organization", "0016_pdf_export_format")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
