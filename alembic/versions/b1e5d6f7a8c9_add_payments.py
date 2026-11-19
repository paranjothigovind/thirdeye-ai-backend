"""add_payments

Revision ID: b1e5d6f7a8c9
Revises: a9d4c5e6f7b8
Create Date: 2026-11-17 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1e5d6f7a8c9'
down_revision: Union[str, Sequence[str], None] = 'a9d4c5e6f7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column("razorpay_order_id", sa.String(length=64), nullable=False),
        sa.Column("razorpay_payment_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="created"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_id", "payments", ["id"], unique=False)
    op.create_index("ix_payments_user_id", "payments", ["user_id"], unique=False)
    op.create_index("ix_payments_course_id", "payments", ["course_id"], unique=False)
    op.create_index("ix_payments_status", "payments", ["status"], unique=False)
    op.create_index("ix_payments_user_course", "payments", ["user_id", "course_id"], unique=False)
    op.create_index("ix_payments_razorpay_order_id", "payments", ["razorpay_order_id"], unique=True)
    op.create_index("ix_payments_razorpay_payment_id", "payments", ["razorpay_payment_id"], unique=True)


def downgrade() -> None:
    for name in ("ix_payments_razorpay_payment_id", "ix_payments_razorpay_order_id",
                 "ix_payments_user_course", "ix_payments_status", "ix_payments_course_id",
                 "ix_payments_user_id", "ix_payments_id"):
        op.drop_index(name, table_name="payments")
    op.drop_table("payments")
