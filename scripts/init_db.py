"""初始化数据库表 + 导入课程模板。运行: python scripts/init_db.py"""
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from server.models.schema import Base, CourseTemplate


async def init():
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    template_path = os.path.join(os.path.dirname(__file__), "..", "data", "course_templates.json")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            templates = json.load(f)
        async with AsyncSession(engine) as session:
            for t in templates:
                existing = await session.execute(
                    select(CourseTemplate).where(
                        CourseTemplate.domain == t["domain"],
                        CourseTemplate.stage == t["stage"],
                    )
                )
                if not existing.scalar_one_or_none():
                    session.add(CourseTemplate(**t))
            await session.commit()
        print(f"Imported {len(templates)} course templates.")

    print("Database initialized.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init())
