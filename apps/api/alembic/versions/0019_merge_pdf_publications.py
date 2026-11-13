"""Join the published-research and PDF migration histories for NI-059.

Keep existing revision IDs and parent relationships so a database at either
head applies the missing branch before reaching the combined head.
"""

revision = "0019_merge_pdf_publications"
down_revision = ("0015_publications", "0018_merge_pdf_organization")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
