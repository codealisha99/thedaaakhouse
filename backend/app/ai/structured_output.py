"""Helpers to parse provider output into Pydantic models with repair retries."""

import json

from pydantic import BaseModel, ValidationError


def parse_structured(text: str, model: type[BaseModel]) -> BaseModel:
    """Parse JSON from LLM text into `model`. Raises ValueError with detail."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # strip fenced code blocks
        cleaned = cleaned.strip("`")
        cleaned = cleaned[cleaned.find("\n") + 1 :] if "\n" in cleaned else cleaned
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM output was not valid JSON: {e}") from e
    try:
        return model.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"LLM output failed schema validation: {e}") from e
