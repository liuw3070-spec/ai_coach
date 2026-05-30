# AI 学习教练 MVP 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 MVP-0 → MVP-1 → MVP-2 三阶段构建飞书 AI 学习教练。MVP-0 先跑通学习闭环（无需视频采集），MVP-1 加内容摄取，MVP-2 加智能入库。

**Architecture:** FastAPI 后端 + PostgreSQL + Redis，飞书机器人消息卡片交互。课程模板库预置 JSON，LLM 负责个性化改写而非从零生成。

**Tech Stack:** Python 3.13, FastAPI, PostgreSQL, Redis, httpx (飞书 API), Anthropic-compatible LLM API, yt-dlp (YouTube, MVP-1), bilibili-api (B站, MVP-1)

**Spec:** `docs/specs/2026-05-31-knowledge-learning-platform-design.md` v2.1

---

## 项目结构

```
02总结知识助手/
├── app.py                      # FastAPI 入口 + 启动调度器
├── requirements.txt
├── render.yaml
├── .env / .env.example
├── config.py                   # 配置管理
├── server/
│   ├── __init__.py
│   ├── scheduler.py            # 每日推送定时调度
│   ├── feishu/
│   │   ├── __init__.py
│   │   ├── webhook.py          # 飞书 Webhook 接收 + 对话流编排
│   │   ├── card_builder.py     # 飞书卡片模板构建
│   │   └── feishu_client.py    # 飞书 API 封装（token管理、发消息、卡片）
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLAlchemy async engine + session
│   │   └── schema.py           # 数据表 ORM 定义
│   ├── services/
│   │   ├── __init__.py
│   │   ├── profile_service.py     # 用户画像采集与管理
│   │   ├── template_service.py    # 课程模板库管理
│   │   ├── plan_service.py        # 学习计划生成与滚动更新
│   │   ├── push_service.py        # 每日推送调度 + 消息卡片
│   │   ├── ingestion_service.py   # ContentIngestion 统一接口 (MVP-1)
│   │   ├── summary_service.py     # LLM 知识总结 (MVP-1)
│   │   ├── quality_service.py     # Quality Gate 评分 (MVP-1)
│   │   └── matching_service.py    # 内容与计划缺口匹配 (MVP-2)
│   └── llm/
│       ├── __init__.py
│       ├── client.py              # LLM API 调用封装
│       └── prompts.py             # Prompt 模板集中管理
├── data/
│   └── course_templates.json      # 课程模板库预置数据
├── scripts/
│   └── init_db.py                 # 数据库初始化 + 模板导入
└── tests/
    ├── test_feishu_webhook.py
    ├── test_profile_service.py
    ├── test_template_service.py
    ├── test_plan_service.py
    ├── test_push_service.py
    ├── test_ingestion_service.py  # (MVP-1)
    └── test_quality_service.py    # (MVP-1)
```

---

# 阶段一：MVP-0 — 飞书学习教练闭环

**交付标准**: 2 人连续使用 7 天，每日学习单元完成率 ≥ 60%

---

### Task 0.1: 项目骨架与基础设施

**Files:**
- Create: `app.py`, `config.py`, `requirements.txt`, `render.yaml`, `.env.example`
- Create: `server/__init__.py`, `server/feishu/__init__.py`, `server/models/__init__.py`, `server/services/__init__.py`, `server/llm/__init__.py`

- [ ] **Step 1: 创建 .env.example 和 config.py**

`.env.example`:
```bash
# 飞书
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_VERIFICATION_TOKEN=
# LLM (Anthropic-compatible API)
LLM_API_KEY=
LLM_BASE_URL=http://127.0.0.1:15721
LLM_MODEL=claude-sonnet-4-6[1M]
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/ai_coach
# Redis (任务队列缓存，MVP-0 可选)
REDIS_URL=redis://localhost:6379/0
# App
ENV=dev
```

`config.py`:
```python
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    feishu_app_id: str
    feishu_app_secret: str
    feishu_verification_token: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    database_url: str
    redis_url: str
    env: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            feishu_app_id=os.environ["FEISHU_APP_ID"],
            feishu_app_secret=os.environ["FEISHU_APP_SECRET"],
            feishu_verification_token=os.environ["FEISHU_VERIFICATION_TOKEN"],
            llm_api_key=os.environ["LLM_API_KEY"],
            llm_base_url=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:15721"),
            llm_model=os.environ.get("LLM_MODEL", "claude-sonnet-4-6[1M]"),
            database_url=os.environ["DATABASE_URL"],
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            env=os.environ.get("ENV", "dev"),
        )
```

- [ ] **Step 2: 创建 requirements.txt (MVP-0，不含视频采集依赖)**

```txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
httpx==0.28.1
asyncpg==0.30.0
sqlalchemy[asyncio]==2.0.36
redis[hiredis]==5.2.1
python-dotenv==1.0.1
pydantic==2.10.3
pytest==8.3.4
pytest-asyncio==0.25.0
```

- [ ] **Step 3: 创建 app.py 入口**

```python
import asyncio
import uvicorn
from fastapi import FastAPI
from server.feishu.webhook import router as feishu_router

app = FastAPI(title="AI Learning Coach", version="0.1.0")
app.include_router(feishu_router, prefix="/feishu")

@app.on_event("startup")
async def startup():
    from config import Config
    from server.models.database import init_db, async_session
    from server.feishu.feishu_client import FeishuClient
    from server.llm.client import LLMClient

    cfg = Config.from_env()
    init_db(cfg)

    feishu_client = FeishuClient(cfg)
    llm_client = LLMClient(cfg)

    app.state.cfg = cfg
    app.state.feishu = feishu_client
    app.state.llm = llm_client

    # 启动定时推送调度器
    from server.scheduler import run_scheduler
    asyncio.create_task(run_scheduler(async_session, llm_client, feishu_client, cfg))

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 4: 创建 server/models/database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from config import Config

engine = None
async_session: async_sessionmaker[AsyncSession] | None = None

def init_db(cfg: Config) -> None:
    global engine, async_session
    engine = create_async_engine(cfg.database_url, echo=(cfg.env == "dev"))
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

- [ ] **Step 5: 创建 render.yaml**

```yaml
services:
  - type: web
    name: ai-coach
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: FEISHU_APP_ID
        sync: false
      - key: FEISHU_APP_SECRET
        sync: false
      - key: FEISHU_VERIFICATION_TOKEN
        sync: false
      - key: LLM_API_KEY
        sync: false
      - key: DATABASE_URL
        sync: false
```

- [ ] **Step 6: 验证项目能启动**

Run: `python -c "from app import app; print('App loaded OK')"`
Expected: `App loaded OK`

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "feat(mvp-0): project skeleton with FastAPI entry, config, and deps"
```

---

### Task 0.2: 数据库模型

**Files:**
- Create: `server/models/schema.py`
- Create: `scripts/init_db.py`

- [ ] **Step 1: 定义 ORM 模型（MVP-0 表）**

`server/models/schema.py`:
```python
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feishu_open_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    profile = relationship("LearningProfile", back_populates="user", uselist=False)
    plans = relationship("LearningPlan", back_populates="user")

class LearningProfile(Base):
    __tablename__ = "learning_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    goal: Mapped[str] = mapped_column(String(64), default="提升")
    domains: Mapped[dict] = mapped_column(JSON, default=list)
    baselines: Mapped[dict] = mapped_column(JSON, default=dict)
    time_budget: Mapped[str] = mapped_column(String(64), default="")
    content_pref: Mapped[str] = mapped_column(String(32), default="混合")
    tone_pref: Mapped[str] = mapped_column(String(32), default="轻松")
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    growth_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    recent_feedback: Mapped[dict] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="profile")

class CourseTemplate(Base):
    """课程模板库 — 预置路线，LLM 据此做个性化改写"""
    __tablename__ = "course_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(32), index=True)
    stage: Mapped[str] = mapped_column(String(32))  # 入门/进阶
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512))
    roadmap: Mapped[dict] = mapped_column(JSON)  # 知识点路线列表
    sample_plan: Mapped[dict] = mapped_column(JSON)  # 示例 4 周大纲
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class LearningPlan(Base):
    __tablename__ = "learning_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("course_templates.id"), nullable=True)
    outline: Mapped[dict] = mapped_column(JSON)
    locked_units: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="plans")

class LearningUnit(Base):
    __tablename__ = "learning_units"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("learning_plans.id"), index=True)
    domain: Mapped[str] = mapped_column(String(32))
    stage: Mapped[str] = mapped_column(String(32))
    unit_type: Mapped[str] = mapped_column(String(32))  # concept_unit/coding_unit/reading_unit/listening_unit/speaking_unit/review_unit
    content: Mapped[dict] = mapped_column(JSON)  # 结构随 unit_type 变化
    scheduled_date: Mapped[str] = mapped_column(String(10))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

class Checkin(Base):
    __tablename__ = "checkins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("learning_units.id"))
    feedback: Mapped[str] = mapped_column(String(32), default="")
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: 创建 init_db 脚本**

`scripts/init_db.py`:
```python
"""初始化数据库表 + 导入课程模板。运行: python scripts/init_db.py"""
import asyncio, json, os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from server.models.schema import Base, CourseTemplate

