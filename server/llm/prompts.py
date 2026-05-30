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
