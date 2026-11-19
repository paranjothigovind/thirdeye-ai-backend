"""add_course_external_id

Revision ID: a9d4c5e6f7b8
Revises: f8c2b3d4e5a6
Create Date: 2026-11-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9d4c5e6f7b8'
down_revision: Union[str, Sequence[str], None] = 'f8c2b3d4e5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("courses") as batch_op:
        batch_op.add_column(sa.Column("external_id", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_courses_external_id", ["external_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("courses") as batch_op:
        batch_op.drop_index("ix_courses_external_id")
        batch_op.drop_column("external_id")