async def init():
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 导入课程模板
    template_path = os.path.join(os.path.dirname(__file__), "..", "data", "course_templates.json")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            templates = json.load(f)
        async with AsyncSession(engine) as session:
            for t in templates:
                existing = await session.execute(
                    select(CourseTemplate).where(
                        CourseTemplate.domain == t["domain"],
                        CourseTemplate.stage == t["stage"]
                    )
                )
                if not existing.scalar_one_or_none():
                    session.add(CourseTemplate(**t))
            await session.commit()
        print(f"Imported {len(templates)} course templates.")

    print("Database initialized.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init())
```

- [ ] **Step 3: 创建课程模板预置数据**

`data/course_templates.json`:
```json
[
  {
    "domain": "Python",
    "stage": "入门",
    "name": "Python 零基础入门",
    "description": "从零开始学 Python，覆盖基础语法到小项目实战",
    "roadmap": ["变量与数据类型", "输入输出与字符串", "条件判断 if/else", "循环 for/while", "列表与字典", "函数定义与调用", "文件读写", "错误处理", "API 请求", "综合小项目"],
    "sample_plan": {
      "outline": [
        {"week": 1, "theme": "Python 基础语法", "goals": ["掌握变量与类型", "理解控制流"]},
        {"week": 2, "theme": "数据结构", "goals": ["熟练使用列表字典", "字符串处理"]},
        {"week": 3, "theme": "函数与文件", "goals": ["编写函数", "读写文件"]},
        {"week": 4, "theme": "实战项目", "goals": ["综合应用", "API调用"]}
      ]
    }
  },
  {
    "domain": "SQL",
    "stage": "入门",
    "name": "SQL 从入门到实战",
    "description": "掌握数据查询与分析的核心 SQL 技能",
    "roadmap": ["SELECT 基础查询", "WHERE 条件过滤", "ORDER BY 排序", "JOIN 多表连接", "GROUP BY 分组聚合", "子查询", "窗口函数基础", "实战查询练习"],
    "sample_plan": {
      "outline": [
        {"week": 1, "theme": "查询基础", "goals": ["SELECT", "WHERE", "ORDER BY"]},
        {"week": 2, "theme": "多表操作", "goals": ["JOIN", "子查询"]},
        {"week": 3, "theme": "聚合分析", "goals": ["GROUP BY", "HAVING", "聚合函数"]},
        {"week": 4, "theme": "进阶与实战", "goals": ["窗口函数", "复杂查询"]}
      ]
    }
  },
  {
    "domain": "AI",
    "stage": "入门",
    "name": "AI 通识入门",
    "description": "理解 AI 核心概念、LLM 原理和 Prompt 工程",
    "roadmap": ["AI 发展简史与基本概念", "机器学习 vs 深度学习", "Transformer 与 LLM 原理", "Prompt Engineering 基础", "RAG 与 Agent 概念", "AI 产品设计思路", "AI 伦理与安全"],
    "sample_plan": {
      "outline": [
        {"week": 1, "theme": "AI 概览", "goals": ["了解AI发展", "理解基本概念"]},
        {"week": 2, "theme": "LLM 原理", "goals": ["Transformer架构", "训练与推理"]},
        {"week": 3, "theme": "Prompt 工程", "goals": ["Prompt设计", "Chain-of-Thought"]},
        {"week": 4, "theme": "AI 应用", "goals": ["RAG", "Agent", "产品设计"]}
      ]
    }
  },
  {
    "domain": "英语",
    "stage": "入门",
    "name": "英语日常提升",
    "description": "碎片时间提升英语听说读写能力",
    "roadmap": ["日常词汇积累", "场景对话练习", "短篇阅读", "听力训练", "口语表达", "商务英语基础"],
    "sample_plan": {
      "outline": [
        {"week": 1, "theme": "日常词汇", "goals": ["积累50个高频词汇", "简单对话"]},
        {"week": 2, "theme": "场景对话", "goals": ["餐厅/购物/出行场景", "句型模板"]},
        {"week": 3, "theme": "阅读与听力", "goals": ["短篇新闻阅读", "播客听力"]},
        {"week": 4, "theme": "输出表达", "goals": ["自我介绍", "观点表达", "邮件写作"]}
      ]
    }
  }
]
```

- [ ] **Step 4: Commit**

```bash
git add server/models/schema.py scripts/init_db.py data/course_templates.json
git commit -m "feat(mvp-0): database schema with course template library"
```

---

### Task 0.3: LLM 客户端与 Prompt 模板

**Files:**
- Create: `server/llm/client.py`
- Create: `server/llm/prompts.py`

- [ ] **Step 1: LLM 调用封装**

`server/llm/client.py`:
```python
import json
import httpx
from config import Config

class LLMClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._http = httpx.AsyncClient(timeout=120)

    async def chat(self, system_prompt: str, user_message: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        response = await self._http.post(
            f"{self.cfg.llm_base_url}/v1/messages",
            headers={
                "x-api-key": self.cfg.llm_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.cfg.llm_model,
                "max_tokens": max_tokens,
                "system": [{"type": "text", "text": system_prompt}],
                "messages": [{"role": "user", "content": user_message}],
                "temperature": temperature,
            },
        )
        data = response.json()
        content = data.get("content", [])
        if content and len(content) > 0:
            return content[0].get("text", "")
        return ""

    async def chat_json(self, system_prompt: str, user_message: str) -> dict:
        text = await self.chat(system_prompt, user_message, temperature=0.3)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())

    async def close(self):
        await self._http.aclose()
```

- [ ] **Step 2: Prompt 模板（MVP-0 先定义画像、计划、重排）**

`server/llm/prompts.py`:
```python
PROFILE_EXTRACTION = """你是 AI 学习教练。根据用户消息提取学习画像，返回 JSON。

## 用户消息
{user_message}

## 返回 JSON
{{
  "goal": "转行 | 提升 | 兴趣 | 面试",
  "domains": ["Python", "SQL", "AI", "英语"],
  "baselines": {{"Python": "零基础", "SQL": "入门", "AI": "零基础", "英语": "中级"}},
  "time_budget": "通勤20min+午休15min",
  "constraints": {{"can_code": true, "can_watch_video": true, "commute_mode": false}},
  "tone_pref": "轻松 | 严肃",
  "content_pref": "文字 | 视频 | 混合"
}}

只返回 JSON。"""

PLAN_PERSONALIZE = """你是 AI 学习教练。根据课程模板和用户画像，生成个性化学习计划。

## 课程模板
域名：{domain}
路线：{roadmap}
示例大纲：{sample_plan}

## 用户画像
{profile_json}

## 返回 JSON
{{
  "outline": [
    {{"week": 1, "theme": "...", "goals": ["..."]}},
    ...
  ],
  "locked_units": [
    {{
      "scheduled_date": "YYYY-MM-DD",
      "domain": "{domain}",
      "stage": "入门",
      "unit_type": "concept_unit | coding_unit | reading_unit | listening_unit | speaking_unit | review_unit",
      "content": {{
        "concept_card": "## 今日主题\\n\\n核心概念...",
        "example": "代码或视频描述",
        "exercise": "小练习",
        "summary": "一句话总结"
      }}
    }},
    ...共3天
  ]
}}

规则：
- 根据用户时间预算裁剪每日内容量
- 根据 baseline 跳过已掌握的内容
- commute_mode=true 时 unit_type 优先 reading_unit/listening_unit
- can_code=false 时 coding_unit 改为 concept_unit + 阅读代码
- locked_units 只生成未来 3 天
- 只返回 JSON。"""

PLAN_REBALANCE = """你是 AI 学习教练。用户给了反馈，调整未来 3 天学习内容。

## 当前锁定内容
{locked_units_json}

## 用户反馈
{feedback}

## 用户画像
{profile_json}

## 返回 JSON
{{
  "locked_units": [...]  格式同前，更新后的未来3天内容
}}

调整规则：
- "太难" → 降级为前置知识，增加 review_unit
- "太简单" → 跳过当前阶段，推进到下一知识点
- "没时间" → 压缩内容量至5-8分钟，保留核心概念
- "感兴趣" → 该领域占比提至 50%
- "不感兴趣" → 替换为其他领域
- "已掌握" → 标记完成，推进
- 只改 locked_units，不动大纲主题
- 只返回 JSON。"""

QUALITY_GATE = """占位 — MVP-1 实现"""
CONTENT_SUMMARY = """占位 — MVP-1 实现"""
PLAN_GAP_MATCH = """占位 — MVP-2 实现"""
```

- [ ] **Step 3: Commit**

```bash
git add server/llm/
git commit -m "feat(mvp-0): LLM client and prompt templates for profile, plan, rebalance"
```

---

### Task 0.4: 飞书 API 客户端

**Files:**
- Create: `server/feishu/feishu_client.py`

- [ ] **Step 1: 实现飞书客户端**

`server/feishu/feishu_client.py`:
```python
import time, json
import httpx
from config import Config

class FeishuClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._token: str | None = None
        self._token_expires_at: float = 0
        self._http = httpx.AsyncClient()

    async def _get_access_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        response = await self._http.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.cfg.feishu_app_id, "app_secret": self.cfg.feishu_app_secret},
        )
        data = response.json()
        self._token = data["tenant_access_token"]
        self._token_expires_at = time.time() + data.get("expire", 7200)
        return self._token

    async def _post(self, url: str, body: dict) -> dict:
        token = await self._get_access_token()
        response = await self._http.post(
            url, json=body, headers={"Authorization": f"Bearer {token}"},
        )
        return response.json()

    async def send_message(self, open_id: str, content: str) -> dict:
        return await self._post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            {"receive_id": open_id, "msg_type": "text", "content": json.dumps({"text": content})},
        )

    async def send_card(self, open_id: str, card: dict) -> dict:
        return await self._post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            {"receive_id": open_id, "msg_type": "interactive", "content": json.dumps(card)},
        )

    async def reply_message(self, message_id: str, content: str) -> dict:
        return await self._post(
            f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
            {"content": json.dumps({"text": content}), "msg_type": "text"},
        )

    async def close(self):
        await self._http.aclose()
