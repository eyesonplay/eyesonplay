"""match_labels: hand-labelled ground truth per match

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_labels",
        sa.Column("match_id", sa.String(40), sa.ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("events", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("labelled_until_s", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("match_labels")
