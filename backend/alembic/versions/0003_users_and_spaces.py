"""users, auth identities, spaces; tasks belong to a space

Every legacy Telegram user found in tasks.user_id becomes an internal user
with a Telegram identity and a personal space that receives all their tasks.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-27 12:00:00+01:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

auth_provider = sa.Enum("telegram", "email", name="auth_provider")
space_kind = sa.Enum("personal", "shared", name="space_kind")
space_role = sa.Enum("owner", "editor", "viewer", name="space_role")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("locale", sa.String(8), nullable=False, server_default="uk"),
        sa.Column("theme", sa.String(16), nullable=False, server_default="dark"),
        sa.Column("accent_color", sa.String(16), nullable=True),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Vienna"),
        *_timestamps(),
    )
    op.create_table(
        "auth_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", auth_provider, nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("provider", "external_id", name="uq_auth_identities_provider_external"),
    )
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])
    op.create_table(
        "spaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("color", sa.String(16), nullable=True),
        sa.Column("icon", sa.String(32), nullable=True),
        sa.Column("kind", space_kind, nullable=False),
        *_timestamps(),
    )
    op.create_table(
        "space_members",
        sa.Column("space_id", sa.Integer(), sa.ForeignKey("spaces.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", space_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_space_members_user_id", "space_members", ["user_id"])

    op.add_column("tasks", sa.Column("space_id", sa.Integer(), nullable=True))
    op.add_column("tasks", sa.Column("created_by_id", sa.Integer(), nullable=True))

    bind = op.get_bind()
    telegram_ids = bind.execute(sa.text("SELECT DISTINCT user_id FROM tasks ORDER BY user_id")).scalars().all()
    for telegram_id in telegram_ids:
        user_id = bind.execute(sa.text("INSERT INTO users DEFAULT VALUES RETURNING id")).scalar_one()
        bind.execute(
            sa.text("INSERT INTO auth_identities (user_id, provider, external_id) VALUES (:u, 'telegram', :e)"),
            {"u": user_id, "e": str(telegram_id)},
        )
        space_id = bind.execute(
            sa.text("INSERT INTO spaces (name, kind) VALUES ('Особисте', 'personal') RETURNING id")
        ).scalar_one()
        bind.execute(
            sa.text("INSERT INTO space_members (space_id, user_id, role) VALUES (:s, :u, 'owner')"),
            {"s": space_id, "u": user_id},
        )
        bind.execute(
            sa.text("UPDATE tasks SET space_id = :s, created_by_id = :u WHERE user_id = :t"),
            {"s": space_id, "u": user_id, "t": telegram_id},
        )

    op.alter_column("tasks", "space_id", nullable=False)
    op.alter_column("tasks", "created_by_id", nullable=False)
    op.create_foreign_key("fk_tasks_space_id", "tasks", "spaces", ["space_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_tasks_created_by_id", "tasks", "users", ["created_by_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_tasks_space_id", "tasks", ["space_id"])
    op.create_index("ix_tasks_created_by_id", "tasks", ["created_by_id"])
    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_column("tasks", "user_id")


def downgrade() -> None:
    op.add_column("tasks", sa.Column("user_id", sa.BigInteger(), nullable=True))
    op.execute(
        """
        UPDATE tasks SET user_id = ai.external_id::bigint
        FROM auth_identities ai
        WHERE ai.user_id = tasks.created_by_id AND ai.provider = 'telegram'
        """
    )
    op.execute("DELETE FROM tasks WHERE user_id IS NULL")
    op.alter_column("tasks", "user_id", nullable=False)
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.drop_index("ix_tasks_created_by_id", table_name="tasks")
    op.drop_index("ix_tasks_space_id", table_name="tasks")
    op.drop_constraint("fk_tasks_created_by_id", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_space_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "created_by_id")
    op.drop_column("tasks", "space_id")

    op.drop_table("space_members")
    op.drop_table("spaces")
    op.drop_table("auth_identities")
    op.drop_table("users")
    bind = op.get_bind()
    space_role.drop(bind, checkfirst=True)
    space_kind.drop(bind, checkfirst=True)
    auth_provider.drop(bind, checkfirst=True)
