"""add_plan_catalog

Revision ID: c644be8468be
Revises: bba5db5bc2fe
Create Date: 2026-10-18 01:38:17.014812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c644be8468be'
down_revision: Union[str, Sequence[str], None] = 'bba5db5bc2fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_amount", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("billing_interval", sa.String(length=20), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("chat_limit", sa.Integer(), nullable=True),
        sa.Column("ingestion_limit", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plans_code", "plans", ["code"], unique=True)
    op.create_index("ix_plans_id", "plans", ["id"], unique=False)

    bind = op.get_bind()
    plans = sa.table(
        "plans",
        sa.column("code"),
        sa.column("name"),
        sa.column("description"),
        sa.column("price_amount"),
        sa.column("currency"),
        sa.column("billing_interval"),
        sa.column("duration_days"),
        sa.column("is_active"),
        sa.column("chat_limit"),
        sa.column("ingestion_limit"),
    )

    existing_codes = {row[0] for row in bind.execute(sa.text("SELECT code FROM plans"))}

    seed_rows = [
        {
            "code": "FREE",
            "name": "Free",
            "description": None,
            "price_amount": 0,
            "currency": "INR",
            "billing_interval": None,
            "duration_days": None,
            "is_active": True,
            "chat_limit": None,
            "ingestion_limit": None,
        },
        {
            "code": "PREMIUM",
            "name": "Premium",
            "description": None,
            "price_amount": None,
            "currency": "INR",
            "billing_interval": None,
            "duration_days": None,
            "is_active": True,
            "chat_limit": None,
            "ingestion_limit": None,
        },
        {
            "code": "ENTERPRISE",
            "name": "Enterprise",
            "description": None,
            "price_amount": None,
            "currency": "INR",
            "billing_interval": None,
            "duration_days": None,
            "is_active": True,
            "chat_limit": None,
            "ingestion_limit": None,
        },
    ]

    for row in seed_rows:
        if row["code"] not in existing_codes:
            bind.execute(plans.insert().values(**row))


def downgrade() -> None:
    op.drop_index("ix_plans_id", table_name="plans")
    op.drop_index("ix_plans_code", table_name="plans")
    op.drop_table("plans")
