"""Any OpenAI-compatible chat-completions endpoint (OpenAI, vLLM, LM Studio...)."""

import httpx

from app.ai.providers.base import ChatMessage, LLMProvider, LLMResponse


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    def complete(self, messages: list[ChatMessage], **kwargs) -> LLMResponse:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        try:
            r = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout_s,
            )
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            return LLMResponse(text=text, model=self.model, provider=self.name)
        except Exception as e:
            raise RuntimeError(f"openai-compatible completion failed: {e}") from e
