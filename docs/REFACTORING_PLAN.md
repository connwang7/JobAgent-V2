# JobAgent-MultiAgent v2.0 整体重构方案

> 版本：v1.0（方案设计稿）
> 范围：前后端分离架构、MySQL 数据库、多智能体核心重构、RAG 匹配引擎、可观测性与部署
> 说明：本文档只定义目标架构、模块划分与各模块技术栈，不涉及工期与开发排期

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [总体架构](#2-总体架构)
3. [前端设计](#3-前端设计)
4. [后端设计（FastAPI）](#4-后端设计fastapi)
5. [数据库设计（MySQL）](#5-数据库设计mysql)
6. [多智能体核心重构](#6-多智能体核心重构)
7. [RAG 人岗匹配引擎](#7-rag-人岗匹配引擎)
8. [工具层重构](#8-工具层重构)
9. [可观测性与评估](#9-可观测性与评估)
10. [部署架构](#10-部署架构)
11. [工程目录结构](#11-工程目录结构)
12. [旧模块迁移映射](#12-旧模块迁移映射)

---

## 1. 背景与目标

### 1.1 现状问题（v1 demo 级实现的技术债）

| 问题 | 位置 | 影响 |
|------|------|------|
| 路由靠硬编码关键词 + 自由文本 LLM 输出 + 关键词兜底，`RouteSchema` 已定义但未使用 | `agents.py supervisor_node` | 路由误判率高，复合任务识别写死 |
| Agent 协作靠 `needs_followup` 单槽位 + 扫描消息历史找 `msg.name` | `agents.py` | 只支持两步链，上下文传递脆弱、token 浪费 |
| 无图状态持久化，每次 invoke 全量重放消息 | `app.py execute_chat_conversation` | 上下文随对话增长爆炸（`recursion_limit=15` 掩盖） |
| 无流式输出，`graph.invoke` 阻塞式执行 | `app.py` | 用户长时间面对 spinner |
| 单文件单体（Streamlit 前后端耦合），无用户体系、无数据沉淀 | 全局 | 无法产品化、无法多用户 |
| `search.py` 为 LinkedIn 遗留死代码，含未导入的 `Linkededin`、`sync_to_async` | `search.py` | 不可调用的坏死代码 |
| 求职信等生成物直接落盘，无版本、无确认环节 | `tools.py` | 生成物不可管理、不可回溯 |
| API Key 明文存 `temp/app_config.json`，网页抓取内容无隔离直接入 prompt | `app.py` / `tools.py` | 安全隐患 |
| 无测试、无评估、无指标 | 全局 | 质量不可度量 |

### 1.2 重构目标

1. **产品化**：从单用户本地 demo 演进为多用户、可部署、可运营的 Web 服务
2. **架构现代化**：前后端分离（Next.js + FastAPI），RESTful API + SSE 流式协议
3. **数据资产化**：简历画像、岗位库、匹配记录、求职信版本、用户记忆全部入库（MySQL）
4. **智能体升级**：关键词路由 → 结构化 Planner 动态任务 DAG；串行执行 → 并行编排；开环生成 → Critic 反思闭环；新增 HITL 确认
5. **匹配可信化**：从"LLM 看着猜"升级为 RAG 向量检索 + 结构化匹配评分
6. **可运营**：全链路追踪、执行轨迹落库、评估体系

### 1.3 非目标（本轮明确不做）

- 不做招聘平台官方 API 对接的深度爬虫矩阵（工具层预留适配器扩展点）
- 不做移动端
- 不做多租户 SaaS 计费体系（保留单实例多用户）

---

## 2. 总体架构

### 2.1 架构图

```
┌────────────────────────────────────────────────────────────────┐
│                     前端 Next.js (SPA/SSR)                      │
│   会话工作台 │ 简历中心 │ 岗位中心 │ 求职信管理 │ 系统设置        │
└───────────────────────────┬────────────────────────────────────┘
                            │ HTTPS (REST + SSE)
┌───────────────────────────▼────────────────────────────────────┐
│                     Nginx 反向代理 / TLS 终结                    │
└───────────────────────────┬────────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────────┐
│                      FastAPI 后端 (ASGI)                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ API 层  /api/v1  (routers: auth/session/resume/job/...)   │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ 服务层  AuthService / SessionService / ResumeService /    │  │
│  │         JobService / MatchingService / LetterService /    │  │
│  │         MemoryService / OrchestratorService               │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ 智能体层 (LangGraph)                                       │  │
│  │   Planner → Executor(并行 fan-out) → Critic → HITL → Fin  │  │
│  │   ├ Deep Research 子图 (WebResearcher)                    │  │
│  │   ├ 模型路由 ModelRouter (分层多模型)                       │  │
│  │   ├ 记忆系统 (checkpoint + 长期记忆)                        │  │
│  │   └ 工具层 ToolRegistry (搜索/抓取/文档生成 + 缓存 + 防护)   │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ 数据访问层  SQLAlchemy 2.0 async + Alembic                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────┬──────────────────┬───────────────────┬─────────────────┘
       │                  │                   │
┌──────▼──────┐   ┌───────▼───────┐   ┌───────▼────────┐
│  MySQL 8.0  │   │   Redis 7     │   │   Qdrant       │
│  业务主库 +  │   │ 缓存/限流/     │   │ 向量库         │
│  checkpoint │   │ Celery broker │   │ (JD/记忆向量)   │
└─────────────┘   └───────┬───────┘   └────────────────┘
                          │
                  ┌───────▼───────┐    ┌────────────────┐
                  │ Celery Worker │    │ MinIO (S3)     │
                  │ 异步任务(抓取/ │    │ 简历PDF/求职信  │
                  │ embedding/研究)│    │ 文件存储        │
                  └───────────────┘    └────────────────┘
```

### 2.2 技术栈总览

| 层级 | 技术 | 选型理由 | 备选 |
|------|------|---------|------|
| 前端框架 | Next.js 14+ (App Router) + TypeScript | 流式 UI 生态最好（React Server Components + SSE），SSR/SEO 友好，AI 产品事实标准 | Vue 3 + Nuxt |
| UI 组件 | Tailwind CSS + shadcn/ui | 定制性强、无重型组件库依赖 | Ant Design |
| 前端状态/数据 | Zustand + TanStack Query | 轻量状态 + 服务端数据缓存 | Redux Toolkit |
| 后端框架 | FastAPI + Uvicorn | 原生 async、Pydantic v2 校验、SSE/OpenAPI 开箱即用 | Litestar |
| ORM | SQLAlchemy 2.0 (async) + asyncmy 驱动 | 异步成熟、Alembic 迁移配套 | Tortoise ORM |
| 数据库 | MySQL 8.0 (InnoDB, utf8mb4) | 指定选型；JSON 类型 + 索引能力满足结构化+半结构化混合存储 | PostgreSQL |
| 缓存/消息 | Redis 7 | 工具结果缓存、API 限流、Celery broker | Valkey |
| 任务队列 | Celery | 深度研究、批量 embedding、网页抓取等长任务异步化 | ARQ / Dramatiq |
| 智能体编排 | LangGraph + langgraph-checkpoint-mysql | 图编排 + `Send` 并行 + `interrupt` HITL；官方 MySQL checkpointer 与主库统一 | 自研编排 |
| 向量库 | Qdrant | 部署简单、payload 过滤强、性能好 | Milvus / pgvector |
| Embedding | BGE-M3（自托管，TEI 部署）；备选 DashScope text-embedding-v3 | 中文效果好，自托管零调用成本，支持稠密+稀疏混合检索 | bce-embedding |
| LLM 接入 | LiteLLM 统一网关（可选）+ OpenAI 兼容协议 | 一套代码路由 Qwen/DeepSeek/GPT，按角色分层选模型 | 直连各厂商 SDK |
| 对象存储 | MinIO (S3 协议) | 简历 PDF、求职信 docx 统一存储，生产可换云 OSS | 云厂商 OSS |
| 认证 | JWT (PyJWT) + bcrypt，access/refresh 双 token | 无状态、前后端分离标准方案 | Session + Redis |
| 追踪观测 | Langfuse（自托管）+ structlog + Prometheus/Grafana + Sentry | Langfuse 开源可自托管，替代 LangSmith，trace+eval 一体 | LangSmith（SaaS） |
| 测试评估 | pytest + pytest-asyncio + RAGAS | 单测 + RAG 质量评估 | deepeval |
| 部署 | Docker Compose（开发/单机）/ K8s（扩展）+ Nginx | 容器化一致环境 | — |

---

## 3. 前端设计

### 3.1 页面模块

| 页面 | 功能要点 |
|------|---------|
| `/auth` 登录注册 | 邮箱+密码；JWT 管理（access 15min / refresh 7d） |
| `/` 工作台（会话） | 左侧会话列表；主区聊天流。**核心亮点：Agent 执行过程可视化**——实时展示 Planner 生成的任务 DAG、各节点状态（pending/running/done）、工具调用卡片、并行进度 |
| `/resume` 简历中心 | 上传 PDF、版本管理、结构化画像卡片（技能/经历/成就），画像来自后端解析入库的结构化 JSON |
| `/jobs` 岗位中心 | 搜索结果列表、**人岗匹配页**：匹配分、技能覆盖雷达图、差距清单 |
| `/letters` 求职信管理 | 草稿列表、Critic 评分展示、HITL 确认流转（待确认 → 已确认 → 已下载）、版本对比 |
| `/settings` 设置 | 个人模型偏好、API Key 管理（加密存储）、求职偏好（城市/行业/薪资）沉淀为长期记忆 |

### 3.2 流式交互协议（SSE）

会话对话统一走 `POST /api/v1/sessions/{id}/chat`，响应为 `text/event-stream`，事件定义：

| event | data 结构 | 说明 |
|-------|----------|------|
| `plan` | `{steps: [{id, agent, desc, depends_on}]}` | Planner 产出的任务 DAG，前端渲染执行视图 |
| `agent_start` | `{run_id, agent}` | 某节点开始 |
| `tool_call` | `{agent, tool, args_digest}` | 工具调用（脱敏参数摘要） |
| `token` | `{content}` | 最终答案的增量 token |
| `interrupt` | `{interrupt_id, type, payload}` | HITL 中断，如求职信确认；前端弹确认卡 |
| `final` | `{message_id, refs}` | 结束，携带生成物引用（岗位列表 id、求职信 id） |
| `error` | `{code, message}` | 异常 |

HITL 确认后前端调 `POST /api/v1/runs/{run_id}/approve`，图从 checkpoint 恢复继续执行。

Markdown 渲染用 react-markdown + remark-gfm（表格）；职业路径可视化用 ECharts。

---

## 4. 后端设计（FastAPI）

### 4.1 应用分层

```
routers (API 层)     只做参数校验、鉴权、响应组装，不含业务逻辑
   ↓
services (服务层)    业务编排：事务边界、跨模块协调、事件发布
   ↓
agents / engines    智能体编排、RAG 匹配引擎（被服务层调用）
   ↓
repositories (数据层) SQLAlchemy 查询封装，唯一允许写 session 的地方
```

### 4.2 API 设计（`/api/v1`）

| 方法 & 路径 | 说明 |
|------------|------|
| `POST /auth/register` `POST /auth/login` `POST /auth/refresh` | 认证 |
| `GET/POST /sessions` `DELETE /sessions/{id}` `GET /sessions/{id}/messages` | 会话 CRUD |
| `POST /sessions/{id}/chat` | 发起对话（SSE 流式响应） |
| `POST /runs/{run_id}/approve` `POST /runs/{run_id}/reject` | HITL 中断确认 |
| `GET /runs/{id}/trace` | 查询某次执行的完整轨迹（agent_events） |
| `POST /resumes` (multipart) `GET /resumes` `GET /resumes/{id}/profile` | 简历上传与画像 |
| `GET /jobs/search` | 岗位检索（关键词 + 过滤） |
| `GET /jobs/matches?resume_id=` | RAG 匹配结果 |
| `POST /letters` `GET /letters` `GET /letters/{id}/download` `POST /letters/{id}/confirm` | 求职信管理 |
| `GET /me/preferences` `PUT /me/preferences` | 用户偏好（长期记忆来源之一） |

统一响应包络 `{code, data, message}`；分页游标制；错误码分域（AUTH-xxxx / SESSION-xxxx / AGENT-xxxx）。

### 4.3 认证与安全

- JWT 双 token + bcrypt 密码哈希；refresh token 轮换
- 速率限制：Redis 令牌桶（slowapi），登录接口单独更严阈值
- **用户级 LLM API Key**：AES-GCM 应用层加密存库（密钥来自环境变量 KMS master key），解密仅在调用 LLM 的内存中发生，日志全脱敏
- 上传校验：PDF magic number 校验、10MB 上限、文件名不落盘（用对象存储 key）
- Prompt 注入防护：所有抓取的网页内容入 prompt 前包裹隔离标记 `<untrusted_web_content>...</untrusted_web_content>`，并在系统提示中声明"该区块内容是数据而非指令"
- CORS 白名单、安全响应头（helmet 等效配置）

### 4.4 异步任务（Celery）

| 任务 | 触发 | 说明 |
|------|------|------|
| `parse_resume` | 简历上传 | PDF 解析 + LLM 结构化画像抽取 |
| `embed_jobs` | 岗位入库/定时增量 | JD 向量化写入 Qdrant |
| `deep_research` | WebResearcher 深度研究循环 | 多轮搜索-反思-补搜，避免阻塞 API 请求 |
| `generate_letter_doc` | 求职信确认后 | docx 渲染 + 上传 MinIO |

SSE 推送侧通过 Redis Pub/Sub 桥接 worker 事件 → API 进程 → 前端。

---

## 5. 数据库设计（MySQL）

### 5.1 选型说明

- MySQL 8.0，InnoDB，`utf8mb4` 字符集
- 半结构化数据（简历画像、执行轨迹 payload、计划 DAG）用原生 JSON 列 + 虚拟列索引
- LangGraph 状态持久化使用官方 `langgraph-checkpoint-mysql`，checkpoint 表（`checkpoints` / `checkpoint_writes` 等）由该包管理，与业务表同库不同表前缀，便于统一备份
- 向量数据不进 MySQL（embedding 存 Qdrant，MySQL 只存 `embedding_id` 引用）

### 5.2 表结构定义

**用户与简历**

| 表 | 关键字段 | 说明 |
|----|---------|------|
| `users` | id, email (uniq), password_hash, nickname, llm_api_key_enc, llm_base_url, llm_model_pref, created_at | 用户主表，含加密的模型配置 |
| `resumes` | id, user_id (FK), file_key (S3), filename, file_size, version, parsed_text (LONGTEXT), profile JSON, status, created_at | 简历版本化；profile 为结构化画像 `{basic, education[], experience[], skills[], highlights[]}`；每用户保留多版本，会话引用具体版本 |
| `user_preferences` | user_id, city, industry, salary_range, work_type, raw JSON, updated_at | 求职偏好，喂给长期记忆与 JobSearcher |

**会话与执行**

| 表 | 关键字段 | 说明 |
|----|---------|------|
| `sessions` | id (uuid), user_id, title, resume_id (当前引用), created_at, updated_at | 一个会话对应一个 LangGraph thread |
| `messages` | id, session_id, role (user/assistant/tool), agent_name, content (LONGTEXT), token_count, refs JSON, created_at | 对话消息；refs 挂生成物（岗位/求职信 id） |
| `agent_runs` | id, session_id, thread_id, plan JSON, status (running/awaiting_human/done/error), error, started_at, finished_at | 一次用户输入触发的完整编排执行 |
| `agent_events` | id, run_id, seq, node_name, event_type (plan/agent_start/tool_call/tool_result/critic/interrupt), payload JSON, latency_ms, created_at | 执行轨迹流水，替代 v1 的 print + callback；`GET /runs/{id}/trace` 数据源 |

**岗位与匹配**

| 表 | 关键字段 | 说明 |
|----|---------|------|
| `job_postings` | id, source (serper/manual/api), external_id, title, company, location, employment_type, salary_text, description (LONGTEXT), url (uniq+idx), posted_at, raw JSON, embedding_id, fetched_at | 岗位池按 url 去重；同一岗位多次抓取只更新 |
| `match_results` | id, resume_id, job_posting_id, overall_score, skill_match JSON, skill_gaps JSON, experience_match, created_at, (uniq: resume_id+job_posting_id) | 匹配结果缓存，同简历同岗位不重算 |

**求职信与记忆**

| 表 | 关键字段 | 说明 |
|----|---------|------|
| `cover_letters` | id, user_id, resume_id, job_posting_id, session_id, content (LONGTEXT), file_key, version, critic_score JSON, status (draft/awaiting_confirm/confirmed/archived), created_at | 状态机：HITL 确认后才生成 docx |
| `user_memories` | id, user_id, memory_type (preference/fact/feedback/correction), content, importance, embedding_id, valid_from, valid_until, created_at | 长期记忆条目；带效期支持过期（如"正在找北京的工作"半年后失效） |

### 5.3 关键索引

- `messages(session_id, id)`、`agent_events(run_id, seq)` — 会话流读取
- `job_postings(company, title)`、`job_postings(fetched_at)` — 岗位池维护
- `match_results(resume_id, overall_score DESC)` — 匹配榜
- `user_memories(user_id, memory_type)` — 记忆召回后向量检索的预过滤

---

## 6. 多智能体核心重构

### 6.1 设计原则

1. **结构化优先**：一切 Agent 间通信走 Pydantic 结构化产物（artifact），杜绝自由文本解析
2. **黑板模式**：图状态即共享黑板，Agent 只读写自己负责的字段
3. **计划与执行分离**：Planner 产出显式 DAG，执行器按依赖调度，可并行则并行
4. **闭环质量**：所有"交付物级"输出（求职信）必须过 Critic，不达标自动修订
5. **人在回路**：不可逆动作（写文件、对外提交）前 `interrupt` 确认

### 6.2 新图结构

```
                ┌──────────┐
   user input → │ Planner  │ with_structured_output(PlanSchema)
                └────┬─────┘
                     │ plan: [Step{agent, desc, depends_on}]
        ┌────────────▼────────────┐
        │     Executor 超步        │  LangGraph Send API
        │  无依赖的 Step 并行分发：  │
        │  ResumeAnalyzer /       │
        │  JobSearcher /          │
        │  WebResearcher(子图)     │
        └────────────┬────────────┘
                     ▼
              ┌────────────┐
              │ Synthesizer │  汇总黑板，判断是否需要 CoverLetterGenerator
              └──────┬─────┘
                     ▼
        ┌─────────────────────────┐
        │ CoverLetterGenerator    │ （仅当计划包含时）
        └───────────┬─────────────┘
                    ▼
             ┌──────────┐   score < threshold
             │  Critic  │ ─────────────────┐
             └────┬─────┘                  │ (≤2次)
                  │ score ≥ threshold      ▼
                  ▼                 修订提示回注生成
          ┌──────────────┐
          │ HITL Node    │ interrupt()：求职信确认
          └──────┬───────┘  用户 approve → 继续
                 ▼
             ┌────────┐
             │ Finish │ 汇总输出 + 写库
             └────────┘
```

### 6.3 State 黑板设计

```python
class PlanStep(BaseModel):
    id: str
    agent: Literal["ResumeAnalyzer", "JobSearcher", "WebResearcher",
                   "CoverLetterGenerator", "ChatBot"]
    description: str
    depends_on: list[str] = []

class Plan(BaseModel):
    steps: list[PlanStep]
    is_simple_chat: bool = False        # 闲聊直连 ChatBot，跳过编排

class ResumeProfile(BaseModel):          # 结构化简历画像（替代 v1 的整段文本）
    basic: dict
    skills: list[str]
    experience_years: float
    highlights: list[str]
    raw_analysis: str                    # 供展示的叙事分析

class JobResult(BaseModel): ...
class CompanyResearch(BaseModel): ...
class CriticResult(BaseModel):
    scores: dict[str, float]             # 针对性/专业度/真实性/简洁度
    passed: bool
    suggestions: list[str]

class AgentState(TypedDict):
    user_input: str
    messages: Annotated[list[BaseMessage], add_messages]
    plan: Plan
    completed_steps: list[str]
    # —— 黑板字段：各 Agent 只写自己负责的 ——
    resume_profile: ResumeProfile | None
    job_results: list[JobResult]
    company_research: CompanyResearch | None
    cover_letter: str | None
    critic: CriticResult | None
    revision_count: int
    awaiting_human: bool
    config: dict
```

对比 v1：`needs_followup` 单槽位 → 显式 `Plan.steps` 依赖图；扫描 `msg.name` 找上游输出 → 直接读黑板字段，token 开销大幅下降。

### 6.4 Agent 定义

| Agent | 职责 | 工具 | 模型档位（默认） | 输出 artifact |
|-------|------|------|----------------|---------------|
| Planner | 意图理解 + 任务 DAG 生成（结构化输出） | — | 快速档 qwen-turbo | `Plan` |
| ResumeAnalyzer | 简历解析 + 画像抽取（结构化输出） | `resume_extractor` | 均衡档 qwen-plus | `ResumeProfile` |
| JobSearcher | 岗位检索 + 初筛 + 结果结构化 | `job_search`, `web_search`, `job_detail_fetch` | 均衡档 | `list[JobResult]` |
| WebResearcher | 深度研究子图（见 6.8） | `web_search`, `scrape_website` | 均衡档 | `CompanyResearch` |
| CoverLetterGenerator | 求职信撰写 | `resume_profile`（黑板直读，不再作为工具） | 强力档 qwen-max / deepseek-reasoner | `cover_letter: str` |
| Critic | 结构化评分 + 修订建议 | — | 均衡档（与生成器**异模型**，避免同源偏见） | `CriticResult` |
| Synthesizer | 汇总黑板成面向用户的最终回答 | — | 均衡档 | 最终消息 |
| ChatBot | 闲聊与咨询（`is_simple_chat` 短路） | — | 均衡档 | 消息 |

### 6.5 并行编排

用 LangGraph `Send` API 实现 map 分发：Executor 节点读取 `plan.steps`，将 `depends_on` 已满足且未执行的步骤并行 `Send` 到对应 Agent 节点；全部完成后进入下一超步。典型收益：`ResumeAnalyzer → JobSearcher/WebResearcher` 中后两者可并行，"搜岗位 + 调研公司"延迟减半。

### 6.6 Critic 反思循环

- 评分维度：针对性（是否贴合 JD 关键要求）、专业度（语气/结构/术语）、真实性（是否有简历中不存在的经历——**可验证幻觉**）、简洁度
- 结构化输出 `CriticResult`；`passed=False` 时将 `suggestions` 回注 CoverLetterGenerator 重写，`revision_count` 上限 2，防止震荡
- Critic 分数与修订轨迹写入 `agent_events`，前端求职信页展示

### 6.7 HITL 中断

- 触发点：求职信落盘（生成 docx）前、批量岗位抓取（>20 条）前
- 机制：LangGraph `interrupt()` + MySQL checkpointer 持久化暂停点；用户 `approve` 后 `Command(resume=...)` 恢复
- 超时策略：`awaiting_human` 状态 24h 未处理自动归档该 run

### 6.8 WebResearcher 深度研究子图

```
search → assess(信息缺口评估, 结构化输出: 已覆盖/缺失) 
   → 缺失且轮次<3 → 补搜(改写query) ↺
   → 覆盖或轮次耗尽 → synthesize(带引用来源的汇总)
```

- 每轮搜索结果带来源 URL，最终输出强制引用格式，抑制编造
- 整个子图作为 Celery 异步任务执行时，进度事件经 Redis Pub/Sub → SSE

### 6.9 记忆系统（三层）

| 层 | 实现 | 内容 | 生命周期 |
|----|------|------|---------|
| 工作记忆 | 图 State（黑板） | 当前任务的结构化产物 | 单次 run |
| 情景记忆 | MySQL checkpoint（thread） + `messages` 表 | 会话上下文断点续跑、跨请求恢复 | 会话级 |
| 语义记忆 | `user_memories` + Qdrant 向量 | 求职偏好、反馈修正（"不要再生成两页以上的求职信"） | 跨会话，带效期 |

记忆写入时机：用户显式说"记住…"、偏好设置变更、Critic 修订被采纳（作为反馈信号）。注入时机：Planner 与 Synthesizer 的 prompt 组装阶段做向量召回（按 `memory_type` + 相似度过滤，注入 top-5，控制 token）。

### 6.10 多模型分层路由（ModelRouter）

```python
ROLE_MODEL_MAP = {
    "planner":  {"model": "qwen-turbo",      "temp": 0.1},
    "worker":   {"model": "qwen-plus",       "temp": 0.3},
    "writer":   {"model": "qwen-max",        "temp": 0.5},
    "critic":   {"model": "deepseek-chat",   "temp": 0.1},   # 异源模型
    "embedder": {"model": "bge-m3"},
}
```

- 用户可在设置页覆盖默认映射（`users.llm_model_pref`）
- 统一经 LiteLLM 网关调用，便于成本统计与熔断降级（强模型超时 → 降级到均衡档）
- 每次 LLM 调用的 token 用量、耗时、费用写入 Langfuse trace

---

## 7. RAG 人岗匹配引擎

### 7.1 数据流

```
岗位入库(job_postings) → [Celery] JD 清洗(去导航/样板文字)
  → 切片(语义段落) → BGE-M3 embedding → Qdrant (collection: job_jd)
简历画像(skills/highlights/experience) → 同一 embedding 空间 → 查询向量
检索: 向量 top-K(召回) + payload 过滤(城市/全职) 
  → 结构化评分(精排) → match_results 落库
```

### 7.2 匹配评分设计（可解释）

总分 = 加权(技能匹配度, 经验匹配度, 行业相关性, 地域/类型硬过滤)

- **技能匹配**：简历 skills 与 JD 抽取的 required_skills 做集合比对 + 语义相似（解决"Python"≈"熟悉 Python 开发"），输出"已覆盖 / 缺失"两栏
- **经验匹配**：JD 要求年限 vs `ResumeProfile.experience_years` + 逐段经历相关性
- 评分维度全部入库 `match_results.skill_match/skill_gaps`，前端渲染雷达图与差距清单——**匹配结果必须可解释**，这是与"让 LLM 直接打分"的本质区别

### 7.3 增量维护

- 定时任务刷新岗位池（同 url 只更新 `fetched_at` 与变更字段，embedding 仅在 description 变化时重算）
- 匹配结果缓存失效条件：简历换版本、岗位描述变更

---

## 8. 工具层重构

### 8.1 工具注册（适配器模式）

```python
class BaseToolAdapter(ABC):
    name: str
    input_schema: type[BaseModel]
    cache_ttl: int | None
    rate_limit: tuple[int, int] | None
    async def arun(self, payload: BaseModel) -> ToolResult: ...
```

| 工具 | 实现 | 缓存/限流 |
|------|------|----------|
| `web_search` | Serper API（保留 v1 封装，升级重试+超时） | TTL 30min |
| `scrape_website` | FireCrawl 为主，Playwright 无头浏览器兜底（FireCrawl 失败/JS 重度页面） | TTL 24h，正文截断 10k |
| `job_search` | Serper 检索 + 结果入库 `job_postings`（**先落库再返回**，v1 是直接丢弃） | TTL 1h |
| `job_detail_fetch` | 新增：FireCrawl/Playwright 抓 JD 详情页 → 结构化抽取 | TTL 7d |
| `resume_extractor` | MinIO 读取 + PyMuPDF 解析 + 画像 JSON 读取 | — |
| `render_docx` | python-docx 渲染求职信 → MinIO（仅 HITL 确认后触发） | — |

### 8.2 安全防护

- 工具入参 Pydantic 严格校验（v1 的 `job_search` 参数实际未生效，全部拼进 query 字符串）
- 抓取内容注入隔离（见 4.3）
- 出站请求统一超时与重试（tenacity 指数退避）
- 工具调用全量记录 `agent_events`（参数摘要 + 结果指纹）

---

## 9. 可观测性与评估

| 维度 | 方案 |
|------|------|
| LLM 追踪 | Langfuse 自托管：每次 run 的 trace 含 Planner 计划、各 Agent span、工具 span、token/费用 |
| 执行轨迹 | `agent_events` 落库，支持事后回放任意 run 的完整决策过程 |
| 应用日志 | structlog JSON 结构化日志，按 request_id/run_id 贯穿链路 |
| 指标 | Prometheus：路由准确率采样、各 Agent P95 延迟、工具成功率、Critic 通过率、修订次数分布 |
| 错误 | Sentry |
| 评估集 | ① 路由评估：≥30 条典型/边界 query 断言期望 Plan；② 求职信质量：LLM-as-judge 评分基线；③ RAG 质量：RAGAS（faithfulness / answer relevancy）；④ 端到端：核心 5 场景回归脚本 |

---

## 10. 部署架构

```
Docker Compose（开发/单机生产）:
  nginx │ frontend(next) │ backend(fastapi) │ worker(celery) 
  │ mysql │ redis │ qdrant │ minio │ langfuse │ prometheus+grafana
```

- 镜像分层：backend 与 worker 共用同一基础镜像（代码一致，入口不同）
- 配置：环境变量注入（Pydantic Settings 管理），密钥走 Docker secrets / 环境注入，**不落盘明文**
- 数据备份：MySQL 每日全量 + binlog；MinIO 版本化桶
- 扩展路径：单机 Compose → K8s（backend/worker 无状态可水平扩，Qdrant/MySQL 先单实例）

---

## 11. 工程目录结构

```
jobagent/
├── frontend/                        # Next.js
│   ├── app/                         # (auth)/(dashboard) 路由组
│   ├── components/                  # chat / plan-view / tool-card / radar-chart
│   ├── lib/                         # sse-client / api / auth
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/v1/routers/          # auth.py session.py resume.py job.py letter.py run.py
│   │   ├── core/                    # config.py security.py logging.py errors.py sse.py
│   │   ├── models/                  # SQLAlchemy ORM（第 5 节表定义）
│   │   ├── schemas/                 # Pydantic 请求/响应模型
│   │   ├── repositories/            # 数据访问封装
│   │   ├── services/                # auth/session/resume/job/matching/letter/memory
│   │   ├── agents/
│   │   │   ├── graph/               # builder.py planner.py executor.py synthesizer.py
│   │   │   │                        # critic.py hitl.py state.py
│   │   │   ├── subgraphs/           # deep_research.py
│   │   │   ├── tools/               # adapters.py web_search.py scraper.py job_search.py ...
│   │   │   ├── memory/              # store_mysql.py（BaseStore 实现）inject.py
│   │   │   ├── llm/                 # model_router.py（角色→模型映射）
│   │   │   └── prompts/             # 各 Agent 提示词（v1 prompts.py 拆分迁移）
│   │   ├── matching/                # embedding.py retriever.py scorer.py
│   │   ├── workers/                 # celery_app.py tasks/（parse/embed/research/render）
│   │   └── main.py
│   ├── alembic/                     # 迁移
│   ├── tests/                       # unit/ integration/ eval/
│   └── pyproject.toml               # uv/poetry 管理，替代 requirements.txt
├── docker/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── nginx.conf
└── docs/
    ├── REFACTORING_PLAN.md          # 本文档
    └── api/                         # OpenAPI 自动生成产物
```

---

## 12. 旧模块迁移映射

| v1 模块 | 处置 | v2 归属 |
|---------|------|---------|
| `app.py`（Streamlit） | 废弃重写 | `frontend/` 全部 + `backend/app/api` |
| `agents.py` | 核心重构 | `agents/graph/`（Planner/Executor/Critic/HITL） |
| `chains.py` | 废弃 | supervisor chain 被 Planner 结构化输出取代；finish chain 被 Synthesizer 取代 |
| `members.py` | 废弃 | 成员信息内化为 `PlanStep.agent` Literal |
| `schemas.py` | 扩展 | `agents/graph/state.py`（RouteSchema 思想落地为 PlanSchema） |
| `prompts.py` | 拆分迁移 | `agents/prompts/`，按 Agent 单文件 |
| `tools.py` | 重构 | `agents/tools/`（适配器 + 落库 + 缓存） |
| `utils.py`（Serper/FireCrawl） | 保留升级 | `agents/tools/web_search.py` / `scraper.py` |
| `data_loader.py` | 拆分 | PDF 解析 → `workers/tasks/parse_resume.py`；docx 生成 → `tools/render_docx.py` |
| `search.py`（LinkedIn 死代码） | **删除** | 无（Serper 适配器已覆盖） |
| `custom_callback_handler.py` | 废弃 | SSE 事件流 + `agent_events` 落库取代 |
| `llms.py` | 重构 | `agents/llm/model_router.py` |
| `temp/` 本地文件 | 废弃 | MinIO 对象存储 + MySQL |
| `requirements.txt` | 废弃 | `pyproject.toml`（uv 管理） |

---

## 附录 A：核心场景端到端流程（示例）

**场景：用户上传简历后说"帮我找北京的大模型岗位，并针对最匹配的写求职信"**

1. `POST /resumes` 上传 → Celery `parse_resume` → 画像入库 → Qdrant 无需操作（简历作为查询方）
2. 用户输入 → `POST /sessions/{id}/chat` → 新建 `agent_run`，Planner 产出：
   `steps = [JobSearcher(搜北京LLM岗位), depends: 无] → [Matching(隐式), WebResearcher(调研TOP公司), depends: JobSearcher] → [CoverLetterGenerator, depends: 全部]`
3. Executor 第一超步：JobSearcher 并行执行，SSE 推 `plan` + `agent_start`/`tool_call`
4. 第二超步：匹配引擎精排 + WebResearcher 深度研究**并行**
5. CoverLetterGenerator 基于黑板（画像 + 匹配 TOP1 岗位 + 公司调研）撰写 → Critic 评分 → （若不达标）修订
6. `interrupt`：SSE 推 `interrupt` 事件，前端展示求职信全文 + 评分卡片，用户点确认
7. `POST /runs/{id}/approve` → 图恢复 → `render_docx` → MinIO → `final` 事件携带下载引用
8. `agent_events` / Langfuse trace 完整落档，`match_results` 供岗位中心展示
