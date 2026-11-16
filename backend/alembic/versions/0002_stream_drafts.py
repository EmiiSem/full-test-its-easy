"""stream drafts for the offer editor

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "offer_catalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("keitaro_offer_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("country", sa.String(length=255), nullable=False, server_default=""),
    )
    op.create_index("ix_offer_catalog_keitaro_offer_id", "offer_catalog", ["keitaro_offer_id"], unique=True)
    op.create_table(
        "stream_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("keitaro_campaign_id", sa.Integer(), nullable=False),
        sa.Column("keitaro_stream_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("dirty", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_offers", sa.Text(), nullable=False, server_default="[]"),
        sa.UniqueConstraint("keitaro_campaign_id", "role", name="uq_stream_draft_campaign_role"),
    )
    op.create_index("ix_stream_drafts_keitaro_campaign_id", "stream_drafts", ["keitaro_campaign_id"])
    op.create_table(
        "stream_offer_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stream_draft_id", sa.Integer(), sa.ForeignKey("stream_drafts.id"), nullable=False),
        sa.Column("keitaro_offer_id", sa.Integer(), nullable=False),
        sa.Column("share", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.UniqueConstraint("stream_draft_id", "keitaro_offer_id", name="uq_stream_offer"),
    )
    op.create_index("ix_stream_offer_drafts_stream_draft_id", "stream_offer_drafts", ["stream_draft_id"])


def downgrade() -> None:
    op.drop_table("stream_offer_drafts")
    op.drop_table("stream_drafts")
    op.drop_index("ix_offer_catalog_keitaro_offer_id", table_name="offer_catalog")
    op.drop_table("offer_catalog")
