"""Ollama provider for local development (http://localhost:11434)."""

import httpx

from app.ai.providers.base import ChatMessage, LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout_s: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def complete(self, messages: list[ChatMessage], **kwargs) -> LLMResponse:
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout_s)
            r.raise_for_status()
            data = r.json()
            text = data.get("message", {}).get("content", "")
            return LLMResponse(text=text, model=self.model, provider=self.name)
        except Exception as e:  # normalize outward-facing errors
            raise RuntimeError(f"ollama completion failed: {e}") from e

    def health(self) -> dict:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            return {"provider": self.name, "reachable": r.status_code == 200, "model": self.model}
        except Exception as e:
            return {"provider": self.name, "reachable": False, "error": str(e)}
