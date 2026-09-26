"""初始迁移：按 ORM 元数据建全量表。

采用 metadata.create_all 的等价写法，保证与 app/models 定义零漂移；
后续增量变更请使用 `alembic revision --autogenerate` 生成独立迁移。
"""
from alembic import op

from app.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
