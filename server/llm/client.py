import json
import httpx
from config import Config


class LLMClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._http = httpx.AsyncClient(timeout=120)
        self._base = cfg.llm_base_url.rstrip("/")
        # OpenRouter 用 Bearer token，Anthropic 用 x-api-key
        if "openrouter" in self._base or cfg.llm_api_key.startswith("sk-or-"):
            self._headers = {
                "Authorization": f"Bearer {cfg.llm_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://ai-coach.onrender.com",
                "X-Title": "AI Learning Coach",
            }
            self._messages_url = f"{self._base}/v1/messages"
        else:
            self._headers = {
                "x-api-key": cfg.llm_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            self._messages_url = f"{self._base}/v1/messages"

    async def chat(self, system_prompt: str, user_message: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        response = await self._http.post(
            self._messages_url,
            headers=self._headers,
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
        # Fallback: OpenAI-compatible format (choices[0].message.content)
        choices = data.get("choices", [])
        if choices and len(choices) > 0:
            return choices[0].get("message", {}).get("content", "")
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
