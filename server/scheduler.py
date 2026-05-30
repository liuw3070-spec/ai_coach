import asyncio
from datetime import datetime
from sqlalchemy import select
from server.models.schema import User, LearningPlan


async def daily_push_job(db_session_factory, llm_client, feishu_client):
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
    while True:
        now = datetime.now()
        hour = now.hour
        if 6 <= hour <= 23:
            await daily_push_job(db_session_factory, llm_client, feishu_client)
        await asyncio.sleep(3600)
