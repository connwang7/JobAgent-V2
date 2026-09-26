"""新增用户级工具服务密钥字段（serper / firecrawl）。

create_all 不会对已存在的表做 ALTER，故需显式迁移。
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_user_tool_keys"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MySQL 不允许 TEXT 列带 DEFAULT，故用可空列（ORM 侧 default="" 在 Python 端生效）
    op.add_column("users", sa.Column("serper_api_key_enc", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("firecrawl_api_key_enc", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "firecrawl_api_key_enc")
    op.drop_column("users", "serper_api_key_enc")
