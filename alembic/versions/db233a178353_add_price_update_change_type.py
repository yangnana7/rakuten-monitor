"""Add PRICE_UPDATE change type

Revision ID: db233a178353
Revises: 3f478b02dffe
Create Date: 2025-07-26 15:35:53.177282

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'db233a178353'
down_revision: Union[str, Sequence[str], None] = '3f478b02dffe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # PRICE_UPDATE enumの追加
    # SQLiteでは列の変更が制限されているため、PostgreSQLでのみ適用
    connection = op.get_bind()
    if connection.dialect.name == 'postgresql':
        # PostgreSQLの場合、ENUMタイプに新しい値を追加
        op.execute("ALTER TYPE changetype ADD VALUE IF NOT EXISTS 'PRICE_UPDATE'")
    
    # SQLiteでは新しいテーブル作成時にPRICE_UPDATEが含まれるため追加処理不要


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQLでENUM値の削除は複雑なため、警告のみ
    # 実際の運用では新しいテーブルを作成してデータ移行が必要
    pass
