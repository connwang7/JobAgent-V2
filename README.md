# JobAgent-MultiAgent

> 基于 LangGraph 的多智能体求职助手系统 · **v2.0（重构进行中）**
>
> - v1（Streamlit 单文件 demo）已按重构方案**下线删除**；如需回看可从 git 历史恢复
>   （`git checkout <旧commit> -- agents.py app.py ...`），迁移映射见
>   [`docs/REFACTORING_PLAN.md`](./docs/REFACTORING_PLAN.md) 第 12 节。
> - v2 采用前后端分离：Next.js 前端 + FastAPI 后端 + MySQL/Redis/Qdrant/MinIO + Celery。

## 本地启动（推荐，无需 Docker）

### Windows / PowerShell（一键）

先**做一次**解除执行策略（当前用户生效，永久，之后就不用再带那一长串了）：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

之后就只需要：

```powershell
.\scripts\start-local.ps1                     # 后端 + 前端（前端走 next dev，带 HMR）
.\scripts\start-local.ps1 backend             # 只启后端
.\scripts\start-local.ps1 frontend            # 只启前端
.\scripts\start-local.ps1 frontend -Prod      # 只启前端，走生产构建（先 npm run build）
.\scripts\stop-local.ps1                      # 停止
```

> 不想改执行策略时，用完整形式：`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local.ps1`。
> `-NoProfile` 只是跳过 profile 加载（更快更干净），`Bypass` 是为了绕过"禁止运行本地脚本"的默认策略。
> 也可以双击 `scripts\start-local.bat`（内部已带 `-ExecutionPolicy Bypass`）。

服务以**独立进程**方式运行，关闭终端 / VSCode 不会停止它们。
日志统一落在 `logs/`：`logs\backend.log`、`logs\frontend.log`。

```powershell
Get-Content logs\backend.log -Wait     # 实时跟踪后端日志
```

> **前端起不来怎么办**：脚本现在会等待前端就绪并给出提示。若 `logs\frontend.log` 停在 `> next dev -p 3000`
> 之后不再输出（说明当前环境拦截了 dev 模式对 `.next` 的清理），改用生产模式即可：
>
> ```powershell
> cd frontend; npm run build
> cd ..; .\scripts\start-local.ps1 frontend -Prod
> ```


### 在 VSCode 里运行（推荐）

已配好 `.vscode/tasks.json`，打开项目后：

- `Ctrl+Shift+B` → 直接跑「启动全部（后端 + 前端）」
- 或 `Ctrl+Shift+P` → `Tasks: Run Task` → 选「只启动后端」/「只启动前端」/「停止服务」/「跟踪后端日志」…

> 注意：脚本自带的 `.sh` 版本只适用于 Git Bash / WSL，**PowerShell 里执行 `.sh` 不会有任何输出**。

### 手动启动（两个终端，等价）

```bash
# 终端 1 - 后端
cd backend
set PYTHONPATH=.            # PowerShell: $env:PYTHONPATH="."
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# 接口文档：http://127.0.0.1:8000/api/docs

# 终端 2 - 前端
cd frontend
npm install                 # 仅首次
npm run dev                 # http://localhost:3000
```

### 前置准备

所需外部服务只有 **MySQL 8.0**（业务库 + LangGraph checkpoint）。
Redis / Qdrant / MinIO **可选**，未启动时代码自动降级：

| 服务 | 缺失时的表现 |
|------|-------------|
| Redis | Celery 不可用 → 简历解析 / 求职信 docx 渲染**自动降级为进程内后台执行**（功能可用，只是不跨进程排队）；工具缓存与登录限流失效。升级路径由 `app/workers/dispatch.py` 的 TCP 预检决定，**不会拖慢请求**（见「已知坑」） |
| Qdrant | 「人岗匹配」与长期记忆向量召回不可用；对话、岗位搜索、求职信不受影响 |
| MinIO | 默认 `STORAGE_BACKEND=local`，文件落 `backend/.storage`，无需对象存储 |

> 没配大模型 Key 时：简历能上传成功，但**解析会失败**并把原因写进 `resume.error`。
> 在「设置 → 大模型接入」填好 Key 后，到「简历中心」点「重新解析」即可，不用重传文件。

