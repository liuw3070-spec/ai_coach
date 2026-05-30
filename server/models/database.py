from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from config import Config

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
