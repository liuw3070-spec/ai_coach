# AI 学习教练 — 项目日志

**最后更新**: 2026-05-31
**版本**: MVP-0 Ready (12 tests passing)
**仓库**: https://github.com/liuw3070-spec/ai_coach

---

## 一、当前状态

MVP-0 代码完成，本地 12 项测试通过，Neon PostgreSQL 已初始化（4 个课程模板已导入）。**待 Render 部署。**

### Git 历史

| Commit | 内容 |
|--------|------|
| `20c0964` | feat(mvp-0): AI learning coach closed loop — 27 文件，7 张 ORM 表 |
| `903409c` | refactor: migrate feishu client to official lark-oapi v1.6.0 SDK |
| `26b1032` | feat: neon ssl support, llm multi-provider, docs |
| `fc122f1` | refactor: switch LLM client to DeepSeek V4 Pro (OpenAI-compatible API) |
| `bbc92ed` | fix: merge card callbacks into webhook, add conversation state management |
| `68a28df` | fix: handle feishu card action callbacks (open_id extraction) |
| `2bf27a9` | fix: support feishu card callback payloads (dict-value compatibility) |
| `d77b02c` | fix: render profile prompt as card (build_profile_prompt_card) |
| `2afb8dc` | fix: dedupe feishu webhook retries (飞书重试去重) |
| `76a8134` | feat: customize profile prompt examples per domain |
| `b55a638` | fix: allow prompt-only LLM JSON calls (chat_json 空消息支持) |

---

## 二、项目结构

```
02总结知识助手/
├── app.py              FastAPI 入口 (lifespan)
├── config.py           配置管理 (Config.from_env)
├── requirements.txt    生产依赖 (lark-oapi + asyncpg + httpx)
├── render.yaml         Render 部署描述
├── .gitignore
├── data/
│   └── course_templates.json   4 课程模板 (Python/SQL/AI/六级英语)
├── scripts/
│   └── init_db.py              数据库建表 + 模板导入
├── server/
│   ├── scheduler.py            每小时推送调度器 (06:00-23:00)
│   ├── feishu/
│   │   ├── webhook.py          飞书 Webhook + 卡片回调 + 对话状态机
│   │   ├── card_builder.py     5 种飞书卡片 (欢迎/画像/计划/学习/状态)
│   │   ├── feishu_client.py    lark-oapi SDK 封装
│   │   └── router.py           7 种意图识别
│   ├── models/
│   │   ├── database.py         异步引擎 (Neon SSL)
│   │   └── schema.py           7 张 ORM 表
│   ├── services/
│   │   ├── profile_service.py  用户画像 + 成长指标
│   │   ├── template_service.py 模板查询 (六级英语 → 英语 兼容)
│   │   ├── plan_service.py     计划生成/滚动/重排
│   │   └── push_service.py     每日推送
│   └── llm/
│       ├── client.py           DeepSeek V4 Pro (OpenAI 兼容 + raise_for_status)
│       └── prompts.py          3 组 Prompt 模板
└── tests/
    └── test_feishu_webhook.py  12 tests PASS
```

---

## 三、数据模型

| 表 | 说明 | 状态 |
|------|------|------|
| users | 飞书 open_id 绑定 | ✅ |
| learning_profiles | 用户画像 (目标/基线/约束/反馈/成长指标) | ✅ |
| course_templates | 课程模板库 (4 条: Python/SQL/AI/六级英语) | ✅ 已导入 |
| learning_plans | 学习计划 (大纲 + 锁定单元) | ✅ |
| learning_units | 每日学习单元 (6 种 unit_type) | ✅ |
| checkins | 打卡记录 + 反馈信号 | ✅ |

### 模板兼容说明

数据库模板 domain 字段为 `"英语"`，代码层面使用 `"六级英语"`。`TemplateService.get_template` 内置了回退逻辑：先查 `"六级英语"`，未命中则查 `"英语"` 旧域名。`data/course_templates.json` 中已同步更新为新名称和真实六级备考内容（核心词汇 → 长难句 → 听力 → 阅读 → 翻译写作）。

---

## 四、对话流（完整）

```
用户操作                      事件                         响应
─────────────────────────────────────────────────────────────────────
/new_plan                 → im.message.receive_v1     → 欢迎卡片 [Python|SQL|AI|六级英语]
点击卡片 [🐍 Python]      → card.action.trigger       → 画像采集卡片 (含领域定制示例)
"想转行，零基础，午休20min"  → im.message.receive_v1     → LLM 提取画像 → 匹配模板 → 生成计划卡片
点击 [✅ 确认开始]         → card.action.trigger       → "计划已确认！明天开始推送"
"太难" / 点击 [😰 太难]    → feedback                  → 反馈响应 + 重排未来3天
"已掌握"                  → feedback                  → 标记完成 + 推进
/status                   → im.message.receive_v1     → 学习状态卡片 (连续天数/完成率等)
/help                     → im.message.receive_v1     → 功能列表
贴 URL                     → paste_link                → "视频摄取即将上线 (MVP-1)"
```

### 对话状态管理

`_pending_conversations` 字典存储 `{open_id: {state, domain, stage, timestamp}}`：

