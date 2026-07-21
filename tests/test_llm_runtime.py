import os

from backend.config.settings import settings
from backend.core import llm_client
from run import configured_key_counts


def test_configured_key_counts_deduplicates_key_pools():
    content = (
        "LLM_PROVIDER=gemini\n"
        "GOOGLE_API_KEYS=a,b,a\n"
        "NVIDIA_NIM_API_KEYS=nv1,nv2,nv1\n"
    )

    assert configured_key_counts(content) == {"google": 2, "nim": 2}


def test_default_google_request_interval_is_one_second():
    assert settings.google_min_request_interval_seconds == 1.0


def test_refresh_llm_runtime_reloads_google_keys(monkeypatch):
    original_provider = settings.llm_provider
    original_google_keys = settings.google_api_keys
    original_google_env = os.environ.get("GOOGLE_API_KEYS")
    original_provider_env = os.environ.get("LLM_PROVIDER")

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEYS", "key-a,key-b,key-a")

    try:
        llm_client.refresh_llm_runtime()

        assert settings.llm_provider == "gemini"
        assert settings.configured_google_keys == ["key-a", "key-b"]
        assert llm_client._pools["gemini"].keys == ["key-a", "key-b"]
    finally:
        if original_google_env is None:
            monkeypatch.delenv("GOOGLE_API_KEYS", raising=False)
        else:
            monkeypatch.setenv("GOOGLE_API_KEYS", original_google_env)

        if original_provider_env is None:
            monkeypatch.delenv("LLM_PROVIDER", raising=False)
        else:
            monkeypatch.setenv("LLM_PROVIDER", original_provider_env)

        settings.llm_provider = original_provider
        settings.google_api_keys = original_google_keys
        llm_client.refresh_llm_runtime()