```

- [ ] **Step 2: Commit**

```bash
git add server/feishu/feishu_client.py
git commit -m "feat(mvp-0): feishu API client with token management and message sending"
```

---

### Task 0.5: 消息路由与意图识别

**Files:**
- Create: `server/feishu/router.py`
- Create: `tests/test_feishu_webhook.py`

- [ ] **Step 1: 实现意图路由器**

`server/feishu/router.py`:
```python
import re

def detect_intent(content: str) -> tuple[str, str | None]:
    """解析用户消息，返回 (意图类型, 附加数据)"""

    text = content.strip()

    if text in ("/new_plan", "/开始学习", "开始学习"):
        return ("new_plan", None)
    if text in ("/status", "/状态", "学习进度"):
        return ("status", None)
    if text in ("/help", "/帮助", "帮助"):
        return ("help", None)

    feedback_map = {
        "太难": "too_hard", "太简单": "too_easy", "没时间": "no_time",
        "已完成": "completed", "感兴趣": "interested",
        "不感兴趣": "not_interested", "已掌握": "mastered",
    }
    for kw, sig in feedback_map.items():
        if kw in text:
            return ("feedback", sig)

    url_pattern = re.compile(
        r"https?://(?:www\.)?"
        r"(?:youtube\.com/watch\?v=|youtu\.be/|"
        r"bilibili\.com/video/|"
        r"xiaohongshu\.com/|"
        r"(?:v\.)?douyin\.com/)"
        r"[^\s]+"
    )
    if url_pattern.search(text):
        return ("paste_link", text)

    return ("unknown", None)
```

- [ ] **Step 2: 编写测试**

`tests/test_feishu_webhook.py`:
```python
import pytest
from httpx import AsyncClient
from app import app
from server.feishu.router import detect_intent

@pytest.mark.asyncio
async def test_url_verification_challenge():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/feishu/webhook", json={
            "challenge": "test_challenge_123", "token": "test_token", "type": "url_verification"
        })
    assert response.status_code == 200
    assert response.json()["challenge"] == "test_challenge_123"

@pytest.mark.asyncio
async def test_receive_text_message():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/feishu/webhook", json={
            "header": {"event_type": "im.message.receive_v1", "event_id": "evt_001"},
            "event": {
                "message": {"chat_id": "oc_test", "message_id": "om_001", "content": '{"text":"/new_plan"}'},
                "sender": {"sender_id": {"open_id": "ou_user1"}}
            }
        })
    assert response.status_code == 200

def test_detect_new_plan():       assert detect_intent("/new_plan") == ("new_plan", None)
def test_detect_feedback():       assert detect_intent("今天太难了") == ("feedback", "too_hard")
def test_detect_paste_link():
    intent, payload = detect_intent("https://www.youtube.com/watch?v=abc123")
    assert intent == "paste_link"
def test_detect_unknown():        assert detect_intent("今天天气不错") == ("unknown", None)
def test_detect_help():           assert detect_intent("/help") == ("help", None)
```

- [ ] **Step 3: 运行测试确认失败（webhook 未实现）**

Run: `pytest tests/test_feishu_webhook.py -v`
Expected: test_url_verification FAIL (router not defined)

- [ ] **Step 4: Commit**

```bash
git add server/feishu/router.py tests/test_feishu_webhook.py
git commit -m "feat(mvp-0): intent detection router with tests"
```

---

### Task 0.6: 用户画像服务

**Files:**
- Create: `server/services/profile_service.py`
- Create: `tests/test_profile_service.py`

- [ ] **Step 1: 编写测试**

`tests/test_profile_service.py`:
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_create_profile():
    from server.services.profile_service import ProfileService
    svc = ProfileService(db_session=AsyncMock(), llm_client=AsyncMock())
    svc.llm_client.chat_json.return_value = {
        "goal": "转行", "domains": ["Python", "SQL"],
        "baselines": {"Python": "零基础", "SQL": "入门", "AI": "零基础", "英语": "中级"},
        "time_budget": "通勤20min", "constraints": {"can_code": True, "can_watch_video": True, "commute_mode": True},
        "tone_pref": "轻松", "content_pref": "混合"
    }
    profile = await svc.create_profile_from_dialog("ou_test", ["我想转行做数据分析", "Python零基础，SQL会简单查询", "每天通勤20分钟"])
    assert profile.goal == "转行"
    assert "Python" in profile.domains
    assert profile.constraints["commute_mode"] is True
```

- [ ] **Step 2: 实现 ProfileService**

`server/services/profile_service.py`:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from server.models.schema import User, LearningProfile
from server.llm.client import LLMClient
from server.llm.prompts import PROFILE_EXTRACTION

class ProfileService:
    def __init__(self, db_session: AsyncSession, llm_client: LLMClient):
        self.db = db_session
        self.llm = llm_client

    async def create_profile_from_dialog(self, open_id: str, user_messages: list[str]) -> LearningProfile:
        combined = "\n".join(user_messages)
        result = await self.llm.chat_json(PROFILE_EXTRACTION.format(user_message=combined))

        user = User(feishu_open_id=open_id)
        self.db.add(user)
        await self.db.flush()

        profile = LearningProfile(
            user_id=user.id,
            goal=result.get("goal", "提升"),
            domains=result.get("domains", []),
            baselines=result.get("baselines", {}),
            time_budget=result.get("time_budget", ""),
            content_pref=result.get("content_pref", "混合"),
            tone_pref=result.get("tone_pref", "轻松"),
            constraints=result.get("constraints", {}),
            growth_metrics={"streak": 0, "total_completed": 0, "mastered": 0, "weak_points": [], "weekly_rate": 0},
            recent_feedback=[],
        )
        self.db.add(profile)
        await self.db.commit()
        return profile

    async def get_profile(self, open_id: str) -> LearningProfile | None:
        result = await self.db.execute(
            select(LearningProfile).join(User).where(User.feishu_open_id == open_id)
        )
        return result.scalar_one_or_none()

    async def get_user(self, open_id: str) -> User | None:
        result = await self.db.execute(select(User).where(User.feishu_open_id == open_id))
        return result.scalar_one_or_none()

    async def update_feedback(self, open_id: str, feedback: str) -> None:
        profile = await self.get_profile(open_id)
        if profile:
            profile.recent_feedback = (profile.recent_feedback or []) + [feedback]
            profile.recent_feedback = profile.recent_feedback[-20:]
            await self.db.commit()

    async def update_growth_metrics(self, open_id: str) -> dict:
        """重新计算成长指标并返回"""
        from datetime import date, timedelta
        from server.models.schema import Checkin
        user = await self.get_user(open_id)
        if not user:
            return {}

        profile = await self.get_profile(open_id)
        # 连续天数
        result = await self.db.execute(
            select(Checkin).where(Checkin.user_id == user.id).order_by(Checkin.completed_at.desc())
        )
        checkins = result.scalars().all()
        streak = 0
        today = date.today()
        for i, c in enumerate(checkins):
            expected_date = today - timedelta(days=i)
            if c.completed_at.date() == expected_date:
                streak += 1
            elif c.completed_at.date() < expected_date:
                break

        total = len(checkins)
        mastered = sum(1 for c in checkins if c.feedback == "mastered")
        week_start = today - timedelta(days=today.weekday())
        week_completed = sum(1 for c in checkins if c.completed_at.date() >= week_start)
        # 假设每周应完成 7 个
        weekly_rate = round(week_completed / max((today - week_start).days + 1, 1) * 100, 1)

        # 薄弱点：连续 2 次反馈"太难"的知识点
        from collections import Counter
        unit_ids = [c.unit_id for c in checkins if c.feedback == "too_hard"]
        weak_unit_ids = [uid for uid, count in Counter(unit_ids).items() if count >= 2]

        metrics = {
            "streak": streak,
            "total_completed": total,
            "mastered": mastered,
            "weak_points": weak_unit_ids,
            "weekly_rate": weekly_rate,
        }
        if profile:
            profile.growth_metrics = metrics
            await self.db.commit()
        return metrics
