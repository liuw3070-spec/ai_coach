import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    feishu_app_id: str
    feishu_app_secret: str
    feishu_verification_token: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    database_url: str
    redis_url: str
    env: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            feishu_app_id=os.environ["FEISHU_APP_ID"],
            feishu_app_secret=os.environ["FEISHU_APP_SECRET"],
            feishu_verification_token=os.environ["FEISHU_VERIFICATION_TOKEN"],
            llm_api_key=os.environ["LLM_API_KEY"],
            llm_base_url=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:15721"),
            llm_model=os.environ.get("LLM_MODEL", "claude-sonnet-4-6[1M]"),
            database_url=os.environ["DATABASE_URL"],
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            env=os.environ.get("ENV", "dev"),
        )
