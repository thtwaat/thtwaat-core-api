"""AI Platform Phase 1

Revision ID: 9589c534ec89
Revises: 5024c368b221
Create Date: 2026-07-16 09:54:06.592452

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9589c534ec89'
down_revision: Union[str, Sequence[str], None] = '5024c368b221'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    NOTE: The original auto-generated migration incorrectly tried to convert
    UUID columns in api_keys and webhooks tables to VARCHAR(36), which violated
    the foreign key constraint with companies.id (UUID type).
    Those columns are already the correct UUID type — no alteration needed.
    """
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