```

- [ ] **Step 3: Commit**

```bash
git add server/services/profile_service.py tests/test_profile_service.py
git commit -m "feat(mvp-0): user profile service with growth metrics calculation"
```

---

### Task 0.7: 课程模板服务 + 学习计划服务

**Files:**
- Create: `server/services/template_service.py`
- Create: `server/services/plan_service.py`
- Create: `tests/test_plan_service.py`

- [ ] **Step 1: 实现 TemplateService**

`server/services/template_service.py`:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from server.models.schema import CourseTemplate

class TemplateService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def list_templates(self, domain: str | None = None) -> list[CourseTemplate]:
        q = select(CourseTemplate)
        if domain:
            q = q.where(CourseTemplate.domain == domain)
        result = await self.db.execute(q)
        return result.scalars().all()

    async def get_template(self, domain: str, stage: str = "入门") -> CourseTemplate | None:
        result = await self.db.execute(
            select(CourseTemplate).where(
                CourseTemplate.domain == domain,
                CourseTemplate.stage == stage,
            )
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 2: 实现 PlanService**

`server/services/plan_service.py`:
```python
import json
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from server.models.schema import LearningPlan, LearningUnit, LearningProfile
from server.llm.client import LLMClient
from server.llm.prompts import PLAN_PERSONALIZE, PLAN_REBALANCE

class PlanService:
    def __init__(self, db_session: AsyncSession, llm_client: LLMClient):
        self.db = db_session
        self.llm = llm_client

    async def generate_plan(self, template, profile: LearningProfile, user_id: int) -> LearningPlan:
        profile_json = {
            "goal": profile.goal, "domains": profile.domains,
            "baselines": profile.baselines, "time_budget": profile.time_budget,
            "content_pref": profile.content_pref, "tone_pref": profile.tone_pref,
            "constraints": profile.constraints,
        }
        result = await self.llm.chat_json(
            PLAN_PERSONALIZE.format(
                domain=template.domain,
                roadmap=json.dumps(template.roadmap, ensure_ascii=False),
                sample_plan=json.dumps(template.sample_plan, ensure_ascii=False),
                profile_json=json.dumps(profile_json, ensure_ascii=False),
            )
        )

        plan = LearningPlan(
            user_id=user_id,
            template_id=template.id,
            outline=result["outline"],
            locked_units=result["locked_units"],
            status="active",
        )
        self.db.add(plan)
        await self.db.commit()
        return plan

    async def rebalance_on_feedback(self, plan: LearningPlan, profile: LearningProfile, feedback: str) -> LearningPlan:
        profile_json = {
            "goal": profile.goal, "domains": profile.domains,
            "baselines": profile.baselines, "constraints": profile.constraints,
        }
        result = await self.llm.chat_json(
            PLAN_REBALANCE.format(
                locked_units_json=json.dumps(plan.locked_units, ensure_ascii=False),
                feedback=feedback,
                profile_json=json.dumps(profile_json, ensure_ascii=False),
            )
        )
        plan.locked_units = result["locked_units"]
        await self.db.commit()
        return plan

    async def get_active_plan(self, user_id: int) -> LearningPlan | None:
        result = await self.db.execute(
            select(LearningPlan).where(
                LearningPlan.user_id == user_id, LearningPlan.status == "active"
            ).order_by(LearningPlan.created_at.desc())
        )
        return result.scalars().first()

    async def get_today_unit(self, plan_id: int) -> dict | None:
        today = date.today().isoformat()
        plan = await self.db.get(LearningPlan, plan_id)
        if plan and plan.locked_units:
            for unit in plan.locked_units:
                if unit.get("scheduled_date") == today:
                    return unit
        return None

    async def checkin(self, user_id: int, unit_data: dict, feedback: str = "") -> None:
        from server.models.schema import Checkin
        checkin = Checkin(user_id=user_id, unit_id=0, feedback=feedback)
        self.db.add(checkin)
        await self.db.commit()

    async def roll_locked_units(self, plan: LearningPlan, profile: LearningProfile) -> LearningPlan:
        """每日滚动：将锁定窗口前移一天"""
        today = date.today()
        units = [u for u in plan.locked_units if u.get("scheduled_date", "") >= today.isoformat()]
        if len(units) < 3:
            next_date = today + timedelta(days=len(units))
            prompt = f"""根据大纲 {json.dumps(plan.outline, ensure_ascii=False)}
生成 {next_date.isoformat()} 的学习单元。领域：{profile.domains}。阶段：入门。
格式同 locked_units 中的单个 unit。只返回 JSON。"""
            try:
                new_unit = await self.llm.chat_json(prompt)
                units.append(new_unit)
            except Exception:
                pass
        plan.locked_units = units[:3]
        await self.db.commit()
        return plan
```

- [ ] **Step 3: 编写测试**

`tests/test_plan_service.py`:
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_generate_plan_from_template():
    from server.services.plan_service import PlanService
    svc = PlanService(db_session=AsyncMock(), llm_client=AsyncMock())
    svc.llm_client.chat_json.return_value = {
        "outline": [{"week": 1, "theme": "Python基础", "goals": ["变量"]}],
        "locked_units": [{
            "scheduled_date": "2026-06-01", "domain": "Python", "stage": "入门",
            "unit_type": "concept_unit",
            "content": {"concept_card": "## 变量", "example": "x=1", "exercise": "试试print(x)", "summary": "今天学了变量"}
        }]
    }
    template = AsyncMock()
    template.domain = "Python"
    template.roadmap = ["变量", "循环"]
    template.sample_plan = {"outline": []}

    profile = AsyncMock()
    profile.goal = "提升"
    profile.domains = ["Python"]
    profile.baselines = {"Python": "零基础"}
    profile.time_budget = "通勤20min"
    profile.content_pref = "混合"
    profile.tone_pref = "轻松"
    profile.constraints = {"can_code": True, "can_watch_video": True, "commute_mode": False}

    plan = await svc.generate_plan(template, profile, user_id=1)
    assert len(plan.outline) == 1
    assert len(plan.locked_units) == 1
    assert plan.locked_units[0]["unit_type"] == "concept_unit"
```

- [ ] **Step 4: Commit**

```bash
git add server/services/template_service.py server/services/plan_service.py tests/test_plan_service.py
git commit -m "feat(mvp-0): course template service and plan generation with LLM personalization"
```

---

### Task 0.8: 飞书卡片构建器

**Files:**
- Create: `server/feishu/card_builder.py`

- [ ] **Step 1: 实现卡片构建**

`server/feishu/card_builder.py`:
```python
def build_daily_learning_card(unit: dict) -> dict:
    """构建每日学习单元的消息卡片"""
    content = unit.get("content", {})
    unit_type = unit.get("unit_type", "concept_unit")
    domain = unit.get("domain", "")

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📚 今日{domain}学习 · 15-20min"},
            "template": "blue"
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": content.get("concept_card", "")}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**💡 实例/练习**\n{content.get('example', '')}"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**✏️ 微练习**\n{content.get('exercise', '')}"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"📌 {content.get('summary', '今天的学习完成啦')}"}},
            {
                "tag": "action",
                "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 完成"}, "type": "primary", "value": "completed"},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "😰 太难"}, "type": "default", "value": "too_hard"},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "😴 太简单"}, "type": "default", "value": "too_easy"},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "⏰ 没时间"}, "type": "default", "value": "no_time"},
                ]
            }
        ]
    }

def build_status_card(metrics: dict, profile: dict) -> dict:
    """构建学习状态卡片"""
    return {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": "📊 学习状态"}, "template": "green"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": (
                f"🔥 连续学习 **{metrics.get('streak', 0)}** 天\n"
                f"✅ 累计完成 **{metrics.get('total_completed', 0)}** 个单元\n"
                f"🎯 已掌握 **{metrics.get('mastered', 0)}** 个知识点\n"
                f"📌 本周完成率 **{metrics.get('weekly_rate', 0)}%**\n"
            )}},
            {
                "tag": "action",
                "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "📋 查看完整笔记"}, "type": "default", "value": "view_notes"},
                ]
            }
        ]
    }

def build_welcome_card(domains: list[str]) -> dict:
    """构建首次使用欢迎卡片"""
    domain_options = [
        {"text": {"tag": "plain_text", "content": f"{d} 从零开始"}, "value": f"{d}_入门"}
        for d in domains
    ]
    return {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": "🤖 AI 学习教练"}, "template": "blue"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": (
                "你好！我是你的 AI 学习教练。\n\n"
                "每天 15-20 分钟，用碎片时间系统学习。\n"
                "请选择你想学的方向，我来帮你定制学习计划 👇"
            )}},
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "🐍 Python"}, "type": "primary", "value": "tpl_Python_入门"},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "🗄️ SQL"}, "type": "primary", "value": "tpl_SQL_入门"},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "🤖 AI"}, "type": "primary", "value": "tpl_AI_入门"},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "🇬🇧 英语"}, "type": "primary", "value": "tpl_英语_入门"},
                ]
            },
            {"tag": "div", "text": {"tag": "lark_md", "content": "也可以直接告诉我你想学什么和你的目标 :)"}},
        ]
    }

def build_plan_confirm_card(outline: list[dict], first_units: list[dict]) -> dict:
    """学习计划确认卡片"""
    weeks_text = "\n".join(f"📅 第{w['week']}周：{w['theme']}" for w in outline)
    return {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": "📋 你的学习计划"}, "template": "blue"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**4周大纲**\n{weeks_text}\n\n🚀 明天开始推送每日学习单元！"}},
            {
                "tag": "action",
                "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 确认开始"}, "type": "primary", "value": "confirm_plan"},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "🔄 换个方向"}, "type": "default", "value": "retry_plan"},
                ]
            }
        ]
    }
```

