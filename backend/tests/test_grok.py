"""Provider boundary tests: Grok stays disabled, factory routes correctly."""

from app.ai.providers.grok import GrokDisabledError, GrokIntegrationProvider


def test_grok_disabled_by_default():
    p = GrokIntegrationProvider(base_url="", api_key="", model="")
    assert p.health()["status"] == "coming_soon_disabled"
    try:
        from app.ai.providers.base import ChatMessage
        p.complete([ChatMessage(role="user", content="hi")])
    except GrokDisabledError:
        return
    raise AssertionError("disabled Grok provider completed a request")


def test_grok_build_context_shapes_handoff():
    p = GrokIntegrationProvider(base_url="", api_key="", model="")
    msgs = p.build_context("JD text here", "Resume text here", "prep")
    assert len(msgs) == 2
    assert "JD text here" in msgs[1].content
    assert "Never invent" in msgs[0].content


def test_factory_selects_grok_and_integrations_status(client, auth_headers, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "grok")
    get_settings.cache_clear()
    try:
        from app.ai.providers import get_llm_provider

        assert get_llm_provider().name == "grok"
    finally:
        get_settings.cache_clear()
    r = client.get("/api/integrations", headers=auth_headers)
    assert r.status_code == 200, r.text
    by_name = {p["name"]: p for p in r.json()["providers"]}
    assert by_name["grok"]["status"] == "coming_soon"
    assert by_name["grok"]["active"] is False
    assert by_name["ollama"]["name"] == "ollama"


def test_integrations_requires_auth(client):
    assert client.get("/api/integrations").status_code == 401
