import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from config import Config

logger = logging.getLogger(__name__)

engine = None
async_session: async_sessionmaker[AsyncSession] | None = None


def init_db(cfg: Config) -> None:
    global engine, async_session
    engine = create_async_engine(
        cfg.database_url,
        echo=(cfg.env == "dev"),
        connect_args={"ssl": "require"},  # Neon 强制 SSL
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    logger.info("Database engine created, session factory ready")


async def check_db_connection() -> bool:
    """Verify the database is reachable. Call after init_db during startup."""
    if async_session is None:
        logger.error("check_db_connection: async_session is None (init_db not called?)")
        return False
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connection verified")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