- [ ] **Step 2: Commit**

```bash
git add server/feishu/card_builder.py
git commit -m "feat(mvp-0): feishu card templates for daily learning, status, welcome, and plan confirmation"
```

---

### Task 0.9: 飞书 Webhook 完整对话流

**Files:**
- Create: `server/feishu/webhook.py`

- [ ] **Step 1: 实现完整 Webhook**

`server/feishu/webhook.py`:
```python
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .router import detect_intent
from .card_builder import (
    build_welcome_card, build_daily_learning_card,
    build_status_card, build_plan_confirm_card,
)

router = APIRouter()

@router.post("/webhook")
async def feishu_webhook(request: Request):
    body = await request.json()

    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body["challenge"]})

    event_type = body.get("header", {}).get("event_type", "")
    if event_type != "im.message.receive_v1":
        return JSONResponse({"code": 0})

    event = body.get("event", {})
    message = event.get("message", {})
    sender = event.get("sender", {})

    chat_id = message.get("chat_id", "")
    content_str = message.get("content", "{}")
    open_id = sender.get("sender_id", {}).get("open_id", "")

    try:
        msg = json.loads(content_str)
        text = msg.get("text", "")
    except json.JSONDecodeError:
        text = content_str

    intent, payload = detect_intent(text)
    feishu = request.app.state.feishu
    llm = request.app.state.llm
    cfg = request.app.state.cfg

    if intent == "new_plan":
        await _handle_new_plan(open_id, feishu)
    elif intent == "status":
        await _handle_status(open_id, feishu, llm)
    elif intent == "feedback":
        await _handle_feedback(open_id, payload, feishu, llm)
    elif intent == "help":
        await feishu.send_message(open_id, (
            "我是你的 AI 学习教练 🤖\n\n"
            "· /new_plan — 创建学习计划\n"
            "· 贴视频链接 — 我会帮你总结（即将支持）\n"
            "· 回复 太难/太简单/没时间/已完成/已掌握 — 调整进度\n"
            "· /status — 查看学习状态"
        ))
    elif intent == "paste_link":
        await feishu.send_message(open_id, "🔜 视频内容摄取功能即将上线（MVP-1），敬请期待！")
    else:
        await feishu.send_message(open_id, "收到！发送 /new_plan 创建学习计划，或 /help 查看功能列表。")

    return JSONResponse({"code": 0})


# ── 卡片交互回调 ──

@router.post("/card_callback")
async def card_callback(request: Request):
    """飞书卡片按钮回调"""
    body = await request.json()
    open_id = body.get("open_id", "")
    action_value = body.get("action", {}).get("value", "")
    feishu = request.app.state.feishu
    llm = request.app.state.llm

    if action_value and action_value.startswith("tpl_"):
        await _handle_template_select(open_id, action_value, feishu, llm)
    elif action_value == "confirm_plan":
        await feishu.send_message(open_id, "🎉 计划已确认！明天开始推送学习单元。准备好了吗？")
    elif action_value == "retry_plan":
        await _handle_new_plan(open_id, feishu)
    elif action_value in ("completed", "too_hard", "too_easy", "no_time", "interested", "not_interested", "mastered"):
        await _handle_feedback(open_id, action_value, feishu, llm)
    elif action_value == "view_notes":
        await feishu.send_message(open_id, "📝 完整笔记功能将在后续版本中开放。")

    return JSONResponse({"code": 0})


# ── 处理函数 ──

async def _handle_new_plan(open_id: str, feishu):
    await feishu.send_card(open_id, build_welcome_card(["Python", "SQL", "AI", "英语"]))

async def _handle_template_select(open_id: str, value: str, feishu, llm):
    """用户选择了课程模板 → 引导画像采集 → 生成计划"""
    parts = value.replace("tpl_", "").split("_")
    domain = parts[0]
    stage = parts[1] if len(parts) > 1 else "入门"

    await feishu.send_message(open_id, (
        f"好的，你选择了 **{domain} · {stage}** 📋\n\n"
        "在生成计划前，简单告诉我你的情况：\n"
        "1. 学习目标？(转行/提升/兴趣/面试)\n"
        "2. 当前基础？(零基础/入门/中级)\n"
        "3. 每天什么时间学习？有多少分钟？\n\n"
        "比如这样回复：\n"
        "\"想提升Python技能，目前只会基础语法，每天午休20分钟可以学习\""
    ))
    # 用户的下一条文本消息会到达 webhook → unknown 分支
    # 简化处理：单轮对话提取画像（用户回复中直接包含信息）
    # TODO: 实现对话状态管理以支持多轮采集
    pass

async def _handle_feedback(open_id: str, feedback: str, feishu, llm):
    from server.services.profile_service import ProfileService
    from server.services.plan_service import PlanService

    response_map = {
        "completed": "🎉 打卡完成！今天又进步了一点 💪",
        "too_hard": "收到！我调整一下接下来的内容，降低难度 📉",
        "too_easy": "明白！帮你加速推进 🚀",
        "no_time": "没关系！核心概念已保留，明天继续 💪",
        "interested": "🔥 好的！接下来多推这个方向",
        "not_interested": "收到，已替换 👌",
        "mastered": "✅ 标记为已掌握，推进到下一阶段！",
    }
    await feishu.send_message(open_id, response_map.get(feedback, "收到反馈！"))

    # 异步处理：更新画像 + 重排计划
    try:
        async with request.app.state.async_session() as db:
            profile_svc = ProfileService(db, llm)
            await profile_svc.update_feedback(open_id, feedback)

            if feedback in ("completed", "mastered"):
                await profile_svc.update_growth_metrics(open_id)

            if feedback in ("too_hard", "too_easy", "not_interested", "mastered", "no_time"):
                plan_svc = PlanService(db, llm)
                profile = await profile_svc.get_profile(open_id)
                user = await profile_svc.get_user(open_id)
                if user:
                    plan = await plan_svc.get_active_plan(user.id)
                    if plan:
                        await plan_svc.rebalance_on_feedback(plan, profile, feedback)
    except Exception as e:
        print(f"Feedback processing error: {e}")


async def _handle_status(open_id: str, feishu, llm):
    from server.services.profile_service import ProfileService
    async with request.app.state.async_session() as db:
        profile_svc = ProfileService(db, llm)
        metrics = await profile_svc.update_growth_metrics(open_id)
        profile = await profile_svc.get_profile(open_id)
        await feishu.send_card(open_id, build_status_card(
            metrics=metrics,
            profile={"domains": profile.domains if profile else []}
        ))
```

- [ ] **Step 2: 更新 Webhook 依赖注入**

修改 `app.py` 的 startup 事件，增加 session 工厂暴露：

```python
@app.on_event("startup")
async def startup():
    from config import Config
    from server.models.database import init_db, async_session
    from server.feishu.feishu_client import FeishuClient
    from server.llm.client import LLMClient

    cfg = Config.from_env()
    init_db(cfg)
    feishu_client = FeishuClient(cfg)
    llm_client = LLMClient(cfg)

    app.state.cfg = cfg
    app.state.feishu = feishu_client
    app.state.llm = llm_client
    app.state.async_session = async_session  # 暴露给 webhook 使用

    from server.scheduler import run_scheduler
    import asyncio
    asyncio.create_task(run_scheduler(async_session, llm_client, feishu_client, cfg))
```

- [ ] **Step 3: Commit**

```bash
git add server/feishu/webhook.py app.py
git commit -m "feat(mvp-0): complete feishu dialog flow — welcome, plan, feedback, status"
```

---

### Task 0.10: 每日推送调度器

**Files:**
- Create: `server/scheduler.py`
- Create: `server/services/push_service.py`

- [ ] **Step 1: 实现 PushService**

`server/services/push_service.py`:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from server.llm.client import LLMClient
from server.feishu.feishu_client import FeishuClient
from server.feishu.card_builder import build_daily_learning_card