```bash
# 0) 准备数据库（仅一次；MySQL 8.0 需已启动）
#    必须用 utf8mb4_0900_ai_ci！原因见下方「已知坑」
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS jobagent CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"

# 1) 后端依赖
cd backend
cp .env.example .env               # LLM_API_KEY 可留空，改在前端「系统设置」里填
pip install -e .                   # 或 poetry/uv install

# 2) 数据库迁移（表结构变更时）
python -m alembic.config upgrade head
```

`DEBUG=true` 时后端启动会自动建表（生产请改用 `alembic upgrade head`）。

### 已知坑（都已修复，换机器/换库时注意）

| 现象 | 原因 | 处理 |
|------|------|------|
| 对话报 `run_failed: (1267, "Illegal mix of collations ...")` | langgraph-checkpoint-mysql 的 SQL 里 `json_table(... VARCHAR(150) CHARACTER SET utf8mb4)` 没写 COLLATE，落在 MySQL 8 默认的 `utf8mb4_0900_ai_ci`；若建库时用了 `utf8mb4_unicode_ci` 就冲突 | 建库用 `utf8mb4_0900_ai_ci`；已有库可 `ALTER DATABASE`/`ALTER TABLE ... CONVERT TO`（外键需先 `SET FOREIGN_KEY_CHECKS=0`） |
| 对话报 `TypeError: 'str' object is not callable`（在 `aput` / checkpoint 写入） | PyMySQL ≥ 1.2 把 `converters.escape_bytes_prefixed` 换成了哨兵字符串，aiomysql 0.3.x 仍在 import 它 | `pyproject.toml` 锁 `PyMySQL>=1.1,<1.2`；`app/core/_compat.py` 另有运行时兜底 |
| 前端「深度思考 / 联网搜索」点了没反应 | 三个独立根因，**都已修复**：① `langchain_openai` 会丢弃非标准的 `reasoning_content`，思考过程根本到不了前端；② 没配 Serper Key，Planner 却按"可用"处理，于是静默无效（开关点亮但什么都不发生）；③ `start-local.ps1` 起的 uvicorn 没有 `--reload`，改了 `backend/` 代码不重启不生效 | ① 用 `ChatOpenAIWithReasoning`（`agents/llm/model_router.py`）捞回推理字段，**不要改回裸 `ChatOpenAI`**；② 服务层显式算 `web_search_available` 并写进 context，缺失时节点直接给出"填入 Serper Key"的提示；③ 改完后端代码重启：`.\scripts\stop-local.ps1 -Ports 8000` 再 `.\scripts\start-local.ps1 backend` |
| 结构化输出抛 `TypeError: list[...] is not a module, class, method, or function` | `with_structured_output(list[X])` 的裸泛型被 `langchain_openai._convert_to_openai_response_format` 当成"函数"，走 `typing.get_type_hints(list[...])` 而崩 | 用具名 `BaseModel` 包住列表（见 `state.JobRanking`）。**永远不要给 `with_structured_output` 传裸 `list[X]` / `dict[...]`**；回归用例见 `tests/test_structured_output.py` |
| 某个功能"配置明明在别的文件里/代码里写了却没用" | `app/core/config.py` 的 `env_file=".env"` 按**当前工作目录**解析。仓库根目录若存在残留的 `.env`，从这里启动就会读它而不是 `backend/.env`，表现为 Serper/LLM 等配置凭空消失 | 配置只放 `backend/.env`（Docker 也走 `env_file: ../backend/.env`）；启动前先 `cd backend`。**仓库根目录不要留 `.env`** |
| 对话历史时间比实际早 8 小时（刚建的会话显示「8 小时前」） | 后端存的是 **naive UTC**，`isoformat()` 不带 `Z`/偏移；浏览器把 `2026-09-25T13:53` 当**本地时间**解析 | 前端统一走 `frontend/lib/format.ts` 的 `parseServerTime()`（无时区后缀时补 `Z`）。**新增页面不要直接用 `new Date(isoString)`**，一律用 `formatDateTime()` / `relativeTime()` |
| 回答是一次性整段蹦出来、没有逐字流式 | `langchain_openai.ChatOpenAI` 默认 `streaming=False`，即使 `astream` 也只会拿到一个完整 chunk | 已在 `role_llm(role, context, streaming=True)` 上按节点开启（仅 `synthesizer` 与 `ChatBot` 这两个会输出给用户的节点）。`streaming` 是 `lru_cache` 键的一部分，加开关时别忘了传进 `_cached_llm` |
| 深色模式第一帧先白后黑 | `<html>` 上的 `dark` class 在 hydration 后才被打上 | `app/layout.tsx` 的 `<head>` 里有一段内联脚本（`lib/theme.ts` 的 `THEME_BOOT_SCRIPT`）在样式生效前先落 class；`<html>` 加了 `suppressHydrationWarning` |
| 上传简历一直转圈，**同时全站接口一起卡住** | 没起 Redis，`parse_resume_task.delay()` 连不上 broker 时会按 kombu 默认策略反复重连 —— 实测 **~108 秒**才抛错；而它是**同步阻塞**调用、又发生在 `async def` 端点里，于是把整个事件循环冻住了（连带把已调度的 inline 解析任务一起饿死，简历长期停在「解析中」） | `app/workers/dispatch.py` 改成 **async + TCP 预检**：先 `broker_reachable()`（0.4s、结果缓存 5s），不可达就直接 inline 降级且**绝不调用 `delay()`**；真正 publish 时用 `asyncio.to_thread` 丢到线程。`celery_app.conf` 里 `task_publish_retry=False` + `broker_connection_max_retries=0` 做双保险。实测 108.4s → **1.16s**（二次上传 0.03s）。回归测试见 `tests/test_dispatch.py` |
| 简历永远停在「解析中」 | 进程内降级任务（inline）在服务重启 / 事件循环关停时被取消，DB 里残留 `pending/parsing` | 启动时 `app/workers/reconcile.py` 把超过 10 分钟的 `pending/parsing` 标成 `failed` 并写明原因（broker 可达时跳过，避免误伤真正的 Celery 队列）；前端在「简历中心」显示失败原因 + 提供「重新解析」 |
| 解析失败但看不出原因 | 首次上传时还没配大模型 Key，任务在后台失败，请求早就返回 201 了 | 失败原因落在 `resume.error`，前端上传后 6 秒回查一次并弹出提示；配好 Key 后在「简历中心」点 `重新解析`（`POST /resumes/{id}/reparse`）即可，不用重传文件 |
| Alembic `downgrade` 报 `(1553, "Cannot drop index 'ix_...': needed in a foreign key constraint")` | 先 `drop_index` 再 `drop_table`；MySQL 要求外键列上始终保留一个索引，先删索引就把外键的索引抽掉了 | 要删整张表就直接 `op.drop_table(...)`，索引随表一起消失（见 `0003_resume_events.py`）。另外 MySQL DDL 非事务，写迁移时注意失败后可能停在中间态 |
| 新加的表 `create_all` 建了、但老库没有 | `Base.metadata.create_all` **只建缺失的表，不会 ALTER 已存在的表**，也不会改 `alembic_version` | 用 `create_all` 兜住新库的同时，**必须**写一条 Alembic 迁移给老库（`0002` / `0003` 都是这个原因），否则老库上 `alembic upgrade head` 会与 `create_all` 抢着建表 |
| `next build` 报 `uncaughtException [Error: EPERM: operation not permitted, open '...\.next\trace']` | Next 的构建 worker 打不开 `.next/trace`。该错误**没有调用栈**（说明来自子进程），改目录名 / 反复重试 / 关沙箱都无效；`next start` 与产物无关 | `.next/trace` 只是性能追踪产物，用 `frontend/scripts/next-no-trace.cjs` 把指向它的 `createWriteStream` 换成空流。**必须走 `NODE_OPTIONS`**（worker 是子进程，`node -r` 只作用于主进程）。已封装：`cd frontend && sh scripts/build.sh` |
| 上传后简历一直停在「排队中」、时间线里只有 `uploaded` | `upload()` 里派发解析任务时**事务还没提交**；inline 降级是 `loop.create_task`，和请求收尾的 `commit` 是竞态的。任务跑在前面就会读到"这行不存在"，直接 `return` 什么都不写 | `upload()` 在派发**之前**显式 `commit()`（`expire_on_commit=False`，提交后属性仍可读，不影响响应组装）。回归测试 `test_upload_commits_before_dispatching_parse` |

