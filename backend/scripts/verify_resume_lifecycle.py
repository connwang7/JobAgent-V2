"""端到端验证：简历删除（单个 / 清空）与操作时间线。

用**固定的临时探针账号**跑，避免动到真实账号的简历；账号已存在就直接登录，
所以反复运行不会再往库里堆新用户。

运行：PYTHONIOENCODING=utf-8 python -X utf8 scripts/verify_resume_lifecycle.py
"""
import pathlib
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
PROBE_EMAIL = "lifecycle_probe@example.com"
PROBE_OTHER = "lifecycle_probe_other@example.com"
PROBE_PWD = "Probe12345"
PDF = pathlib.Path(".storage/resumes/21/8dcb3119cb574f97be9de0317c47cedf.pdf")
if not PDF.exists():  # 兜底：随便找一个已存的对象
    PDF = next(pathlib.Path(".storage").rglob("*.pdf"))

ok_count = 0
fail_count = 0


def check(label: str, cond: bool, extra: str = "") -> None:
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  PASS  {label}")
    else:
        fail_count += 1
        print(f"  FAIL  {label} {extra}")


def login_or_register(c: httpx.Client, email: str, nickname: str) -> dict:
    """已存在就登录，不存在才注册 —— 让脚本可重复运行且不留新账号。"""
    r = c.post(f"{BASE}/auth/login", json={"email": email, "password": PROBE_PWD})
    if r.status_code != 200:
        r = c.post(f"{BASE}/auth/register",
                   json={"email": email, "password": PROBE_PWD, "nickname": nickname})
        assert r.status_code == 201, r.text
        r = c.post(f"{BASE}/auth/login", json={"email": email, "password": PROBE_PWD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def main() -> int:
    stamp = int(time.time())

    c = httpx.Client(timeout=60)
    h = login_or_register(c, PROBE_EMAIL, "时间线探针")
    me = c.get(f"{BASE}/me/profile", headers=h).json()["data"]
    uid = me["id"]
    # 上次运行若异常中断，可能残留数据；先清干净保证断言成立
    c.delete(f"{BASE}/resumes", headers=h)
    print(f"测试用户 id={uid} email={me['email']}（已清空历史残留）")

    print("\n[1] 上传第一份简历 → 解析 → 时间线")
    with PDF.open("rb") as f:
        r = c.post(f"{BASE}/resumes", headers=h,
                   files={"file": (f"probe_{stamp}.pdf", f, "application/pdf")})
    check("上传返回 201", r.status_code == 201, r.text[:200])
    r1 = r.json()["data"]
    check("版本号为 1", r1["version"] == 1, str(r1))
    check("初始状态 pending", r1["status"] == "pending", str(r1))

    # 无大模型 Key → 解析会失败；等它落到 failed（这正是我们要看的时间线终态）
    status = r1["status"]
    for _ in range(20):
        time.sleep(1)
        rows = c.get(f"{BASE}/resumes", headers=h).json()["data"]
        cur = next((x for x in rows if x["id"] == r1["id"]), None)
        if cur and cur["status"] in ("ready", "failed"):
            status = cur["status"]
            break
    print(f"      解析终态 = {status}")

    ev = c.get(f"{BASE}/resumes/{r1['id']}/events", headers=h)
    check("GET events 200", ev.status_code == 200, ev.text[:200])
    data = ev.json()["data"]
    names = [e["event"] for e in data["events"]]
    print(f"      事件序列 = {names}")
    check("含 uploaded", "uploaded" in names, str(names))
    check("含 parse_started", "parse_started" in names, str(names))
    check("含终态事件", ("parse_succeeded" in names) or ("parse_failed" in names), str(names))
    check("事件按时间升序（uploaded 在最前）", names[0] == "uploaded", str(names))
    started = next((e for e in data["events"] if e["event"] == "parse_started"), None)
    check("parse_started 标了解析模式", bool(started and "解析模式" in started["detail"]),
          str(started))
    up = next(e for e in data["events"] if e["event"] == "uploaded")
    check("uploaded 带版本/文件名/体积", "probe_" in up["detail"] and "v1" in up["detail"],
          up["detail"])
    check("时间线带 resume_id/version/status",
          data.get("resume_id") == r1["id"] and data.get("version") == 1, str(data)[:200])

    print("\n[2] 越权保护：别人不能读/删我的时间线与简历")
    h2 = login_or_register(c, PROBE_OTHER, "别人")
    check("他人读 events → 404",
          c.get(f"{BASE}/resumes/{r1['id']}/events", headers=h2).status_code == 404)
    check("他人删简历 → 404",
          c.delete(f"{BASE}/resumes/{r1['id']}", headers=h2).status_code == 404)
    check("未授权读 events → 401",
          c.get(f"{BASE}/resumes/{r1['id']}/events").status_code == 401)

    print("\n[3] 上传第二份 → 删除单个版本")
    with PDF.open("rb") as f:
        r = c.post(f"{BASE}/resumes", headers=h,
                   files={"file": (f"probe2_{stamp}.pdf", f, "application/pdf")})
    r2 = r.json()["data"]
    check("第二份版本号 2", r2["version"] == 2, str(r2))
    # 真实对象 key 在库里，用目录里的文件数变化来判断删没删掉
    dirp = pathlib.Path(".storage/resumes") / str(uid)
    before = sorted(p.name for p in dirp.glob("*.pdf")) if dirp.exists() else []
    check("目录里已有 2 个对象", len(before) == 2, str(before))

    d = c.delete(f"{BASE}/resumes/{r2['id']}", headers=h)
    check("DELETE 200", d.status_code == 200, d.text[:200])
    body = d.json()["data"]
    check("报告 object_deleted=True", body.get("object_deleted") is True, str(body))

    after = sorted(p.name for p in dirp.glob("*.pdf")) if dirp.exists() else []
    check("磁盘对象数 -1", len(after) == len(before) - 1, f"{before} -> {after}")

    rows = c.get(f"{BASE}/resumes", headers=h).json()["data"]
    check("列表只剩 1 条", len(rows) == 1, str([x["id"] for x in rows]))
    check("剩的是 v1", rows[0]["id"] == r1["id"], str(rows))
    check("被删版本 events → 404",
          c.get(f"{BASE}/resumes/{r2['id']}/events", headers=h).status_code == 404)
    check("重复删除 → 404", c.delete(f"{BASE}/resumes/{r2['id']}", headers=h).status_code == 404)
    # 时间线也要随之删掉（DB 层）
    other_ids = [x["id"] for x in c.get(f"{BASE}/resumes", headers=h2).json()["data"]]
    check("别人的列表不受影响（不含我的简历）",
          r1["id"] not in other_ids and r2["id"] not in other_ids, str(other_ids))

    print("\n[4] 一键清空")
    cl = c.delete(f"{BASE}/resumes", headers=h)
    check("DELETE /resumes 200", cl.status_code == 200, cl.text[:200])
    cb = cl.json()["data"]
    check("deleted=1", cb.get("deleted") == 1, str(cb))
    check("objects_deleted=1", cb.get("objects_deleted") == 1, str(cb))
    check("列表已空", c.get(f"{BASE}/resumes", headers=h).json()["data"] == [])
    leftover = list(dirp.glob("*.pdf")) if dirp.exists() else []
    check("磁盘对象已清空", leftover == [], str(leftover))
    check("空目录顺手清掉", not dirp.exists(), str(dirp))
    # 再清一次必须幂等
    cl2 = c.delete(f"{BASE}/resumes", headers=h)
    check("重复清空幂等（deleted=0）", cl2.json()["data"]["deleted"] == 0, cl2.text[:200])

    print(f"\n===== PASS {ok_count} / FAIL {fail_count} =====")
    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
