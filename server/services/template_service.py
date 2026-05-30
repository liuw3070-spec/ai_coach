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