> 排查这类"对话没反应"的问题：先看 `logs/backend.log` 里的 `run_failed`（现在会带完整 traceback），
> 再到左下角「设置 → 大模型接入 → 测试连接」确认 Key / Base URL / 模型名。

## 前端交互（会话工作台）

- **对话历史**：左侧栏「对话历史」列出全部会话（标题 + 相对时间），可点击切换、悬停删除。
  会话状态放在 `frontend/lib/store.ts`（zustand），因为列表在 `layout.tsx` 而消息流在 `page.tsx`。
  **新建会话只切到"草稿态"、不立刻建库**，首次发送时才创建 —— 避免历史里堆积空的「新会话」。
- **参考简历**：输入框左侧的回形针按钮可上传 PDF 简历（≤10MB），上传后作为本会话的参考简历，
  输入框上方会显示 `参考简历 v3 · xxx.pdf`；上传期间显示"已等待 n 秒"。会话生成时后端优先用
  `session.resume_id`，没有则用该用户最新的一份简历。解析失败时会弹出原因，并指向
  「简历中心 → 重新解析」。
- **请求超时**：`lib/api.ts` 的 `request()` 默认 30s 超时（上传 120s），超时抛 `HTTP-TIMEOUT`。
  **所有网络请求都必须走它**，否则后端一旦被阻塞，前端就会无限转圈、没有任何提示。