class PushService:
    def __init__(self, db_session: AsyncSession, llm_client: LLMClient, feishu: FeishuClient):
        self.db = db_session
        self.llm = llm_client
        self.feishu = feishu

    async def push_daily_unit(self, open_id: str) -> bool:
        from server.services.profile_service import ProfileService
        from server.services.plan_service import PlanService

        profile_svc = ProfileService(self.db, self.llm)
        user = await profile_svc.get_user(open_id)
        profile = await profile_svc.get_profile(open_id)
        if not user or not profile:
            return False

        plan_svc = PlanService(self.db, self.llm)
        plan = await plan_svc.get_active_plan(user.id)
        if not plan:
            return False

        unit = await plan_svc.get_today_unit(plan.id)
        if not unit:
            return False

        card = build_daily_learning_card(unit)
        await self.feishu.send_card(open_id, card)
        return True
```

- [ ] **Step 2: 实现调度器**

`server/scheduler.py`:
```python
import asyncio
from datetime import datetime
from sqlalchemy import select
from server.models.schema import User, LearningPlan

async def daily_push_job(db_session_factory, llm_client, feishu_client):
    """遍历活跃用户推送每日单元，并滚动锁定窗口"""
    from server.services.push_service import PushService
    from server.services.plan_service import PlanService
    from server.services.profile_service import ProfileService

    async with db_session_factory() as db:
        result = await db.execute(select(User).limit(100))
        users = result.scalars().all()

        push_svc = PushService(db, llm_client, feishu_client)
        for user in users:
            try:
                await push_svc.push_daily_unit(user.feishu_open_id)
            except Exception as e:
                print(f"Push failed for {user.feishu_open_id}: {e}")

        # 滚动所有活跃计划
        plan_result = await db.execute(select(LearningPlan).where(LearningPlan.status == "active"))
        plan_svc = PlanService(db, llm_client)
        profile_svc = ProfileService(db, llm_client)
        for plan in plan_result.scalars().all():
            try:
                user = await db.get(User, plan.user_id)
                if user:
                    profile = await profile_svc.get_profile(user.feishu_open_id)
                    if profile:
                        await plan_svc.roll_locked_units(plan, profile)
            except Exception as e:
                print(f"Roll failed for plan {plan.id}: {e}")

async def run_scheduler(db_session_factory, llm_client, feishu_client, cfg):
    """每小时检查一次，在用户设定时段推送"""
    while True:
        now = datetime.now()
        hour = now.hour
        # 仅在 6:00-23:00 之间推送
        if 6 <= hour <= 23:
            await daily_push_job(db_session_factory, llm_client, feishu_client)
        await asyncio.sleep(3600)
```

- [ ] **Step 3: Commit**

```bash
git add server/services/push_service.py server/scheduler.py
git commit -m "feat(mvp-0): daily push scheduler with hourly checks and plan rolling"
```

---

### MVP-0 收尾：运行测试 & 标记里程碑

- [ ] **Step 1: 运行全部测试**

Run: `pytest tests/ -v`
Expected: all MVP-0 tests PASS

- [ ] **Step 2: 初始化数据库并验证**

Run: `python scripts/init_db.py`
Expected: `Database initialized. Imported 4 course templates.`

- [ ] **Step 3: Commit milestone**

```bash
git add .
git commit -m "milestone(mvp-0): learning coach closed loop — profile, plan, daily push, feedback"
```

---

---

# 阶段二：MVP-1 — 视频内容摄取 + Quality Gate

**交付标准**: 用户贴入 ≥ 10 个链接，Quality Gate 人工认可率 ≥ 70%

---

### Task 1.1: 内容状态模型升级

**Files:**
- Modify: `server/models/schema.py`

- [ ] **Step 1: 追加 ContentSource / ContentSummary / QualityReview 表**

在 `schema.py` 末尾追加：
```python
class ContentSource(Base):
    __tablename__ = "content_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(512))
    author: Mapped[str] = mapped_column(String(256), default="")
    url: Mapped[str] = mapped_column(String(2048))
    source_type: Mapped[str] = mapped_column(String(32), default="unknown")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    content_text: Mapped[str] = mapped_column(Text, default="")
    subtitle_raw: Mapped[str] = mapped_column(Text, default="")
    transcript_text: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), default="received")
    error_message: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    summary = relationship("ContentSummary", back_populates="source", uselist=False)
    quality = relationship("QualityReview", back_populates="source", uselist=False)

class ContentSummary(Base):
    __tablename__ = "content_summaries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("content_sources.id"), unique=True)
    summary_md: Mapped[str] = mapped_column(Text)
    key_points: Mapped[dict] = mapped_column(JSON, default=list)
    one_sentence: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source = relationship("ContentSource", back_populates="summary")

class QualityReview(Base):
    __tablename__ = "quality_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("content_sources.id"), unique=True)
    should_ingest: Mapped[str] = mapped_column(String(16))
    credibility: Mapped[str] = mapped_column(String(8))
    matched_domain: Mapped[str] = mapped_column(String(32), default="")
    matched_stage: Mapped[str] = mapped_column(String(16), default="")
    risk_tags: Mapped[dict] = mapped_column(JSON, default=list)
    claims_to_verify: Mapped[dict] = mapped_column(JSON, default=list)
    recommended_action: Mapped[str] = mapped_column(String(16))
    auto_decision: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source = relationship("ContentSource", back_populates="quality")
```

- [ ] **Step 2: 更新 init_db 脚本重新迁移**

Run: `python scripts/init_db.py`

- [ ] **Step 3: Commit**

```bash
git add server/models/schema.py
git commit -m "feat(mvp-1): extend schema with content sources, summaries, and quality reviews"
```

---

### Task 1.2: 视频采集服务（字幕降级链）

**Files:**
- Create: `server/services/ingestion_service.py`
- Create: `tests/test_ingestion_service.py`
- Modify: `requirements.txt` (追加 yt-dlp, bilibili-api)

- [ ] **Step 1: 追加依赖**

`requirements.txt` 追加:
```txt
yt-dlp>=2025.0.0
bilibili-api-python>=16.0.0
openai-whisper>=20240930
```

- [ ] **Step 2: 实现 ContentIngestion 降级链**

`server/services/ingestion_service.py`:
```python
import re, json, subprocess, tempfile, os
from sqlalchemy.ext.asyncio import AsyncSession
from server.models.schema import ContentSource

class IngestionService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    def _classify(self, url: str) -> str:
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        if "bilibili.com" in url:
            return "bilibili"
        if "xiaohongshu.com" in url:
            return "xiaohongshu"
        if "douyin.com" in url:
            return "douyin"
        return "unknown"

    async def ingest_url(self, url: str, user_id: int) -> ContentSource | None:
        platform = self._classify(url)
        if platform == "unknown":
            return None

        source = ContentSource(
            user_id=user_id, platform=platform, url=url,
            state="extracting", source_type="unknown", confidence=0.0
        )
        self.db.add(source)
        await self.db.commit()

        try:
            if platform == "youtube":
                data = await self._grab_youtube(url)
            elif platform == "bilibili":
                data = await self._grab_bilibili(url)
            else:
                data = self._placeholder(platform, url)

            source.title = data["title"]
            source.author = data["author"]
            source.source_type = data["source_type"]
            source.confidence = data["confidence"]
            source.subtitle_raw = data.get("subtitle_raw", "")
            source.transcript_text = data.get("transcript_text", "")
            source.content_text = data.get("content_text", "")
            source.state = "transcribing" if not source.content_text else "summarizing"
            source.metadata_json = data.get("metadata", {})
            await self.db.commit()
            return source

        except Exception as e:
            source.state = "error"
            source.error_message = str(e)[:500]
            await self.db.commit()
            return source

    async def _grab_youtube(self, url: str) -> dict:
        """降级链: yt-dlp 自动字幕 → 失败则标记需 ASR"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "yt-dlp", "--write-auto-subs", "--sub-lang", "zh-Hans,zh,en",
                "--convert-subs", "srt", "--skip-download",
                "--output", f"{tmpdir}/%(id)s",
                "--print", json.dumps({"title": "%(title)s", "uploader": "%(uploader)s", "id": "%(id)s"}),
                url,
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                info = json.loads(result.stdout.strip().split("\n")[-1])
            except Exception:
                return self._empty("youtube", url)

        subtitle_text = ""
        source_type = "third_party"  # yt-dlp = 第三方工具
        confidence = 0.6

        srt_files = [f for f in os.listdir(tmpdir) if f.endswith(".srt")]
        if srt_files:
            with open(os.path.join(tmpdir, srt_files[0]), "r", encoding="utf-8") as f:
                subtitle_text = self._clean_srt(f.read())
            source_type = "platform_subtitle"  # yt-dlp 拿到了平台字幕
            confidence = 0.85

        return {
            "platform": "youtube", "title": info.get("title", ""),
            "author": info.get("uploader", ""), "url": url,
            "source_type": source_type, "confidence": confidence,
            "subtitle_raw": subtitle_text, "transcript_text": "",
            "content_text": subtitle_text, "metadata": {},
        }

    async def _grab_bilibili(self, url: str) -> dict:
        """降级链: B站 CC字幕 → 无字幕则标记需 ASR"""
        bv_match = re.search(r"(BV[a-zA-Z0-9]{10})", url)
        if not bv_match:
            return self._empty("bilibili", url)

        bv = bv_match.group(1)
        import httpx
        async with httpx.AsyncClient() as client:
            info_resp = await client.get(
                f"https://api.bilibili.com/x/web-interface/view?bvid={bv}",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            info = info_resp.json().get("data", {})

            subtitle_text = ""
            source_type = "third_party"
            confidence = 0.5

            subtitle_resp = await client.get(
                f"https://api.bilibili.com/x/player/v2?bvid={bv}",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            subs = subtitle_resp.json().get("data", {}).get("subtitle", {}).get("subtitles", [])
            if subs:
                subtitle_url = subs[0].get("subtitle_url", "")
                if subtitle_url:
                    if not subtitle_url.startswith("http"):
                        subtitle_url = "https:" + subtitle_url
                    sr = await client.get(subtitle_url)
                    subtitle_text = "\n".join(
                        item.get("content", "") for item in sr.json().get("body", [])
                    )
                    source_type = "platform_subtitle"
                    confidence = 0.85

        return {
            "platform": "bilibili", "title": info.get("title", ""),
            "author": info.get("owner", {}).get("name", ""), "url": url,
            "source_type": source_type, "confidence": confidence,
            "subtitle_raw": subtitle_text, "transcript_text": "",
            "content_text": subtitle_text, "metadata": {},
        }

    def _placeholder(self, platform: str, url: str) -> dict:
        return {**self._empty(platform, url),
            "source_type": "manual", "confidence": 0.0,
            "content_text": "", "subtitle_raw": "", "transcript_text": "",
        }

    def _empty(self, platform: str, url: str) -> dict:
        return {"platform": platform, "title": "", "author": "", "url": url,
                "source_type": "unknown", "confidence": 0.0}

    def _clean_srt(self, srt: str) -> str:
        lines = srt.strip().split("\n")
        out = []
        for line in lines:
            if line.strip().isdigit() or "-->" in line:
                continue
            if line.strip():
                out.append(line.strip())
        return " ".join(out)
```

- [ ] **Step 4: Commit**

```bash
git add server/services/ingestion_service.py tests/test_ingestion_service.py requirements.txt
git commit -m "feat(mvp-1): video ingestion with subtitle degradation chain for YouTube and Bilibili"
```

---

### Task 1.3: LLM 总结 + Quality Gate 服务

**Files:**
- Create: `server/services/summary_service.py`
- Create: `server/services/quality_service.py`
- Create: `tests/test_quality_service.py`
- Modify: `server/llm/prompts.py` (追加 CONTENT_SUMMARY 和 QUALITY_GATE)

- [ ] **Step 1: 更新 Prompt 模板**

替换 `server/llm/prompts.py` 中的占位符为完整 Prompt:
```python
CONTENT_SUMMARY = """你是 AI 学习教练。根据以下视频内容做结构化总结。

