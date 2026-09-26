"""新增简历操作时间线表 resume_events。

create_all 只建缺失的表、不会改已存在的表，老库需要显式迁移补上这张表。

事件语义（纯追加，前端展开即读）：
  uploaded           上传成功
  reparse_requested  用户点「重新解析」
  parse_started      解析任务开始（附解析模式 celery / inline）
  parse_succeeded    解析成功（附技能数 / 经历年数 / 耗时）
  parse_failed       解析失败（附错误原文）
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_resume_events"
down_revision = "0002_user_tool_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resume_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(length=32), nullable=False),
        # MySQL 不允许 TEXT 列带 DEFAULT，故用可空列（ORM 侧 default="" 在 Python 端生效）
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resume_events_resume_id", "resume_events", ["resume_id"])
    op.create_index("ix_resume_events_user_id", "resume_events", ["user_id"])

    _backfill()


def _backfill() -> None:
    """给迁移前就已存在的简历补时间线，否则老版本点开「操作历史」是空白。

    只补**确凿知道**的事实：上传时间/版本/文件名来自 resumes 本行；
    终态（ready / failed）也来自本行。这些补出来的行都标注「历史记录」，
    不伪造耗时等我们并不知道的信息。纯 Python 拼字符串，避开 CONCAT/|| 的方言差异。
    """
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, user_id, version, filename, file_size, status, error, created_at "
        "FROM resumes ORDER BY id"
    )).fetchall()
    if not rows:
        return

    known = {r[0] for r in conn.execute(sa.text("SELECT DISTINCT resume_id FROM resume_events"))}

    def _size(n: int) -> str:
        if n < 1024:
            return f"{n} B"
        if n < 1024 * 1024:
            return f"{n / 1024:.0f} KB"
        return f"{n / 1024 / 1024:.1f} MB"

    payload = []
    for rid, uid, version, filename, file_size, status, error, created_at in rows:
        if rid in known:
            continue
        payload.append((rid, uid, "uploaded",
                        f"v{version} · {filename} · {_size(file_size or 0)} · 历史记录",
                        created_at))
        if status == "ready":
            payload.append((rid, uid, "parse_succeeded",
                            "历史记录（时间线功能上线前的解析结果）", created_at))
        elif status == "failed":
            payload.append((rid, uid, "parse_failed",
                            f"{(error or '未知原因')[:300]} · 历史记录", created_at))

    if payload:
        conn.execute(
            sa.text(
                "INSERT INTO resume_events (resume_id, user_id, event, detail, created_at) "
                "VALUES (:resume_id, :user_id, :event, :detail, :created_at)"
            ),
            [
                {"resume_id": rid, "user_id": uid, "event": ev,
                 "detail": d, "created_at": ts}
                for rid, uid, ev, d, ts in payload
            ],
        )


def downgrade() -> None:
    # 直接 drop_table 即可：索引随表一起删。
    # 别写成 drop_index 后再 drop_table —— MySQL 会报
    # 1553 "Cannot drop index '...': needed in a foreign key constraint"
    # （user_id 上的外键需要一个索引，先删索引就把外键的索引删掉了）。
    op.drop_table("resume_events")
