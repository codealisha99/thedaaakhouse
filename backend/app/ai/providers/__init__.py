"""Provider factory — selected by LLM_PROVIDER env var."""

from app.ai.providers.base import LLMProvider
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
    return OllamaProvider(base_url=s.ollama_base_url, model=s.ollama_model)
