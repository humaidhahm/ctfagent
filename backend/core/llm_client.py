import threading
from collections.abc import AsyncIterator
from typing import Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from loguru import logger

from backend.config.settings import settings
from backend.core.model_registry import model_registry


class KeyPool:
    def __init__(self, keys: list[str]):
        self.keys = list(dict.fromkeys(keys))
        self._current = 0
        self._lock = threading.Lock()

    def candidates(self) -> list[str]:
        with self._lock:
            if not self.keys:
                return []

            return (
                self.keys[self._current:]
                + self.keys[:self._current]
            )

    def mark_success(self, key: str) -> None:
        with self._lock:
            self._current = self.keys.index(key)

    def mark_failed(self, key: str) -> None:
        with self._lock:
            index = self.keys.index(key)
            self._current = (index + 1) % len(self.keys)


_google_pool = KeyPool(settings.configured_google_keys)

_pools = {
    "nim": KeyPool(settings.nim_keys),
    "gemma": _google_pool,
    "gemini": _google_pool,
}

_session_models: dict[str, str] = {}


def _status_code(exc: Exception) -> Optional[int]:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status

    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def _should_rotate_key(exc: Exception) -> bool:
    status = _status_code(exc)

    if status is None:
        # Timeouts, connection failures and SDK transport errors.
        return True

    # Authentication, quota/rate limits and server errors.
    return status in {401, 403, 408, 409, 429} or status >= 500


def _nim_model(model_key: str) -> str:
    model = _session_models.get(model_key)

    if not model:
        model = settings.nim_models.get(model_key, "")

        if not model:
            tier = settings.nim_model_tiers.get(model_key, "capable")
            model = model_registry.select_model(tier)

        _session_models[model_key] = model

    return model


def _build_client(
    provider: str,
    api_key: str,
    model_key: str,
    temperature: float,
):
    if provider == "nim":
        return ChatOpenAI(
            model=_nim_model(model_key),
            api_key=api_key,
            base_url=settings.nvidia_nim_base_url,
            temperature=temperature,
            max_tokens=4096,
            max_retries=0,  # Rotation handles retries
            timeout=120,
        )

    if provider == "gemma":
        return ChatGoogleGenerativeAI(
            model=settings.gemma_model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=4096,
            max_retries=0,
            timeout=120,
        )

    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=4096,
            max_retries=0,
            timeout=120,
        )

    raise ValueError(f"Unknown LLM provider: {provider}")


class RotatingLLM:
    def __init__(
        self,
        provider: str,
        model_key: str,
        temperature: float,
    ):
        self.provider = provider
        self.model_key = model_key
        self.temperature = temperature
        self.pool = _pools[provider]

        if not self.pool.keys:
            raise RuntimeError(
                f"No API keys configured for provider '{provider}'"
            )

    async def ainvoke(
        self,
        input: Any,
        config: Any = None,
        **kwargs,
    ):
        last_error: Optional[Exception] = None

        for api_key in self.pool.candidates():
            try:
                client = _build_client(
                    self.provider,
                    api_key,
                    self.model_key,
                    self.temperature,
                )

                result = await client.ainvoke(
                    input,
                    config=config,
                    **kwargs,
                )

                self.pool.mark_success(api_key)
                return result

            except Exception as exc:
                last_error = exc

                if not _should_rotate_key(exc):
                    raise

                logger.warning(
                    "{} API key failed; rotating to next key: {}",
                    self.provider,
                    type(exc).__name__,
                )
                self.pool.mark_failed(api_key)

        raise RuntimeError(
            f"All {self.provider} API keys failed"
        ) from last_error

    async def astream(
        self,
        input: Any,
        config: Any = None,
        **kwargs,
    ) -> AsyncIterator[Any]:
        last_error: Optional[Exception] = None

        for api_key in self.pool.candidates():
            emitted_output = False

            try:
                client = _build_client(
                    self.provider,
                    api_key,
                    self.model_key,
                    self.temperature,
                )

                async for chunk in client.astream(
                    input,
                    config=config,
                    **kwargs,
                ):
                    emitted_output = True
                    yield chunk

                self.pool.mark_success(api_key)
                return

            except Exception as exc:
                last_error = exc

                # Restarting after output was emitted would duplicate text.
                if emitted_output or not _should_rotate_key(exc):
                    raise

                logger.warning(
                    "{} streaming key failed; rotating: {}",
                    self.provider,
                    type(exc).__name__,
                )
                self.pool.mark_failed(api_key)

        raise RuntimeError(
            f"All {self.provider} API keys failed"
        ) from last_error


def get_llm(
    model_key: str,
    temperature: Optional[float] = None,
) -> RotatingLLM:
    provider = settings.llm_provider.strip().lower()

    if provider not in {"nim", "gemma", "gemini"}:
        raise ValueError(
            "LLM_PROVIDER must be nim, gemma, or gemini"
        )

    return RotatingLLM(
        provider=provider,
        model_key=model_key,
        temperature=(
            temperature
            if temperature is not None
            else settings.agent_temperature
        ),
    )


def clear_session_models() -> None:
    _session_models.clear()