- **流式事件**：后端 `POST /sessions/{id}/chat` 走 SSE，事件协议为
  `status → plan → agent_start / tool_call → thinking / thinking_done → token → [critic] → interrupt | final | error`。
- **真流式输出**：`synthesizer` / `ChatBot` 节点用 `streaming=True` 的模型 + `astream`，
  前端逐 token 渲染并带渐变光标。**首个 token 到达前**显示
  「模型正在思考」（流动渐变文字 + 阶段名 + 已等待秒数），不是空白等待。
- **深度思考**：输入框左侧「深度思考」开关会带上 `deep_thinking: true`，后端把
  Worker / Synthesizer 切到 `thinking` 角色（默认 `deepseek-reasoner`），模型返回的
  `reasoning_content` 以 `thinking` 事件先行下发，前端渲染成可折叠的
  「模型正在思考（n 秒）」面板，正式回答开始时自动折叠为「已深度思考（用时 n 秒）」。
- **消息操作**：每条回答下方有「复制」；最后一条回答额外有「重新生成」
  （丢掉该条回答、用上一条提问重跑，不会重复插入用户消息）。
- **联网搜索**：`web_search: true` 会让 Planner 强制插入 `WebSearcher` 步骤。
- **可中止**：生成中发送按钮变为停止按钮，走 `AbortController`，已输出的内容会保留为消息。
- **执行可视化**：主区顶部是执行计划（进度条 + 每步 done/running/pending），右侧栏（≥1280px 显示）
  是工具调用轨迹。
- **图标**：全部为内联 SVG（`frontend/components/icons.tsx`），不使用 emoji 图片资源；
  站点图标由 `frontend/app/icon.svg` 提供。
- **字号**：正文基准 16px，辅助信息**不低于 12.5px**（`.md` 用 16px / 行高 1.75）。
  想整体缩放时，改 `frontend/tailwind.config.js` 的令牌或 `app/globals.css` 里的 `.md` 基准即可。
  改完之后用 `grep -rnoE "text-\[(0|[1-9]|1[01])(\.[0-9]+)?px\]" app components` 自查（应为空）。
- 两个开关的选择会记在 `localStorage`（`jobagent.deepThinking` / `jobagent.webSearch`）。

### 前端构建与启动

```bash
cd frontend && npm run build     # 本机若报 EPERM（见「已知坑」）改用：sh scripts/build.sh
cd frontend && npm start         # 等价于 next start -H 127.0.0.1 -p 3000
```

> `next start` **必须**绑 `127.0.0.1`（`npm start` 已带 `-p 3000`，若手敲要加 `-H 127.0.0.1`），
> 绑 `0.0.0.0` 在这个环境里会直接 exit 1。

## 简历中心（版本 / 删除 / 操作时间线）

每用户保留多版本（`resumes.version` 递增），列表按版本倒序。每行有四个动作：
`画像`、`重新解析`（非 `ready` 时出现）、`操作历史`、`删除`。

### 删除（可单条，也可一键清空）

