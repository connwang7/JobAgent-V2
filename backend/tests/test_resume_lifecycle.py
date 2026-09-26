"""简历删除 / 一键清空 / 操作时间线的回归测试（不需要 DB、Redis、对象存储）。

锁死的不变量：
  1. 删除单个版本要**同时**清掉对象、时间线、主记录；
  2. 对象已经不在（或删不动）也必须把记录删掉 —— 否则用户陷入"删不掉"死角；
  3. 一键清空只删自己的数据，并准确报告对象删除数；
  4. `dispatch_or_inline` 的 kwargs 只喂给进程内实现（Celery 的 .delay() 拿不到 kwargs）。
"""
import asyncio

import pytest

from app.core.errors import NotFoundError, ValidationError
from app.models.resume import Resume
from app.services import resume as resume_service
from app.workers import dispatch as d


# ---------- 测试替身 ----------

class _FakeSession:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


class _FakeResumeRepo:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.session = _FakeSession()
        self.events: list[tuple] = []
        self.deleted_rows: list = []
        self.deleted_events: list[int] = []

    async def get(self, rid):
        return next((r for r in self.rows if r.id == rid), None)

    async def list_by_user(self, uid):
        return [r for r in self.rows if r.user_id == uid]

    async def add(self, obj):
        self.rows.append(obj)
        return obj

    async def add_event(self, resume_id, user_id, event, detail=""):
        self.events.append((resume_id, user_id, event, detail))

    async def delete_events(self, resume_id):
        self.deleted_events.append(resume_id)

    async def delete(self, obj):
        self.deleted_rows.append(obj)
        self.rows.remove(obj)

    async def delete_all_by_user(self, user_id):
        n = len([r for r in self.rows if r.user_id == user_id])
        self.rows = [r for r in self.rows if r.user_id != user_id]
        return n


class _FakeStorage:
    """key 在 keys 里才算删得掉；否则返回 False（幂等语义）。"""

    def __init__(self, keys):
        self.keys = set(keys)
        self.deleted: list[str] = []
        self.put_keys: list[str] = []

    def put(self, key: str, data: bytes, content_type: str = "") -> str:
        self.put_keys.append(key)
        self.keys.add(key)
        return key

    def delete(self, key: str) -> bool:
        self.deleted.append(key)
        if key in self.keys:
            self.keys.discard(key)
            return True
        return False


def _resume(rid: int, uid: int, *, version=1, file_key="k", status="ready", filename="a.pdf"):
    return Resume(id=rid, user_id=uid, file_key=file_key, filename=filename,
                  file_size=1024, version=version, status=status, error="")


class _User:
    id = 11


# ---------- human_size ----------

@pytest.mark.parametrize("size,expected", [
    (0, "0 B"),
    (904, "904 B"),
    (2048, "2 KB"),
    (303 * 1024, "303 KB"),
    (10 * 1024 * 1024, "10.0 MB"),
])
def test_human_size(size, expected):
    assert resume_service.human_size(size) == expected


# ---------- 删除单个版本 ----------

def test_delete_resume_removes_object_events_and_row(monkeypatch):
    repo = _FakeResumeRepo([_resume(7, 11, version=3, file_key="resumes/11/x.pdf")])
    storage = _FakeStorage({"resumes/11/x.pdf"})
    monkeypatch.setattr(resume_service, "get_storage", lambda: storage)

    result = asyncio.run(resume_service.delete_resume(repo, _User(), 7))

    assert result == {"id": 7, "version": 3, "object_deleted": True}
    assert storage.deleted == ["resumes/11/x.pdf"]
    assert repo.deleted_events == [7]
    assert [r.id for r in repo.deleted_rows] == [7]
    assert repo.rows == []
    assert repo.session.commits == 1


def test_delete_resume_keeps_going_when_object_is_gone(monkeypatch):
    """对象已不存在 → object_deleted=False，但记录照样删掉（不能卡住用户）。"""
    repo = _FakeResumeRepo([_resume(7, 11, file_key="missing.pdf")])
    storage = _FakeStorage(set())  # 什么也删不掉
    monkeypatch.setattr(resume_service, "get_storage", lambda: storage)

    result = asyncio.run(resume_service.delete_resume(repo, _User(), 7))

    assert result["object_deleted"] is False
    assert repo.rows == [], "存储删失败不应该阻止记录删除"


def test_delete_resume_skips_storage_when_no_file_key(monkeypatch):
    repo = _FakeResumeRepo([_resume(7, 11, file_key="")])
    storage = _FakeStorage(set())
    monkeypatch.setattr(resume_service, "get_storage", lambda: storage)

    result = asyncio.run(resume_service.delete_resume(repo, _User(), 7))

    assert result["object_deleted"] is False
    assert storage.deleted == [], "空 key 不该去调存储"


def test_delete_resume_rejects_other_users_resume(monkeypatch):
    repo = _FakeResumeRepo([_resume(7, 999)])  # 属于别的用户
    monkeypatch.setattr(resume_service, "get_storage", lambda: _FakeStorage(set()))

    with pytest.raises(NotFoundError):
        asyncio.run(resume_service.delete_resume(repo, _User(), 7))

    assert repo.rows != [], "越权删除不能生效"


# ---------- 一键清空 ----------

