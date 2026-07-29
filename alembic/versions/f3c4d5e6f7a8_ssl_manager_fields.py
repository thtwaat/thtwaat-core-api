"""Alembic: SSL manager columns on company_domains.

Revision ID: f3c4d5e6f7a8
Revises: e2b3c4d5e6f7
Create Date: 2026-07-29 11:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "e2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    cols = [
        ("ssl_challenge", sa.String(32), "http-01"),
        ("certificate_serial", sa.String(128), None),
        ("ssl_last_checked_at", sa.DateTime(timezone=True), None),
        ("renew_attempts", sa.Integer(), "0"),
        ("renewal_error", sa.Text(), None),
        ("cert_path", sa.String(500), None),
        ("key_path", sa.String(500), None),
        ("nginx_config_path", sa.String(500), None),
        ("is_wildcard", sa.Boolean(), "false"),
    ]
    for name, col_type, default in cols:
        if not _has_column("company_domains", name):
            kwargs = {"nullable": False if default is not None and name != "certificate_serial" else True}
            if name in ("ssl_challenge",):
                kwargs["nullable"] = False
                kwargs["server_default"] = default
            elif name == "renew_attempts":
                kwargs["nullable"] = False
                kwargs["server_default"] = default
            elif name == "is_wildcard":
                kwargs["nullable"] = False
                kwargs["server_default"] = sa.text("false")
            op.add_column("company_domains", sa.Column(name, col_type, **kwargs))

    # Normalize legacy lowercase ssl_status → uppercase
    op.execute(
        """
        UPDATE company_domains SET ssl_status = UPPER(ssl_status)
        WHERE ssl_status IN ('none','pending','issued','renewing','expired','failed')
        """
    )
    # Map issued → ACTIVE for live domains
    op.execute(
        """
        UPDATE company_domains
        SET ssl_status = 'ACTIVE'
        WHERE ssl_status = 'ISSUED' AND status = 'LIVE'
        """
    )


def downgrade() -> None:
    for name in (
        "is_wildcard",
        "nginx_config_path",
        "key_path",
        "cert_path",
        "renewal_error",
        "renew_attempts",
        "ssl_last_checked_at",
        "certificate_serial",
        "ssl_challenge",
    ):
        if _has_column("company_domains", name):
            op.drop_column("company_domains", name)
