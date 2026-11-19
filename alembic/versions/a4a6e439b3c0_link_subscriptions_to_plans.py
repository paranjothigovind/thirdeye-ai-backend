"""link_subscriptions_to_plans

Revision ID: a4a6e439b3c0
Revises: c644be8468be
Create Date: 2026-10-18 01:40:11.848011

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4a6e439b3c0'
down_revision: Union[str, Sequence[str], None] = 'c644be8468be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TYPE_TO_PLAN_CODE = {
    "FREE": "FREE",
    "PREMIUM": "PREMIUM",
    "ENTERPRISE": "ENTERPRISE",
}


def upgrade() -> None:
    bind = op.get_bind()

    plan_rows = bind.execute(sa.text("SELECT code, id FROM plans")).fetchall()
    plan_ids = {row[0]: row[1] for row in plan_rows}
    required_plan_codes = tuple(TYPE_TO_PLAN_CODE.values())
    missing_plans = [code for code in required_plan_codes if code not in plan_ids]
    if missing_plans:
        raise RuntimeError(f"Required plans are missing: {missing_plans}")

    type_rows = bind.execute(sa.text("SELECT DISTINCT type FROM subscriptions")).fetchall()
    subscription_types = {row[0] for row in type_rows}
    unknown_types = sorted(
        repr(value) for value in subscription_types if value not in TYPE_TO_PLAN_CODE
    )
    if unknown_types:
        raise RuntimeError(f"Unmapped subscription types: {unknown_types}")

    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.add_column(sa.Column("plan_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_subscriptions_plan_id_plans",
            "plans",
            ["plan_id"],
            ["id"],
        )

    for subscription_type, plan_code in TYPE_TO_PLAN_CODE.items():
        bind.execute(
            sa.text(
                "UPDATE subscriptions SET plan_id = :plan_id WHERE type = :type"
            ),
            {"plan_id": plan_ids[plan_code], "type": subscription_type},
        )


def downgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_constraint("fk_subscriptions_plan_id_plans", type_="foreignkey")
        batch_op.drop_column("plan_id")
