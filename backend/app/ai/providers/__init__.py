"""Provider factory — selected by LLM_PROVIDER env var."""

from app.ai.providers.base import LLMProvider
from app.ai.providers.grok import GrokIntegrationProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.core.config import get_settings


def get_llm_provider() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "openai_compatible":
        return OpenAICompatibleProvider(
            base_url=s.openai_compatible_base_url,
            api_key=s.openai_compatible_api_key,
            model=s.openai_compatible_model,
        )
    if s.llm_provider == "grok":
        return GrokIntegrationProvider(
            base_url=s.grok_base_url,
            api_key=s.grok_api_key,
            model=s.grok_model,
            enabled=s.grok_enabled,
        )
    return OllamaProvider(base_url=s.ollama_base_url, model=s.ollama_model)


def provider_status() -> list[dict]:
    """Status of every known provider for the Integrations UI."""
    s = get_settings()
    ollama = OllamaProvider(base_url=s.ollama_base_url, model=s.ollama_model)
    grok = GrokIntegrationProvider(base_url=s.grok_base_url, api_key=s.grok_api_key,
                                   model=s.grok_model, enabled=s.grok_enabled)
    return [
        {"name": "ollama", "active": s.llm_provider == "ollama",
         "model": s.ollama_model, "status": "ready" if ollama.health().get("reachable") else "unreachable"},
        {"name": "openai_compatible", "active": s.llm_provider == "openai_compatible",
         "model": s.openai_compatible_model,
         "status": "configured" if s.openai_compatible_api_key else "no_api_key"},
        {"name": "grok", "active": False, "model": s.grok_model,
         "status": "coming_soon", "note": "Disabled placeholder. Nothing routes here."},
    ]
