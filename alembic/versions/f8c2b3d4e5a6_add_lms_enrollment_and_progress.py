"""add_lms_enrollment_and_progress

Revision ID: f8c2b3d4e5a6
Revises: e7b1a2c3d4f5
Create Date: 2026-10-27 02:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8c2b3d4e5a6'
down_revision: Union[str, Sequence[str], None] = 'e7b1a2c3d4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. course_enrollments
    op.create_table(
        "course_enrollments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course_id", name="uq_user_course_enrollment"),
    )
    op.create_index("ix_course_enrollments_id", "course_enrollments", ["id"], unique=False)
    op.create_index("ix_course_enrollments_user_id", "course_enrollments", ["user_id"], unique=False)
    op.create_index("ix_course_enrollments_course_id", "course_enrollments", ["course_id"], unique=False)

    # 2. user_lesson_progress
    op.create_table(
        "user_lesson_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("progress_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_position_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson_progress"),
    )
    op.create_index("ix_user_lesson_progress_id", "user_lesson_progress", ["id"], unique=False)
    op.create_index("ix_user_lesson_progress_user_id", "user_lesson_progress", ["user_id"], unique=False)
    op.create_index("ix_user_lesson_progress_lesson_id", "user_lesson_progress", ["lesson_id"], unique=False)
    op.create_index("ix_user_lesson_progress_course_id", "user_lesson_progress", ["course_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_lesson_progress_course_id", table_name="user_lesson_progress")
    op.drop_index("ix_user_lesson_progress_lesson_id", table_name="user_lesson_progress")
    op.drop_index("ix_user_lesson_progress_user_id", table_name="user_lesson_progress")
    op.drop_index("ix_user_lesson_progress_id", table_name="user_lesson_progress")
    op.drop_table("user_lesson_progress")

    op.drop_index("ix_course_enrollments_course_id", table_name="course_enrollments")
    op.drop_index("ix_course_enrollments_user_id", table_name="course_enrollments")
    op.drop_index("ix_course_enrollments_id", table_name="course_enrollments")
    op.drop_table("course_enrollments")
