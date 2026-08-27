"""THTWAAT Deploy Phase 5 — github_connections + github_oauth_states.

Adds the GitHub Connect connection-layer tables (see
app/static_sites/models.py::GitHubConnection/GitHubOAuthState). Purely
additive — no existing table or column is touched, and no auto-deploy/
webhook wiring happens yet. Deliberately no access_token/refresh_token
column on github_connections: this is a GitHub App installation, not an
OAuth App, so there is no GitHub user token to store in the first place —
see app/static_sites/github_client.py.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-08-22
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def upgrade() -> None:
    if not _has_table("github_connections"):
        op.create_table(
            "github_connections",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "workspace_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "site_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("static_sites.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("installation_id", sa.String(length=64), nullable=False),
            sa.Column("github_account_id", sa.String(length=64), nullable=False),
            sa.Column("github_username", sa.String(length=255), nullable=False),
            sa.Column("account_type", sa.String(length=32), nullable=True),
            sa.Column("repository_owner", sa.String(length=255), nullable=True),
            sa.Column("repository_name", sa.String(length=255), nullable=True),
            sa.Column("repository_id", sa.String(length=64), nullable=True),
            sa.Column("default_branch", sa.String(length=255), nullable=True),
            sa.Column("selected_branch", sa.String(length=255), nullable=True),
            sa.Column(
                "created_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("site_id", name="uq_github_connections_site"),
        )
        op.create_index("ix_github_connections_workspace", "github_connections", ["workspace_id"])

    if not _has_table("github_oauth_states"):
        op.create_table(
            "github_oauth_states",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("state_hash", sa.String(length=64), nullable=False, unique=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "workspace_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "site_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("static_sites.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index("ix_github_oauth_states_state_hash", "github_oauth_states", ["state_hash"], unique=True)
        op.create_index("ix_github_oauth_states_expires_at", "github_oauth_states", ["expires_at"])


def downgrade() -> None:
    if _has_table("github_oauth_states"):
        op.drop_index("ix_github_oauth_states_expires_at", table_name="github_oauth_states")
        op.drop_index("ix_github_oauth_states_state_hash", table_name="github_oauth_states")
        op.drop_table("github_oauth_states")
    if _has_table("github_connections"):
        op.drop_index("ix_github_connections_workspace", table_name="github_connections")
        op.drop_table("github_connections")
