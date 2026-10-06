"""matches.sport (football | tennis)

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matches",
        sa.Column(
            "sport",
            sa.Enum("football", "tennis", name="sport", native_enum=False, length=32),
            nullable=False,
            server_default="football",
        ),
    )


def downgrade() -> None:
    op.drop_column("matches", "sport")
