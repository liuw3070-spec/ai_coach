import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .router import detect_intent
from .card_builder import (
    build_welcome_card, build_daily_learning_card,
    build_status_card, build_plan_confirm_card, build_profile_prompt_card,
)

router = APIRouter()

# 对话状态：open_id → {state, domain, stage, timestamp}
_pending_conversations: dict[str, dict] = {}
_last_card_actions: dict[str, str] = {}


@router.post("/webhook")
async def feishu_webhook(request: Request):
    body = await request.json()
    print(f"feishu_webhook body={json.dumps(body, ensure_ascii=False)[:2000]}")

    # URL 验证
    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body["challenge"]})

    feishu = getattr(request.app.state, "feishu", None)
    llm = getattr(request.app.state, "llm", None)
    if not feishu or not llm:
        return JSONResponse({"code": 0})

    event_type = body.get("header", {}).get("event_type", "")
    event = body.get("event", {})
    open_id = _extract_open_id(body, event)

    if event_type == "im.message.receive_v1":
        return await _handle_message(event, open_id, feishu, llm, request)

    if event_type == "card.action.trigger":
        return await _handle_card_action(event, open_id, feishu, llm, request)

    # 飞书“回调配置”里的卡片回传可能没有 header.event_type，action 在根节点。
    if body.get("action") or body.get("action_value"):
        return await _handle_card_action(body, open_id, feishu, llm, request)

    return JSONResponse({"code": 0})


# ── 消息处理 ──

async def _handle_message(event, open_id, feishu, llm, request):
    message = event.get("message", {})
    content_str = message.get("content", "{}")

    try:
        msg = json.loads(content_str)
        text = msg.get("text", "")
    except json.JSONDecodeError:
        text = content_str

    intent, payload = detect_intent(text)

    # 检查是否有待处理的对话状态
    pending = _pending_conversations.pop(open_id, None)

    if intent == "new_plan":
        _pending_conversations.pop(open_id, None)
        await _handle_new_plan(open_id, feishu)

    elif intent == "status":
        await _handle_status(open_id, feishu, llm, request)

    elif intent == "feedback":
        await _handle_feedback(open_id, payload, feishu, llm, request)

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

    elif pending and pending["state"] == "collecting_profile":
        # 模板已选，用户回复了画像信息 → 生成计划
        await _handle_profile_collected(open_id, text, pending, feishu, llm, request)

    else:
        await feishu.send_message(open_id, "收到！发送 /new_plan 创建学习计划，或 /help 查看功能列表。")

    return JSONResponse({"code": 0})


# ── 卡片按钮回调 ──

async def _handle_card_action(event, open_id, feishu, llm, request):
    if not open_id:
        open_id = _extract_open_id(event, event)
    action_value = _extract_action_value(event)
    print(f"card.action.trigger open_id={open_id} action_value={action_value}")

    if not open_id:
        print(f"card.action.trigger missing open_id event={json.dumps(event, ensure_ascii=False)[:2000]}")
        return JSONResponse({"code": 0})

    if action_value and action_value.startswith("tpl_"):
        parts = action_value.replace("tpl_", "").split("_")
        domain = parts[0]
        stage = parts[1] if len(parts) > 1 else "入门"
        action_key = f"{open_id}:{action_value}"
        if _last_card_actions.get(open_id) == action_key:
            return JSONResponse({"code": 0})
        _last_card_actions[open_id] = action_key

        # 存储对话状态
        _pending_conversations[open_id] = {
            "state": "collecting_profile",
            "domain": domain,
            "stage": stage,
        }

        await feishu.send_card(open_id, build_profile_prompt_card(domain, stage))

    elif action_value == "confirm_plan":
        _pending_conversations.pop(open_id, None)
        await feishu.send_message(open_id, "🎉 计划已确认！明天开始推送学习单元。准备好了吗？")

    elif action_value == "retry_plan":
        await _handle_new_plan(open_id, feishu)

    elif action_value in ("completed", "too_hard", "too_easy", "no_time", "interested", "not_interested", "mastered"):
        await _handle_feedback(open_id, action_value, feishu, llm, request)

    elif action_value == "view_notes":
        await feishu.send_message(open_id, "📝 完整笔记功能将在后续版本中开放。")

    return JSONResponse({"code": 0})


