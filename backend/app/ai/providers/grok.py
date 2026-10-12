"""Grok (xAI) integration boundary — DISABLED placeholder.

xAI exposes an OpenAI-compatible chat-completions API, so the provider
subclasses OpenAICompatibleProvider. Nothing here runs unless explicitly
enabled: `complete()` refuses while disabled, so core flows (tailor, ATS,
learning, arena) can never depend on it.

Enablement checklist (for later, not now):
  LLM_PROVIDER=grok, GROK_ENABLED=true, GROK_API_KEY set, model chosen.
"""

from app.ai.providers.base import ChatMessage, LLMResponse
from app.ai.providers.openai_compatible import OpenAICompatibleProvider


class GrokDisabledError(RuntimeError):
    pass


class GrokIntegrationProvider(OpenAICompatibleProvider):
    """Adapter for xAI Grok. Disabled by default."""

    name = "grok"

    def __init__(self, base_url: str, api_key: str, model: str,
                 enabled: bool = False, timeout_s: float = 120.0):
        super().__init__(base_url or "https://api.x.ai/v1", api_key, model or "grok-3",
                         timeout_s=timeout_s)
        self.enabled = enabled and bool(api_key)

    def health(self) -> dict:
        return {"provider": self.name, "configured": self.enabled,
                "status": "enabled" if self.enabled else "coming_soon_disabled"}

    def complete(self, messages: list[ChatMessage], **kwargs) -> LLMResponse:
        if not self.enabled:
            raise GrokDisabledError(
                "Grok integration is disabled. Set LLM_PROVIDER=grok, "
                "GROK_ENABLED=true, and GROK_API_KEY to enable it.")
        return super().complete(messages, **kwargs)

    def build_context(self, job_description: str, tailored_resume: str,
                      prep_context: str = "") -> list[ChatMessage]:
        """Controlled handoff shape for future use: JD + resume + prep context."""
        return [
            ChatMessage(role="system", content=(
                "You assist with job applications using only the provided materials. "
                "Never invent experience, skills, or achievements.")),
            ChatMessage(role="user", content=(
                f"JOB DESCRIPTION:\n{job_description[:6000]}\n\n"
                f"TAILORED RESUME:\n{tailored_resume[:6000]}\n\n"
                f"PREPARATION CONTEXT:\n{prep_context[:2000]}")),
        ]
