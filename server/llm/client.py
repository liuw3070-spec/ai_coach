import json
import httpx
from config import Config


class LLMClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._http = httpx.AsyncClient(timeout=120)

    async def chat(self, system_prompt: str, user_message: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        response = await self._http.post(
            f"{self.cfg.llm_base_url}/v1/messages",
            headers={
                "x-api-key": self.cfg.llm_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.cfg.llm_model,
                "max_tokens": max_tokens,
                "system": [{"type": "text", "text": system_prompt}],
                "messages": [{"role": "user", "content": user_message}],
                "temperature": temperature,
            },
        )
        data = response.json()
        content = data.get("content", [])
        if content and len(content) > 0:
            return content[0].get("text", "")
        return ""

    async def chat_json(self, system_prompt: str, user_message: str) -> dict:
        text = await self.chat(system_prompt, user_message, temperature=0.3)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())

    async def close(self):
        await self._http.aclose()
