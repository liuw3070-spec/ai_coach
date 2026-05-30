# AI 学习教练 — 项目日志

**最后更新**: 2026-05-31
**版本**: MVP-0 Ready
**仓库**: https://github.com/liuw3070-spec/ai_coach

---

## 一、当前状态

MVP-0 代码完成，本地 7 项测试通过，Neon PostgreSQL 已初始化（4 个课程模板已导入）。待 Render 部署。

### Git 历史

| Commit | 内容 |
|--------|------|
| `20c0964` | feat(mvp-0): AI learning coach closed loop — 27 文件，7 张 ORM 表，全模块 |
| `903409c` | refactor: migrate feishu client to official lark-oapi v1.6.0 SDK |
| `26b1032` | feat: neon ssl support, llm multi-provider, docs |
| `fc122f1` | refactor: switch LLM client to DeepSeek V4 Pro (OpenAI-compatible API) |

---

## 二、项目结构

```
02总结知识助手/
├── app.py              FastAPI 入口 (lifespan)
├── config.py           配置管理 (Config.from_env)
├── requirements.txt    生产依赖
├── render.yaml         Render 部署描述
├── .gitignore
├── data/
│   └── course_templates.json   4 领域课程模板 (Python/SQL/AI/英语 × 入门)
├── scripts/
│   └── init_db.py              数据库建表 + 模板导入
├── server/
│   ├── scheduler.py            每小时推送调度器 (06:00-23:00)
│   ├── feishu/
│   │   ├── webhook.py          飞书 Webhook 接收 + 对话流编排
│   │   ├── card_builder.py     4 种飞书消息卡片
│   │   ├── feishu_client.py    lark-oapi SDK 封装
│   │   └── router.py           7 种意图识别
│   ├── models/
│   │   ├── database.py         异步引擎 (Neon SSL)
│   │   └── schema.py           7 张 ORM 表
│   ├── services/
│   │   ├── profile_service.py  用户画像 + 成长指标
│   │   ├── template_service.py 模板查询
│   │   ├── plan_service.py     计划生成/滚动/重排
│   │   └── push_service.py     每日推送
│   └── llm/
│       ├── client.py           DeepSeek V4 Pro (OpenAI 兼容)
│       └── prompts.py          3 组 Prompt 模板
└── tests/
    └── test_feishu_webhook.py  7 tests PASS
```

---

## 三、数据模型

| 表 | 说明 | 状态 |
|------|------|------|
| users | 飞书 open_id 绑定 | ✅ |
| learning_profiles | 用户画像 (目标/基线/约束/反馈/成长指标) | ✅ |
| course_templates | 课程模板库 (4 条预置数据) | ✅ 已导入 |
| learning_plans | 学习计划 (大纲 + 锁定单元) | ✅ |
| learning_units | 每日学习单元 (6 种 unit_type) | ✅ |
| checkins | 打卡记录 + 反馈信号 | ✅ |
| content_sources | # MVP-1 视频来源 | 🔜 |
| content_summaries | # MVP-1 LLM 总结 | 🔜 |
| quality_reviews | # MVP-1 Quality Gate | 🔜 |

---

## 四、对话流

```
用户消息                意图              响应
─────────────────────────────────────────────────────
/new_plan            → new_plan    → 欢迎卡片 (选择方向)
点击 [Python] 按钮   → tpl_Python  → 追问画像问题
"想转行，零基础，20min" → unknown    → TODO: 需要对话状态管理串联画像生成
太难                   → feedback   → 调整难度 + 重排计划
已掌握                 → feedback   → 标记完成 + 推进
/status               → status     → 学习状态卡片
/help                 → help       → 功能列表
贴 URL                 → paste_link → 暂不支持 (MVP-1)
```

> **已知缺口**：模板选择后用户文本回复尚未自动走 ProfileService → PlanService 流程。当前 webhook 的 `_handle_template_select` 只发了追问消息，下一轮用户回复会走 `unknown` 分支。需要在对话状态中缓存 `pending_template`，在 unknown 分支检测并触发画像采集 → 生成计划。

---

## 五、部署清单

### 外部服务

| 服务 | 用途 | 状态 |
|------|------|------|
| **Neon PostgreSQL** | 数据库 (亚太区) | ✅ 已创建 |
| **GitHub** | 代码仓库 | ✅ https://github.com/liuw3070-spec/ai_coach |
| **DeepSeek API** | LLM (deepseek-chat / V4 Pro) | ✅ key 已获取 |
| **飞书开放平台** | 机器人 App | ✅ App 已创建，待配置事件订阅 |
| **Render** | 托管 FastAPI | 🔜 待部署 |

### Render 环境变量

| Key | 说明 |
|-----|------|
| `FEISHU_APP_ID` | cli_aa9198f854b9dbdf |
| `FEISHU_APP_SECRET` | 已填入 Render |
| `FEISHU_VERIFICATION_TOKEN` | **待飞书事件订阅 URL 验证后获取** |
| `LLM_API_KEY` | sk-bf5b209d... |
| `LLM_BASE_URL` | https://api.deepseek.com |
| `LLM_MODEL` | deepseek-chat |
| `DATABASE_URL` | postgresql+asyncpg://neondb_owner:***@ep-damp-boat-ao3uwrhu.c-2.ap-southeast-1.aws.neon.tech/neondb |
| `ENV` | prod |

### 部署步骤

```
1. Render Dashboard → New Web Service → 连接 liuw3070-spec/ai_coach
2. 填环境变量 → Deploy → 等待 3-5 分钟
3. 拿到域名: https://ai-coach-xxxx.onrender.com
4. 飞书开放平台 → 事件订阅 → 请求 URL:
   https://ai-coach-xxxx.onrender.com/feishu/webhook
5. 验证通过 → 复制 Verification Token → 填入 Render 环境变量
6. 飞书 App → 创建版本 → 发布
7. 飞书客户端搜索 "AI学习教练" → 发送 /new_plan 测试
```

---

## 六、待修复问题

| # | 问题 | 影响 | 优先级 |
|---|------|------|--------|
| 1 | 对话状态管理缺失：模板选择后无法自动触发画像→计划流程 | /new_plan 卡片按钮流程中断 | 🔴 部署前应修 |
| 2 | `/card_callback` 路由未注册到 app.py | 卡片按钮点击无响应 | 🔴 部署前应修 |
| 3 | 每日推送时段硬编码 06:00-23:00 每小时一次 | 非用户设定时段，重复推送 | 🟡 |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-05-31 | MVP-0 代码完成，27 文件 1124 行，Neon 初始化，飞书 App 创建 |
| 2026-05-31 | 飞书 SDK 迁移至 lark-oapi 1.6.0，LLM 切换至 DeepSeek V4 Pro |
