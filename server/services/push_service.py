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