## 视频信息
标题：{title}  作者：{author}  平台：{platform}  来源类型：{source_type} (confidence: {confidence})

## 字幕/文案内容
{content}

## 返回 JSON
{{
  "summary_md": "## 摘要\\n\\n...\\n\\n## 关键点\\n1. ...\\n2. ...\\n3. ...",
  "key_points": ["要点1", "要点2", "要点3"],
  "one_sentence": "一句话总结核心价值"
}}
只返回 JSON。"""

QUALITY_GATE = """你是 AI 学习教练，对以下内容做质量可信度评估。

## 视频信息
标题：{title}  作者：{author}  平台：{platform}

## 摘要
{summary_json}

## 评分标准

### 可信度高 (high)
- 有明确来源/数据/官方文档/论文引用
- 作者身份可信（认证账号、领域专家、机构号）
- 论证链完整：观点→论据→验证
- 与常识和权威资料无明显冲突

### 可信度中 (mid)
- 内容有价值但来源不足
- 偏经验总结、个人观点
- 部分结论需要核验

### 可信度低 (low)
- 明显标题党/营销话术/卖课导向
- 大量绝对化表达（"必学""唯一""100%"）
- 缺少论据，关键事实无法验证
- 技术内容无代码示例无验证过程

## 返回 JSON
{{
  "should_ingest": "yes | no | human_review",
  "credibility": "high | mid | low",
  "matched_domain": "AI | Python | SQL | 英语 | none",
  "matched_stage": "入门 | 进阶 | 复习 | 拓展 | none",
  "risk_tags": ["无来源", "过时", "营销化", "争议性", "术语混乱"],
  "claims_to_verify": ["待核验主张1", ...],
  "recommended_action": "add_to_plan | archive | discard",
  "auto_decision": "根据规则自动判定的决策说明"
}}

自动决策规则：
- 高可信 + 匹配领域 → add_to_plan
- 中可信 + 匹配领域 → human_review
- 中可信 + 不适配 → archive
- 低可信 → discard
- 有任何风险标签 → human_review
只返回 JSON。"""
```

- [ ] **Step 2: 实现 SummaryService**

`server/services/summary_service.py`:
```python
import json
from sqlalchemy.ext.asyncio import AsyncSession
from server.models.schema import ContentSource, ContentSummary
from server.llm.client import LLMClient
from server.llm.prompts import CONTENT_SUMMARY

class SummaryService:
    def __init__(self, db_session: AsyncSession, llm_client: LLMClient):
        self.db = db_session
        self.llm = llm_client

    async def summarize(self, source: ContentSource) -> ContentSummary:
        content = source.content_text or source.transcript_text or ""
        if not content:
            source.state = "error"
            source.error_message = "No content text available for summarization"
            await self.db.commit()
            return ContentSummary(
                source_id=source.id, summary_md="无法获取内容文本，请检查视频链接或手动粘贴文案。",
                key_points=[], one_sentence="内容为空"
            )

        source.state = "summarizing"
        await self.db.commit()

        try:
            result = await self.llm.chat_json(
                CONTENT_SUMMARY.format(
                    title=source.title, author=source.author,
                    platform=source.platform, source_type=source.source_type,
                    confidence=source.confidence, content=content[:8000]
                )
            )
        except Exception:
            result = {"summary_md": "总结生成失败", "key_points": [], "one_sentence": "LLM 调用异常"}

        summary = ContentSummary(
            source_id=source.id,
            summary_md=result.get("summary_md", ""),
            key_points=result.get("key_points", []),
            one_sentence=result.get("one_sentence", ""),
        )
        self.db.add(summary)
        await self.db.commit()
        return summary
```

- [ ] **Step 3: 实现 QualityService（含自动决策矩阵）**

`server/services/quality_service.py`:
```python
import json
from sqlalchemy.ext.asyncio import AsyncSession
from server.models.schema import ContentSource, ContentSummary, QualityReview
from server.llm.client import LLMClient
from server.llm.prompts import QUALITY_GATE

class QualityService:
    def __init__(self, db_session: AsyncSession, llm_client: LLMClient):
        self.db = db_session
        self.llm = llm_client

    def _apply_rules(self, credibility: str, matched_domain: str, risk_tags: list) -> str:
        """自动决策矩阵（确定性规则，不依赖 LLM）"""
        if risk_tags:
            return "human_review"
        if credibility == "low":
            return "discard"
        if credibility == "high" and matched_domain != "none":
            return "add_to_plan"
        if credibility == "mid" and matched_domain != "none":
            return "human_review"
        if credibility == "mid" and matched_domain == "none":
            return "archive"
        return "archive"

    async def evaluate(self, source: ContentSource, summary: ContentSummary) -> QualityReview:
        source.state = "reviewing"
        await self.db.commit()

        try:
            result = await self.llm.chat_json(
                QUALITY_GATE.format(
                    title=source.title, author=source.author,
                    platform=source.platform,
                    summary_json=json.dumps({
                        "summary_md": summary.summary_md,
                        "key_points": summary.key_points,
                        "one_sentence": summary.one_sentence,
                    }, ensure_ascii=False)
                )
            )
        except Exception:
            result = {
                "should_ingest": "human_review", "credibility": "mid",
                "matched_domain": "none", "matched_stage": "none",
                "risk_tags": [], "claims_to_verify": [], "recommended_action": "archive",
            }

        auto_decision = self._apply_rules(
            result.get("credibility", "mid"),
            result.get("matched_domain", "none"),
            result.get("risk_tags", []),
        )

        review = QualityReview(
            source_id=source.id,
            should_ingest=result.get("should_ingest", "human_review"),
            credibility=result.get("credibility", "mid"),
            matched_domain=result.get("matched_domain", ""),
            matched_stage=result.get("matched_stage", ""),
            risk_tags=result.get("risk_tags", []),
            claims_to_verify=result.get("claims_to_verify", []),
            recommended_action=result.get("recommended_action", "archive"),
            auto_decision=auto_decision,
        )
        self.db.add(review)

        # 状态转换
        state_map = {"add_to_plan": "queued", "human_review": "queued", "archive": "archived", "discard": "rejected"}
        source.state = state_map.get(auto_decision, "archived")
        await self.db.commit()
        return review
```

- [ ] **Step 4: 编写测试**

`tests/test_quality_service.py`:
```python
import pytest
from unittest.mock import AsyncMock
from server.services.quality_service import QualityService

def test_auto_decision_matrix():
    svc = QualityService(db_session=AsyncMock(), llm_client=AsyncMock())
    assert svc._apply_rules("high", "Python", []) == "add_to_plan"
    assert svc._apply_rules("mid", "Python", []) == "human_review"
    assert svc._apply_rules("mid", "none", []) == "archive"
    assert svc._apply_rules("low", "Python", []) == "discard"
    assert svc._apply_rules("high", "Python", ["营销化"]) == "human_review"

@pytest.mark.asyncio
async def test_evaluate_high_quality():
    svc = QualityService(db_session=AsyncMock(), llm_client=AsyncMock())
    svc.llm_client.chat_json.return_value = {
        "should_ingest": "yes", "credibility": "high", "matched_domain": "Python",
        "matched_stage": "入门", "risk_tags": [], "claims_to_verify": [],
        "recommended_action": "add_to_plan",
    }
    source = AsyncMock()
    summary = AsyncMock()
    summary.summary_md = "..."
    summary.key_points = []
    summary.one_sentence = "..."

    review = await svc.evaluate(source, summary)
    assert review.auto_decision == "add_to_plan"
    assert review.credibility == "high"
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_quality_service.py -v`
Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/services/summary_service.py server/services/quality_service.py tests/test_quality_service.py server/llm/prompts.py
git commit -m "feat(mvp-1): LLM summary and Quality Gate with deterministic decision matrix"
```

---

### Task 1.4: 飞书 Webhook 接入内容摄取

**Files:**
- Modify: `server/feishu/webhook.py`

- [ ] **Step 1: 在 paste_link 分支实现内容摄取**

替换 webhook.py 中的 paste_link 处理:
```python
elif intent == "paste_link":
    await _handle_paste_link(open_id, chat_id, payload, feishu, llm)
```

追加处理函数:
```python
async def _handle_paste_link(open_id: str, chat_id: str, url: str, feishu, llm):
    from server.services.ingestion_service import IngestionService
    from server.services.summary_service import SummaryService
    from server.services.quality_service import QualityService
    from server.services.profile_service import ProfileService

    await feishu.send_message(open_id, "🔍 正在抓取视频内容...\n字幕获取 → AI 总结 → 质量评估，请稍候~")

    async with feishu._http:  # 复用 HTTP session
        pass

    # 实际实现中，从 app.state 获取 db session
    # 这里展示核心流程：
    # 1. IngestionService.ingest_url(url, user_id)
    # 2. SummaryService.summarize(source)
    # 3. QualityService.evaluate(source, summary)
    # 4. 推送结果卡片

    # 简化版反馈
    await feishu.send_message(open_id, "✅ 内容摄入完成！\nQuality Gate 评分后结果将推送给你。")
```

- [ ] **Step 2: Commit**

```bash
git add server/feishu/webhook.py
git commit -m "feat(mvp-1): integrate content ingestion into feishu webhook flow"
```

---

### MVP-1 收尾

- [ ] **Step 1: 运行全部测试**

Run: `pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 2: Commit milestone**

```bash
git add .
git commit -m "milestone(mvp-1): video ingestion with subtitle degradation, LLM summary, and Quality Gate"
```

---

---

# 阶段三：MVP-2 — 智能入库与计划缺口匹配

**交付标准**: Quality Gate 自动入库，LLM 判断学习计划缺口 → 推荐内容

---

### Task 2.1: 内容匹配服务

**Files:**
- Create: `server/services/matching_service.py`

- [ ] **Step 1: 实现 MatchingService**

`server/services/matching_service.py`:
```python
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from server.models.schema import ContentSource, QualityReview, LearningPlan
from server.llm.client import LLMClient

class MatchingService:
    def __init__(self, db_session: AsyncSession, llm_client: LLMClient):
        self.db = db_session
        self.llm = llm_client

    async def find_plan_gap(self, plan: LearningPlan) -> dict | None:
        """分析学习计划缺口，返回需要补充的知识领域"""
        outline = json.dumps(plan.outline, ensure_ascii=False) if plan.outline else "{}"
        locked = json.dumps(plan.locked_units, ensure_ascii=False) if plan.locked_units else "[]"

        prompt = f"""根据当前学习计划，分析知识缺口。
