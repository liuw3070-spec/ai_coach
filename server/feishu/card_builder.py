def build_daily_learning_card(unit: dict) -> dict:
    content = unit.get("content", {})
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
                    {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 完成"}, "type": "primary", "value": {"action": "completed"}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "😰 太难"}, "type": "default", "value": {"action": "too_hard"}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "😴 太简单"}, "type": "default", "value": {"action": "too_easy"}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "⏰ 没时间"}, "type": "default", "value": {"action": "no_time"}},
                ]
            }
        ]
    }


def build_status_card(metrics: dict, profile: dict) -> dict:
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
                    {"tag": "button", "text": {"tag": "plain_text", "content": "📋 查看完整笔记"}, "type": "default", "value": {"action": "view_notes"}},
                ]
            }
        ]
    }


def build_welcome_card(domains: list[str]) -> dict:
    domain_buttons = []
    emoji_map = {"Python": "🐍", "SQL": "🗄️", "AI": "🤖", "六级英语": "🇬🇧"}
    for d in domains:
        emoji = emoji_map.get(d, "📚")
        domain_buttons.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": f"{emoji} {d}"},
            "type": "primary",
            "value": {"action": f"tpl_{d}_入门"}
        })

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
            {"tag": "action", "actions": domain_buttons},
            {"tag": "div", "text": {"tag": "lark_md", "content": "也可以直接告诉我你想学什么和你的目标 :)"}},
        ]
    }


def build_profile_prompt_card(domain: str, stage: str) -> dict:
    examples = {
        "Python": "想提升 Python 技能，目前只会基础语法，每天午休 20 分钟可以学习",
        "SQL": "想准备数据分析岗位，SQL 只会简单 SELECT，每天晚上 25 分钟可以练习",
        "AI": "想系统了解 AI 产品和大模型应用，目前只知道基础概念，每天通勤 20 分钟学习",
        "六级英语": "想备考英语六级，目前词汇量一般，听力比较弱，每天晚上 30 分钟可以学习",
    }
    example = examples.get(domain, f"想学习 {domain}，目前是零基础，每天 20 分钟可以学习")

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📋 学习画像采集"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"已选择：**{domain} · {stage}**\n\n"
                        "在生成计划前，请简单告诉我：\n"
                        "1. 学习目标：转行 / 提升 / 兴趣 / 面试\n"
                        "2. 当前基础：零基础 / 入门 / 中级\n"
                        "3. 学习时间：每天什么时候？多少分钟？"
                    ),
                },
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        "**示例回复**\n"
                        f"{example}"
                    ),
                },
            },
        ],
    }


def build_plan_confirm_card(outline: list[dict], first_units: list[dict]) -> dict:
    weeks_text = "\n".join(f"📅 第{w['week']}周：{w['theme']}" for w in outline)
    return {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": "📋 你的学习计划"}, "template": "blue"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**4周大纲**\n{weeks_text}\n\n🚀 明天开始推送每日学习单元！"}},
            {
                "tag": "action",
                "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 确认开始"}, "type": "primary", "value": {"action": "confirm_plan"}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "🔄 换个方向"}, "type": "default", "value": {"action": "retry_plan"}},
                ]
            }
        ]
    }
