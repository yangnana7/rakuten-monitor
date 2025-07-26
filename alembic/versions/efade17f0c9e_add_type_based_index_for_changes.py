"""Add type-based index for changes

Revision ID: efade17f0c9e
Revises: db233a178353
Create Date: 2025-07-26 15:42:55.235393

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'efade17f0c9e'
down_revision: Union[str, Sequence[str], None] = 'db233a178353'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # インデックス追加: 変更タイプ別の時系列検索用
    op.create_index('idx_changes_type_occurred', 'changes', ['type', 'occurred_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # インデックス削除
    op.drop_index('idx_changes_type_occurred', table_name='changes')