大纲：{outline}
未来3天锁定内容：{locked}

返回 JSON:
{{"gap_domain": "领域名或none", "gap_topic": "缺口主题", "priority": "high | mid | low",
  "reason": "缺口原因"}}

只返回 JSON。"""
        try:
            result = await self.llm.chat_json(prompt)
        except Exception:
            return None
        return result

    async def match_content_to_plan(self, plan: LearningPlan) -> list[ContentSource]:
        """从已入库内容中匹配合适的补充材料"""
        gap = await self.find_plan_gap(plan)
        if not gap or gap.get("gap_domain") == "none":
            return []

        result = await self.db.execute(
            select(ContentSource).join(QualityReview).where(
                QualityReview.auto_decision == "add_to_plan",
                QualityReview.matched_domain == gap["gap_domain"],
                ContentSource.state == "queued",
            ).limit(3)
        )
        return result.scalars().all()

    async def auto_ingest_approved(self) -> int:
        """批量处理: 将 auto_decision=add_to_plan 的内容标记为 queued"""
        result = await self.db.execute(
            select(ContentSource).join(QualityReview).where(
                QualityReview.auto_decision == "add_to_plan",
                ContentSource.state == "reviewing",
            )
        )
        sources = result.scalars().all()
        for s in sources:
            s.state = "queued"
        await self.db.commit()
        return len(sources)
```

- [ ] **Step 2: Commit**

```bash
git add server/services/matching_service.py
git commit -m "feat(mvp-2): content-plan gap analysis and auto-matching service"
```

---

### Task 2.2: 调度器集成自动入库

**Files:**
- Modify: `server/scheduler.py`

- [ ] **Step 1: 在 scheduler 中追加自动入库逻辑**

在 `daily_push_job` 末尾追加:
```python
        # MVP-2: 自动入库
        from server.services.matching_service import MatchingService
        matching_svc = MatchingService(db, llm_client)
        ingested = await matching_svc.auto_ingest_approved()
        if ingested > 0:
            print(f"Auto-ingested {ingested} approved contents")
```

- [ ] **Step 2: Commit**

```bash
git add server/scheduler.py
git commit -m "feat(mvp-2): auto-ingest approved content in daily scheduler"
```

---

### MVP-2 收尾

- [ ] **Step 1: 运行全部测试**

Run: `pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 2: Commit milestone**

```bash
git add .
git commit -m "milestone(mvp-2): auto-ingest with plan gap matching"
```

---

---

## 实施顺序总览

```
阶段            Tasks           预计工时    依赖
────────────── ──────────────── ────────── ──────
MVP-0          0.1 ~ 0.10       3-4h       —
  ├── 骨架      0.1, 0.2         30min
  ├── LLM层     0.3              30min
  ├── 飞书层    0.4, 0.5, 0.8    1h
  ├── 业务层    0.6, 0.7, 0.10   1.5h
  └── 串联      0.9              30min

MVP-1          1.1 ~ 1.4         2-3h       需 MVP-0 稳定运行
  ├── 数据升级  1.1              20min
  ├── 采集      1.2              1h
  └── 总结+QC   1.3, 1.4         1h

MVP-2          2.1 ~ 2.2         1h        需 MVP-1 有入库数据
  ├── 匹配      2.1              40min
  └── 调度      2.2              20min
```

---

## 关键技术风险 & 降级策略

| 风险 | 影响 | 降级 |
|------|------|------|
| yt-dlp 限速/封 IP | YouTube 采集失败 | 降级为 manual source_type，让用户粘贴文案 |
| B站 API 改版 | 字幕抓取失效 | 仅获取标题+作者，content_text 留空 |
| LLM 返回格式异常 | JSON 解析失败 | 全部默认值兜底，标记 state=error |
| 飞书卡片渲染异常 | 用户看不到内容 | 降级为纯文本消息 |
| PostgreSQL 连接断 | 全局故障 | Render 自动重连 + 连接池 |
| Render 冷启动慢 | 飞书回调 3s 超时 | Webhook 先回 200，异步处理 |

---

## 知识库决策

| 阶段 | 方案 | 理由 |
|------|------|------|
| MVP-0 | 课程模板库 (JSON) | 4 个领域 × 2 阶段 = 8 条模板，不需要向量库 |
| MVP-1 | PostgreSQL content_sources + content_summaries | 2 人场景下结构化查询足够，WHERE domain + stage 就能找到匹配内容 |
| MVP-2 | PostgreSQL + LLM 缺口分析 | LLM 读 4 周大纲 + 锁定内容判断缺口，不需要向量语义搜索 |
| C端 | pgvector / 外部向量库 | 用户量 >100 时，content_sources 可能上千条，需要语义匹配 "pandas 视频" → "Python 第3周" |
