from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from server.models.schema import User, LearningProfile
from server.llm.client import LLMClient
from server.llm.prompts import PROFILE_EXTRACTION
from datetime import date, timedelta
from collections import Counter


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
        from server.models.schema import Checkin
        user = await self.get_user(open_id)
        if not user:
            return {}

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

        days_passed = max((today - week_start).days + 1, 1)
        weekly_rate = round(week_completed / days_passed * 100, 1)

        unit_ids = [c.unit_id for c in checkins if c.feedback == "too_hard"]
        weak_unit_ids = [uid for uid, count in Counter(unit_ids).items() if count >= 2]

        metrics = {
            "streak": streak,
            "total_completed": total,
            "mastered": mastered,
            "weak_points": weak_unit_ids,
            "weekly_rate": weekly_rate,
        }
        profile = await self.get_profile(open_id)
        if profile:
            profile.growth_metrics = metrics
            await self.db.commit()
        return metrics
