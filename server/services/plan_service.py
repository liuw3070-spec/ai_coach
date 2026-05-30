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