| 入口 | 接口 | 行为 |
|------|------|------|
| 行内「删除」图标 | `DELETE /resumes/{id}` | 删对象存储文件 → 删该版本时间线 → 删主记录 |
| 标题栏「清空全部」 | `DELETE /resumes` | 删该用户全部版本的上述三样 |

两个入口都是**两步确认**（先展开就地的确认条，再点「确认删除 / 确认清空」），
清空那条会写明「将删除 N 个版本」以及"会话和求职信会保留、但不再关联简历"。

几个刻意设计：

- **先删存储再删库**，且存储删失败**不阻止**记录删除。若反过来，一旦对象损坏或权限异常，
  用户就会陷入"怎么点都删不掉"的死角；残留的孤儿对象不影响功能，只占一点空间。
  返回值里带 `object_deleted`，前端据此显示"文件此前已不存在"。
- **不做级联误伤**：`match_results.resume_id` 是 `ON DELETE CASCADE`（匹配缓存本就该随简历走），
  但 `sessions.resume_id` 与 `cover_letters.resume_id` 是 `ON DELETE SET NULL` ——
  删简历不该把用户的会话和已生成的求职信一起删掉，只断开引用。
- 归属校验走 `get_profile()`，别人的简历返回 404（不是 403，避免探测资源是否存在）。

### 操作历史（版本操作时间线）

`GET /resumes/{id}/events`，前端点「操作历史」就地展开（同一时刻只开一行）。
事件是**纯追加**的 `resume_events` 表，比在 `resumes` 上记 `started_at/finished_at`
更合适 —— 一份简历可以「重新解析」多次，字段只能保留最后一次，无法回放。

| event | 写入位置 | detail 内容 |
|-------|----------|-------------|
| `uploaded` | `services/resume.upload()` | `v3 · 秋招简历.pdf · 303 KB` |
| `reparse_requested` | `services/resume.reparse()` | 版本号 |
| `parse_started` | `workers/tasks/parse_resume.run_parse_resume()` | 解析模式 `celery` / `inline` |
| `parse_succeeded` | 同上 | 技能数 · 经历年数 · 耗时 |
| `parse_failed` | 同上 | 异常类型 + 错误原文（≤300 字）+ 耗时 |

- 时间线里的时间是**后端 naive UTC**，前端一律用 `formatDateTime()` 渲染（见「已知坑」的时区行）。
- **老数据回填**：`0003_resume_events.py` 里有一段纯 Python 回填，给迁移前就存在的简历补
  `uploaded`（时间/版本/文件名/体积来自本行，确凿已知）以及终态行，detail 都带「历史记录」标注，
  不伪造耗时。没有简历的新库该段是 no-op。
- 列表里只要还有 `pending`/`parsing` 的版本，前端每 5s 轮询一次；
  时间线开着时一并刷新，用户能实时看到「开始解析 → 解析成功」。

### 验证

`backend/scripts/verify_resume_lifecycle.py` 用**临时新用户**跑完整链路（不动真实账号数据）：
上传 → 等解析终态 → 读时间线 → 越权读写（他人 404 / 未授权 401）→ 删单条（核对磁盘对象少一个、
被删版本 events 404、重复删除 404）→ 一键清空（核对 `deleted`/`objects_deleted`、磁盘目录被清、
重复清空幂等）。

```bash
cd backend && PYTHONIOENCODING=utf-8 python -X utf8 scripts/verify_resume_lifecycle.py
# 连跑 3 次结果：PASS 31 / FAIL 0
```

## 统一设置页与主题

侧栏**底部用户卡片**是设置入口（头像 + 昵称 + 齿轮 + 箭头），点击进入 `/settings`；
`系统设置` 已从主导航移除。设置页左侧分栏，四块内容：

| 分栏 | 内容 |
|------|------|
| 账号信息 | 头像 / 昵称（`PUT /me/profile`）、邮箱、注册时间、数据概览（会话·简历·求职信·长期记忆计数）、修改密码（`POST /me/password`，校验旧密码 + 新密码≥8 位 + 不能与原密码相同） |
| 外观 | 白天 / 夜晚 / 跟随系统，三张预览卡；选择存 `localStorage`（`ja-theme`） |
| 大模型接入 | 服务商预设一键填充、API Key、Base URL、测试连接、模型分层路由、Serper / FireCrawl 密钥 |
| 求职偏好 | 城市 / 行业 / 薪资 / 工作方式，同时沉淀为长期记忆 |