def _extract_action_value(event: dict) -> str:
    """兼容飞书卡片回调的多种 action value 结构。"""
    action = event.get("action") or {}
    value = action.get("value") or event.get("action_value") or ""

    if isinstance(value, dict):
        return (
            value.get("action")
            or value.get("value")
            or value.get("key")
            or value.get("tag")
            or ""
        )

    if isinstance(value, str):
        return value

    return action.get("tag", "") if isinstance(action.get("tag"), str) else ""


def _extract_open_id(body: dict, event: dict | None = None) -> str:
    event = event or {}

    candidates = [
        event.get("sender", {}).get("sender_id", {}),
        event.get("operator", {}).get("operator_id", {}),
        event.get("operator", {}),
        body.get("sender", {}).get("sender_id", {}),
        body.get("operator", {}).get("operator_id", {}),
        body.get("operator", {}),
    ]

    for candidate in candidates:
        if isinstance(candidate, dict):
            for key in ("open_id", "user_id", "union_id"):
                value = candidate.get(key)
                if value:
                    return value

    for key in ("open_id", "user_id", "operator_id"):
        value = body.get(key) or event.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            for nested_key in ("open_id", "user_id", "union_id"):
                nested_value = value.get(nested_key)
                if nested_value:
                    return nested_value

    return ""


# ── 处理函数 ──

async def _handle_new_plan(open_id: str, feishu):
    await feishu.send_card(open_id, build_welcome_card(["Python", "SQL", "AI", "六级英语"]))


async def _handle_profile_collected(open_id: str, text: str, pending: dict, feishu, llm, request):
    """用户回复了画像信息后，提取画像 → 匹配模板 → 生成计划"""
    domain = pending["domain"]
    stage = pending.get("stage", "入门")

    await feishu.send_message(open_id, f"⏳ 正在分析你的学习画像，生成个性化计划...")

    try:
        from server.services.profile_service import ProfileService
        from server.services.template_service import TemplateService
        from server.services.plan_service import PlanService

        async with request.app.state.async_session() as db:
            # 1. 提取用户画像
            profile_svc = ProfileService(db, llm)
            profile = await profile_svc.create_profile_from_dialog(open_id, [text])

            # 2. 获取课程模板
            template_svc = TemplateService(db)
            template = await template_svc.get_template(domain, stage)
            if not template:
                await feishu.send_message(open_id, f"抱歉，{domain}·{stage} 课程模板暂未就绪。")
                return

            # 3. 生成个性化计划
            plan_svc = PlanService(db, llm)
            user = await profile_svc.get_user(open_id)
            plan = await plan_svc.generate_plan(template, profile, user.id)

            # 4. 推送确认卡片
            await feishu.send_card(open_id, build_plan_confirm_card(
                outline=plan.outline,
                first_units=plan.locked_units,
            ))

    except Exception as e:
        print(f"Profile/plan generation error: {e}")
        await feishu.send_message(open_id, "生成计划时出了点问题，请稍后再试或发送 /new_plan 重新开始。")


async def _handle_feedback(open_id: str, feedback: str, feishu, llm, request):
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

    try:
        from server.services.profile_service import ProfileService
        from server.services.plan_service import PlanService

        async with request.app.state.async_session() as db:
            profile_svc = ProfileService(db, llm)
            await profile_svc.update_feedback(open_id, feedback)

            if feedback in ("completed", "mastered"):
                await profile_svc.update_growth_metrics(open_id)

            if feedback in ("too_hard", "too_easy", "not_interested", "mastered", "no_time"):
                plan_svc = PlanService(db, llm)
                profile = await profile_svc.get_profile(open_id)
                user = await profile_svc.get_user(open_id)
                if user and profile:
                    plan = await plan_svc.get_active_plan(user.id)
                    if plan:
                        await plan_svc.rebalance_on_feedback(plan, profile, feedback)
    except Exception as e:
        print(f"Feedback processing error: {e}")


async def _handle_status(open_id: str, feishu, llm, request):
    try:
        from server.services.profile_service import ProfileService
        async with request.app.state.async_session() as db:
            profile_svc = ProfileService(db, llm)
            metrics = await profile_svc.update_growth_metrics(open_id)
            profile = await profile_svc.get_profile(open_id)
            await feishu.send_card(open_id, build_status_card(
                metrics=metrics,
                profile={"domains": profile.domains if profile else []}
            ))
    except Exception as e:
        print(f"Status error: {e}")
        await feishu.send_message(open_id, "获取学习状态时出了点问题，请稍后再试。")
