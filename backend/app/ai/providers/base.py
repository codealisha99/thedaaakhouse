"""LLM provider interface. App code depends on this, never on Ollama/OpenAI."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    role: str  # system | user | assistant
    content: str


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    metadata: dict = field(default_factory=dict)


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, messages: list[ChatMessage], **kwargs) -> LLMResponse:
        """Single completion. Must not raise provider-specific errors outward."""
        ...

    def health(self) -> dict:
        return {"provider": self.name, "configured": True}
