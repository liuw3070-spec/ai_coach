import json
import httpx
from config import Config


class LLMClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._http = httpx.AsyncClient(timeout=120)
        self._base = cfg.llm_base_url.rstrip("/")
        self._url = f"{self._base}/v1/chat/completions"
        self._headers = {
            "Authorization": f"Bearer {cfg.llm_api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        response = await self._http.post(
            self._url,
            headers=self._headers,
            json={
                "model": self.cfg.llm_model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if choices and len(choices) > 0:
            return choices[0].get("message", {}).get("content", "")
        return ""

    async def chat_json(self, system_prompt: str, user_message: str = "") -> dict:
        text = await self.chat(system_prompt, user_message or "请按要求返回 JSON。", temperature=0.3)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())

    async def close(self):
        await self._http.aclose()
