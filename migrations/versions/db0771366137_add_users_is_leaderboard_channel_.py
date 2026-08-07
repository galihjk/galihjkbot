"""add users is_leaderboard_channel_subscribed

Revision ID: db0771366137
Revises: 9c4d7e2a5f18
Create Date: 2026-08-07 20:09:21.267935

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db0771366137'
down_revision: Union[str, Sequence[str], None] = '9c4d7e2a5f18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column(
            'is_leaderboard_channel_subscribed',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'is_leaderboard_channel_subscribed')