### 深色模式怎么实现的

**不给每个元素写 `dark:`**，而是把「会反转的颜色」抽成 CSS 变量，在 `app/globals.css` 里给两套值：

```css
:root { --c-surface-0: 255 255 255; --c-ink-800: 30 41 59;  --c-tint: 238 242 255; }
.dark { --c-surface-0: 24 30 41;    --c-ink-800: 226 232 240; --c-tint: 41 47 84; }
```

`tailwind.config.js` 里让 `surface.* / ink.* / tint.*` 指向这些变量
（`rgb(var(--c-x) / <alpha-value>)`），所以 `<html class="dark">` 一变，整套配色就翻转。

约定：

- **只用** `bg-surface-0`（卡片）/ `bg-surface-50`（页底）/ `bg-surface-100`（次级块）、
  `text-ink-900…300`、`bg-tint` + `text-tint-fg` + `border-tint-line`。不要写 `bg-white`、`bg-slate-*`、`text-gray-*`。
- `brand.*` / `accent.*` 是**固定值**（渐变、实心按钮、发光点昼夜通用）；`night.*` 是**永远偏暗**的
  （代码块、登录页左栏、用户头像渐变）——需要"永远深色"时用 `night`，不要用 `ink-900`。
- 状态色（emerald / rose / amber）保留色相，只在需要处补 `dark:` 变体（浅底→同色系深底、深字→浅字）。
- 主题切换入口有两处：设置页「外观」分栏，以及侧栏底部用户卡片上方的快捷三段开关。
  逻辑在 `frontend/lib/theme.ts`（`initTheme` / `setThemeMode` / `subscribeTheme`，`system` 模式监听 `matchMedia`）。

## Docker 启动（可选，一键起全栈）

```bash
docker compose -f docker/docker-compose.dev.yml up -d   # 仅基础设施
docker compose -f docker/docker-compose.yml up --build  # 全栈含 Nginx
```

## v2 工程结构

```
backend/app/
├── api/v1/routers/     auth session resume job letter run me（只做校验/鉴权/响应组装）
├── core/               config db security logging errors sse storage cache injection_guard
├── models/             SQLAlchemy ORM（users/resumes/resume_events/sessions/messages/agent_runs/
│                       agent_events/job_postings/match_results/cover_letters/user_memories）
├── repositories/       数据访问封装（唯一允许写 session 的地方）
├── services/           auth session resume job letter memory orchestrator
├── agents/
│   ├── graph/          planner executor workers synthesizer critic hitl finish builder state
│   ├── subgraphs/      deep_research（搜索→评估→补搜→综合，≤3 轮，强制引用来源）
│   ├── tools/          adapters + web_search/scraper/job_search/resume_extractor/render_docx
│   ├── prompts/        按 Agent 拆分
│   ├── memory/         user_memories + Qdrant 向量召回
│   └── llm/            model_router（角色→模型分层路由）
├── matching/           embedding retriever scorer（可解释匹配评分）
└── workers/            celery_app + dispatch（TCP 预检 + inline 降级）+ reconcile（残留状态兜底）
                        + tasks（parse_resume/embed_jobs/deep_research/render_letter）
├── alembic/versions/   0001_initial / 0002_user_tool_keys / 0003_resume_events（含老数据回填）
└── scripts/            verify_resume_lifecycle.py（删除 + 时间线端到端自检）
```