def test_clear_resumes_noop_when_empty(monkeypatch):
    repo = _FakeResumeRepo([])
    storage = _FakeStorage(set())
    monkeypatch.setattr(resume_service, "get_storage", lambda: storage)

    result = asyncio.run(resume_service.clear_resumes(repo, _User()))

    assert result == {"deleted": 0, "objects_deleted": 0}
    assert storage.deleted == []


def test_clear_resumes_only_touches_own_rows(monkeypatch):
    repo = _FakeResumeRepo([
        _resume(1, 11, file_key="a.pdf"),
        _resume(2, 11, file_key="b.pdf"),
        _resume(3, 999, file_key="other.pdf"),
    ])
    storage = _FakeStorage({"a.pdf", "b.pdf", "other.pdf"})
    monkeypatch.setattr(resume_service, "get_storage", lambda: storage)

    result = asyncio.run(resume_service.clear_resumes(repo, _User()))

    assert result == {"deleted": 2, "objects_deleted": 2}
    assert sorted(storage.deleted) == ["a.pdf", "b.pdf"], "不该碰别人的对象"
    assert [r.id for r in repo.rows] == [3]
    assert repo.session.commits == 1


def test_clear_resumes_counts_only_really_deleted_objects(monkeypatch):
    repo = _FakeResumeRepo([_resume(1, 11, file_key="a.pdf"), _resume(2, 11, file_key="gone.pdf")])
    storage = _FakeStorage({"a.pdf"})  # 第二个已经没了
    monkeypatch.setattr(resume_service, "get_storage", lambda: storage)

    result = asyncio.run(resume_service.clear_resumes(repo, _User()))

    assert result == {"deleted": 2, "objects_deleted": 1}
    assert repo.rows == []


# ---------- upload：提交一定要早于派发解析 ----------

def test_upload_commits_before_dispatching_parse(monkeypatch):
    """解析任务另开 session 读简历行，而 inline 降级是 create_task ——
    它和请求收尾的 commit 是竞态的。若派发时还没提交，任务会读到"行不存在"
    并静默 return：状态永远停在 pending、时间线里也没有解析事件。
    """
    repo = _FakeResumeRepo([])
    storage = _FakeStorage(set())
    observed: dict[str, int] = {}

    async def fake_dispatch(task, impl, *args, **kwargs):
        observed["commits_at_dispatch"] = repo.session.commits
        observed["events_at_dispatch"] = len(repo.events)
        return "inline"

    monkeypatch.setattr(resume_service, "get_storage", lambda: storage)
    monkeypatch.setattr(d, "dispatch_or_inline", fake_dispatch)

    resume = asyncio.run(resume_service.upload(repo, _User(), "a.pdf", b"%PDF-1.4\n%%EOF"))

    assert observed["commits_at_dispatch"] >= 1, "派发解析前必须先提交简历行"
    assert observed["events_at_dispatch"] == 1, "uploaded 事件要和简历行一起提交"
    assert repo.events[0][2] == "uploaded"
    assert resume.version == 1 and resume.status == "pending"
    assert storage.put_keys and storage.put_keys[0].startswith("resumes/11/")


def test_upload_rejects_non_pdf(monkeypatch):
    repo = _FakeResumeRepo([])
    monkeypatch.setattr(resume_service, "get_storage", lambda: _FakeStorage(set()))

    with pytest.raises(ValidationError):
        asyncio.run(resume_service.upload(repo, _User(), "a.txt", b"not a pdf"))

    assert repo.rows == [] and repo.session.commits == 0


def test_upload_rejects_oversize(monkeypatch):
    repo = _FakeResumeRepo([])
    monkeypatch.setattr(resume_service, "get_storage", lambda: _FakeStorage(set()))

    too_big = b"%PDF-" + b"x" * (resume_service.MAX_SIZE + 1)
    with pytest.raises(ValidationError):
        asyncio.run(resume_service.upload(repo, _User(), "big.pdf", too_big))

    assert repo.rows == [], "超限文件不该落库"


# ---------- dispatch kwargs 只给 inline 实现 ----------

class _FakeTask:
    name = "fake_task"

    def __init__(self):
        self.args = None

    def delay(self, *args):
        self.args = args
        return None


def test_dispatch_kwargs_reach_inline_impl(monkeypatch):
    """broker 不可达 → 降级路径，kwargs 必须传进 impl（时间线要知道 celery/inline）。"""
    d._probe_cache = None
    monkeypatch.setattr(d.settings, "celery_broker_url", "redis://127.0.0.1:6399/1")

    seen: list[str] = []

    async def impl(resume_id: int, parse_mode: str = "celery") -> str:
        seen.append(parse_mode)
        return "ok"

    async def main() -> str:
        mode = await d.dispatch_or_inline(_FakeTask(), impl, 5, parse_mode="inline")
        await asyncio.sleep(0.05)
        return mode

    assert asyncio.run(main()) == "inline"
    assert seen == ["inline"]


def test_dispatch_ignores_kwargs_on_celery_path(monkeypatch):
    """memory broker 一定可达 → 走 Celery，只传 args，kwargs 不参与。"""
    d._probe_cache = None
    monkeypatch.setattr(d.settings, "celery_broker_url", "memory://")

    task = _FakeTask()

    async def impl(resume_id: int, parse_mode: str = "celery") -> str:
        return "ok"  # pragma: no cover - Celery 分支下不该被调用

    mode = asyncio.run(d.dispatch_or_inline(task, impl, 5, parse_mode="inline"))

    assert mode == "celery"
    assert task.args == (5,), "Celery 只能收到位置参数"
