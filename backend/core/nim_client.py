import time
from langchain_openai import ChatOpenAI
from typing import Optional
from backend.config.settings import settings
from backend.core.model_registry import model_registry
from loguru import logger


# Per-session sticky model assignment (model_key -> model_name)
_session_models: dict[str, str] = {}


def get_nim_llm(model_key: str, temperature: Optional[float] = None) -> ChatOpenAI:
    global _session_models

    # If model_key already has a sticky assignment, reuse it
    model_name = _session_models.get(model_key)
    if not model_name:
        model_name = settings.nim_models.get(model_key, "")
        if not model_name:
            tier = settings.nim_model_tiers.get(model_key, "capable")
            model_name = model_registry.select_model(tier)
        _session_models[model_key] = model_name  # sticky once selected

    temp = temperature if temperature is not None else settings.agent_temperature
    logger.debug(f"Creating NIM LLM: model_key={model_key}, model_name={model_name}, temperature={temp}")
    return SmartLLM(
        model=model_name,
        model_key=model_key,
        openai_api_key=settings.nvidia_nim_api_key,
        openai_api_base=settings.nvidia_nim_base_url,
        temperature=temp,
        max_tokens=4096,
        max_retries=5,
        request_timeout=120,
        model_kwargs={},
    )


def clear_session_models():
    global _session_models
    _session_models.clear()


class SmartLLM(ChatOpenAI):
    """Wrapper that tracks per-model latency and keeps max_tokens."""

    model_key: str = ""

    def __init__(self, model_key: str = "", **kwargs):
        kwargs.pop("max_completion_tokens", None)
        super().__init__(**kwargs)
        self.model_key = model_key

    def _get_request_payload(self, *args, **kwargs) -> dict:
        # LangChain renames max_tokens -> max_completion_tokens which NIM rejects
        payload = super()._get_request_payload(*args, **kwargs)
        if "max_completion_tokens" in payload:
            payload["max_tokens"] = payload.pop("max_completion_tokens")
        return payload

    async def _astream(self, *args, **kwargs):
        start = time.time()
        try:
            async for chunk in super()._astream(*args, **kwargs):
                yield chunk
            latency = time.time() - start
            model_registry.record(self.model, latency, success=True)
        except Exception:
            latency = time.time() - start
            model_registry.record(self.model, latency, success=False)
            raise

    async def _agenerate(self, *args, **kwargs):
        start = time.time()
        try:
            result = await super()._agenerate(*args, **kwargs)
            latency = time.time() - start
            model_registry.record(self.model, latency, success=True)
            return result
        except Exception:
            latency = time.time() - start
            model_registry.record(self.model, latency, success=False)
            raise