```
frontend/
├── app/
│   ├── layout.tsx        根布局：<head> 内联主题防闪烁脚本 + Viewport
│   ├── icon.svg          站点图标
│   ├── globals.css       设计令牌（:root / .dark 两套 CSS 变量）+ 组件类 + .md 排版
│   ├── auth/page.tsx     登录 / 注册
│   └── (dashboard)/
│       ├── layout.tsx    侧栏：主导航 + 对话历史 + 底部用户卡片（设置入口）+ 主题快捷开关
│       ├── page.tsx      会话工作台：消息流 / 计划 / 执行轨迹 / 输入区 / 思考态 / 重新生成
│       ├── resume/page.tsx    简历中心：上传 / 版本列表 / 删除（单条 + 一键清空）/ 操作时间线
│       ├── jobs letters
│       └── settings/page.tsx  统一设置页（账号 / 外观 / 大模型 / 偏好）
├── components/
│   ├── icons.tsx         内联 SVG 图标集 + Logo + Agent 名→图标映射
│   ├── thinking-block.tsx  可折叠思考过程（计时 / 自动折叠）
│   ├── plan-view.tsx tool-card.tsx confirm-card.tsx page-header.tsx
├── lib/
│   ├── api.ts            接口封装（统一 envelope 解包 + 401 跳登录）
│   ├── sse.ts            SSE 客户端（status/plan/agent_start/tool_call/thinking/token/...）
│   ├── store.ts          zustand 会话状态（历史列表 ↔ 消息流共享）
│   ├── theme.ts          白天 / 夜晚 / 跟随系统 + 防闪烁引导脚本
│   ├── format.ts         时间格式化（parseServerTime 补 Z / relativeTime / formatDateTime）
│   └── auth.ts           token 存取
└── scripts/
    ├── build.sh             生产构建（next build + 屏蔽 .next/trace，见「已知坑」）
    └── next-no-trace.cjs    把 .next/trace 的 createWriteStream 换成空流
```

## v1 → v2 关键变化

| 维度 | v1 | v2 |
|------|----|----|
| 前端 | Streamlit 单体 | Next.js 14 + Tailwind，SSE 流式，执行过程可视化 |
| 路由 | 关键词硬编码 + 自由文本 + 关键词兜底 | Planner 结构化输出任务 DAG（`Plan.steps` + `depends_on`） |
| 协作 | `needs_followup` 单槽位，扫描消息历史找 `msg.name` | 黑板模式：Agent 只读写自己字段，直接读 artifact |
| 并行 | 串行 | LangGraph `Send` 并行超步（无依赖步骤同时执行） |
| 质量 | 开环生成 | Critic 结构化评分 + 修订闭环（≤2 次），与生成器异模型 |
| 不可逆动作 | 直接落盘 | HITL `interrupt()` 确认后才渲染 docx |
| 状态 | 每次全量重放消息 | MySQL checkpointer 持久化，会话级断点续跑 |
| 岗位数据 | 搜索结果丢弃 | 先落库 `job_postings`（按 url 去重），再返回 |
| 匹配 | LLM 看着猜 | BGE-M3 向量召回 + 结构化可解释评分（技能覆盖/差距/经验） |
| 密钥 | 明文存 `temp/app_config.json` | JWT 双 token + AES-GCM 加密用户级 Key |
| 抓取内容 | 直接入 prompt | `<untrusted_web_content>` 隔离 + 系统提示声明 |
| 可观测性 | print + callback | `agent_events` 落库 + structlog + Langfuse 预留 |

## 旧模块迁移映射

见 `docs/REFACTORING_PLAN.md` 第 12 节。其中 `search.py`（LinkedIn 死代码）已确定删除，
`chains.py` / `members.py` / `custom_callback_handler.py` 已被 v2 结构化编排取代。

## 测试

```bash
cd backend && pytest -q     # 37 passed
```

单测不依赖 MySQL / Redis / MinIO（`tests/conftest.py` 里落到 SQLite + 本地存储），
只覆盖纯逻辑与不变量：

| 文件 | 覆盖 |
|------|------|
| `test_dispatch.py` | 任务分发的三条不变量：broker 不可达必须**快速**返回、**绝不**调 `delay()`、降级任务真的被调度执行 |
| `test_resume_lifecycle.py` | 删除单条（对象 + 时间线 + 记录一起清、存储删失败不阻塞、空 key 不碰存储、越权 404）、一键清空（只动自己的、`objects_deleted` 只算真删掉的、幂等）、上传校验（非 PDF / 超 10MB 不落库）、**派发解析早于提交的竞态**、`human_size`、`dispatch` 的 kwargs 只给 inline 实现 |
| `test_security.py` / `test_planner.py` / `test_scorer.py` / `test_graph_compile.py` | 加密、Planner 解析、匹配打分、图编译 |

数据库/接口层的行为用 `scripts/verify_resume_lifecycle.py`（真起服务、真连 MySQL、真落盘）
做端到端自检，连跑 3 次均 **PASS 31 / FAIL 0**，见上文「简历中心 → 验证」。
