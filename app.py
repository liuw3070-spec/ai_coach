import asyncio
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from server.feishu.webhook import router as feishu_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    from config import Config
    from server.models import database as db_module
    from server.feishu.feishu_client import FeishuClient
    from server.llm.client import LLMClient

    cfg = Config.from_env()
    db_module.init_db(cfg)

    # 启动时验证数据库连接
    db_ok = await db_module.check_db_connection()
    if not db_ok:
        print("[startup] WARNING: Database connection check failed — data features unavailable")

    feishu_client = FeishuClient(
        app_id=cfg.feishu_app_id,
        app_secret=cfg.feishu_app_secret,
    )
    llm_client = LLMClient(cfg)

    application.state.cfg = cfg
    application.state.feishu = feishu_client
    application.state.llm = llm_client
    application.state.async_session = db_module.async_session

    from server.scheduler import run_scheduler
    task = asyncio.create_task(run_scheduler(db_module.async_session, llm_client, feishu_client, cfg))

    yield

    task.cancel()
    await feishu_client.close()
    await llm_client.close()


app = FastAPI(title="AI Learning Coach", version="0.1.0", lifespan=lifespan)
app.include_router(feishu_router, prefix="/feishu")


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