```
模板按钮点击 → 写入 pending[open_id] = {state: "collecting_profile", ...}
用户文字回复 → 弹出 pending，检测 state → 触发画像→计划流程
确认/取消 → 清理 pending
/new_plan → 清理旧 pending
```

### 事件去重

飞书 Webhook 在 3 秒内无响应时会重试，导致重复事件。`_is_duplicate_event` 按事件 ID / 消息 ID / 卡片动作键去重，TTL 600 秒。卡片按钮连续点击也通过 `_last_card_actions` 去重（同 open_id + action_value 只处理一次）。

---

## 五、飞书卡片规范

按钮 `value` 使用字典格式以保证飞书卡片回调兼容：

```json
{"tag": "button", "value": {"action": "tpl_Python_入门"}, ...}
{"tag": "button", "value": {"action": "completed"}, ...}
```

`_extract_action_value` 兼容三种回调格式：
- `action.value` 为 `{"action": "..."}` → 提取 `.action`
- `action.value` 为字符串 `"tpl_SQL_入门"` → 直接返回
- 根节点有 `action_value` → 直接返回

`_extract_open_id` 覆盖四种 open_id 来源：
- 消息事件 → `event.sender.sender_id.open_id`
- 卡片回调 → `event.operator.operator_id.open_id`
- 根节点 → `body.open_id`
- 根节点 operator → `body.operator.operator_id.open_id`

---

## 六、LLM 客户端

| 项目 | 值 |
|------|-----|
| 模型 | `deepseek-chat` (V4 Pro) |
| API 格式 | OpenAI-compatible (`/v1/chat/completions`) |
| System prompt | `messages[0].role = "system"` |
| 错误处理 | `response.raise_for_status()` (非 2xx 直接抛异常) |
| JSON 模式 | `chat_json()` 允许空 user_message，自动填 `"请按要求返回 JSON。"` |

---

## 七、部署清单

### 外部服务

| 服务 | 用途 | 状态 |
|------|------|------|
| Neon PostgreSQL | 数据库 (ap-southeast-1) | ✅ 已创建，4 模板已导入 |
| GitHub | 代码仓库 | ✅ https://github.com/liuw3070-spec/ai_coach |
| DeepSeek API | LLM (deepseek-chat) | ✅ key 已获取 |
| 飞书开放平台 | 机器人 App | ✅ App 已创建，权限已配置 |
| Render | 托管 FastAPI | 🔜 待部署 |

### Render 环境变量

| Key | 值 |
|-----|-----|
| `FEISHU_APP_ID` | `cli_aa9198f854b9dbdf` |
| `FEISHU_APP_SECRET` | `pUyzzmOXXV3cUrJQfhaAde5yIvTfpj8W` |
| `FEISHU_VERIFICATION_TOKEN` | **部署拿到域名后，飞书事件订阅验证获取** |
| `LLM_API_KEY` | `sk-bf5b209d692f4c2894f3c40b7f37b63d` |
| `LLM_BASE_URL` | `https://api.deepseek.com` |
| `LLM_MODEL` | `deepseek-chat` |
| `DATABASE_URL` | `postgresql+asyncpg://neondb_owner:npg_pbk3IuwlLs0c@ep-damp-boat-ao3uwrhu.c-2.ap-southeast-1.aws.neon.tech/neondb` |
| `ENV` | `prod` |

### 部署步骤

```
1. Render Dashboard → New Web Service → 连接 liuw3070-spec/ai_coach
2. 填入上方所有环境变量 → Deploy → 等待 3-5 分钟
3. 拿到域名: https://ai-coach-xxxx.onrender.com
4. 飞书开放平台 → 事件订阅 → 请求 URL:
   https://ai-coach-xxxx.onrender.com/feishu/webhook
5. 飞书验证后 → 复制 Verification Token → 填入 Render 环境变量
6. 飞书 App → 创建版本 → 发布
7. 飞书客户端搜索 "AI学习教练" → 发送 /new_plan 测试
```

---

## 八、选择记录

| 决策 | 结论 | 原因 |
|------|------|------|
| 部署 vs 本地 | Render Webhook 模式 | 需要卡片按钮交互回调，WebSocket 长连接不支持 |
| 飞书 SDK | lark-oapi 1.6.0 | 官方 Python SDK，token 管理 + 消息发送 + 事件接收 |
| LLM | DeepSeek V4 Pro (OpenAI 格式) | 用户选择，API 兼容层一次写好 |
| 数据库 | Neon PostgreSQL | 免费 0.5GB，无信用卡，serverless 自动扩缩 |
| 卡片按钮值格式 | `{"action": "..."}` 字典 | 飞书 SDK 兼容要求，`_extract_action_value` 兼容三种格式 |
| 课程领域 | 英语 → 六级英语 | 更精准的学习目标，备考场景更聚焦 |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-05-31 | MVP-0 代码完成，27 文件 1124 行，Neon 初始化，飞书 App 创建 |
| 2026-05-31 | 飞书 SDK 迁移至 lark-oapi 1.6.0，LLM 切换至 DeepSeek V4 Pro |
| 2026-05-31 | 卡片回调集成、对话状态管理、事件去重、画像采集卡片、六级英语模板、12 项测试 |
