import time
import json
import httpx
from config import Config


class FeishuClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._token: str | None = None
        self._token_expires_at: float = 0
        self._http = httpx.AsyncClient()

    async def _get_access_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        response = await self._http.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.cfg.feishu_app_id, "app_secret": self.cfg.feishu_app_secret},
        )
        data = response.json()
        self._token = data["tenant_access_token"]
        self._token_expires_at = time.time() + data.get("expire", 7200)
        return self._token

    async def _post(self, url: str, body: dict) -> dict:
        token = await self._get_access_token()
        response = await self._http.post(
            url, json=body, headers={"Authorization": f"Bearer {token}"},
        )
        return response.json()

    async def send_message(self, open_id: str, content: str) -> dict:
        return await self._post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            {"receive_id": open_id, "msg_type": "text", "content": json.dumps({"text": content})},
        )

    async def send_card(self, open_id: str, card: dict) -> dict:
        return await self._post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            {"receive_id": open_id, "msg_type": "interactive", "content": json.dumps(card)},
        )

    async def reply_message(self, message_id: str, content: str) -> dict:
        return await self._post(
            f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
            {"content": json.dumps({"text": content}), "msg_type": "text"},
        )

    async def close(self):
        await self._http.aclose()
