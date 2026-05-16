"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-15

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("avatar_url", sa.String(1024)),
        sa.Column("credits", sa.Integer, nullable=False, server_default="0"),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column("auth_provider", sa.String(50), nullable=False, server_default="local"),
        sa.Column("auth_provider_id", sa.String(255)),
        sa.Column("hashed_password", sa.String(255)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("cover_url", sa.String(2048)),
        sa.Column("share_token", sa.String(64), unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "style_prompt",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("model", sa.String(50), nullable=False, server_default="auto"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "preset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("presets.id", ondelete="SET NULL"),
        ),
        sa.Column("task_id", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("mode", sa.String(20), nullable=False, server_default="song"),
        sa.Column(
            "prompt",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("lyrics", sa.Text),
        sa.Column("model", sa.String(50), nullable=False, server_default="auto"),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mureka_trace_id", sa.String(255)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_message", sa.Text),
        sa.Column("credit_cost", sa.Integer, nullable=False, server_default="1"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_generations_user_created", "generations", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_generations_status_inflight",
        "generations",
        ["status", "created_at"],
        postgresql_where=sa.text("status IN ('queued','processing')"),
    )
    op.create_index(
        "uq_generations_task_id", "generations", ["task_id"], unique=True
    )

    op.create_table(
        "songs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
        ),
        sa.Column("mureka_song_id", sa.String(255)),
        sa.Column("variant", sa.String(4), nullable=False, server_default="A"),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("mp3_url", sa.String(2048)),
        sa.Column("wav_url", sa.String(2048)),
        sa.Column("cover_url", sa.String(2048)),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("bpm", sa.Integer),
        sa.Column("key", sa.String(10)),
        sa.Column(
            "genres",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column(
            "moods",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column(
            "is_favorite", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_songs_generation", "songs", ["generation_id"])
    op.create_index("ix_songs_project", "songs", ["project_id"])
    op.create_index("ix_songs_mureka_uq", "songs", ["mureka_song_id"], unique=True)

    op.create_table(
        "stems",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "song_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("songs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stem_type", sa.String(20), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("duration_ms", sa.Integer),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "credit_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generations.id", ondelete="SET NULL"),
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("reason", sa.String(255)),
        sa.Column("stripe_payment_intent", sa.String(255)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_credit_ledger_user_created", "credit_ledger", ["user_id", "created_at"]
    )
    op.create_index("ix_credit_ledger_generation", "credit_ledger", ["generation_id"])


def downgrade() -> None:
    op.drop_index("ix_credit_ledger_generation", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_user_created", table_name="credit_ledger")
    op.drop_table("credit_ledger")
    op.drop_table("stems")
    op.drop_index("ix_songs_mureka_uq", table_name="songs")
    op.drop_index("ix_songs_project", table_name="songs")
    op.drop_index("ix_songs_generation", table_name="songs")
    op.drop_table("songs")
    op.drop_index("uq_generations_task_id", table_name="generations")
    op.drop_index("ix_generations_status_inflight", table_name="generations")
    op.drop_index("ix_generations_user_created", table_name="generations")
    op.drop_table("generations")
    op.drop_table("presets")
    op.drop_table("projects")
    op.drop_table("users")
