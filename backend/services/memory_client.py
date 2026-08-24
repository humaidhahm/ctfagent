from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx

from backend.config.settings import settings


class MemoryServiceError(RuntimeError):
    """A non-fatal failure while communicating with the memory service."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        kind: str = "upstream",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.kind = kind


class MemoryClient:
    """Small async client for the memory service HTTP API."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        enabled: bool | None = None,
        api_token: str | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or settings.memory_service_url).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.memory_timeout_seconds
        self.enabled = enabled if enabled is not None else settings.memory_enabled
        self.api_token = api_token if api_token is not None else settings.memory_api_token
        self._http_client = http_client

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise MemoryServiceError(
                "Memory service is disabled",
                kind="disabled",
            )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        self._ensure_enabled()
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        try:
            if self._http_client is not None:
                response = await self._http_client.request(
                    method, url, timeout=self.timeout, headers=headers, **kwargs
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            try:
                return response.json()
            except ValueError as exc:
                raise MemoryServiceError(
                    "Memory service returned invalid JSON", kind="invalid_response"
                ) from exc
        except MemoryServiceError:
            raise
        except httpx.TimeoutException as exc:
            raise MemoryServiceError(
                "Memory service request timed out", kind="timeout"
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise MemoryServiceError(
                f"Memory service returned HTTP {status_code}",
                status_code=status_code,
                kind="http_error",
            ) from exc
        except httpx.HTTPError as exc:
            raise MemoryServiceError(
                "Memory service is unavailable", kind="unavailable"
            ) from exc
        except Exception as exc:
            raise MemoryServiceError(
                "Memory service request failed", kind="unavailable"
            ) from exc

    async def health(self) -> dict[str, Any]:
        result = await self._request("GET", "/mcp")
        if not isinstance(result, Mapping):
            raise MemoryServiceError(
                "Memory service returned an unexpected health response",
                kind="invalid_response",
            )
        return dict(result)

    async def search_writeups(
        self,
        query: str,
        domain: str | None = None,
        difficulty: str | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "offset": offset,
        }
        if domain is not None:
            params["domain"] = domain
        if difficulty is not None:
            params["difficulty"] = difficulty
        result = await self._request("GET", "/mcp/writeups", params=params)
        if not isinstance(result, Mapping):
            raise MemoryServiceError(
                "Memory service returned an unexpected search response",
                kind="invalid_response",
            )
        return dict(result)

    async def get_writeup(self, id: int | str) -> dict[str, Any]:
        result = await self._request("GET", f"/mcp/writeups/{quote(str(id), safe='')}" )
        if not isinstance(result, Mapping):
            raise MemoryServiceError(
                "Memory service returned an unexpected writeup response",
                kind="invalid_response",
            )
        return dict(result)

    async def fetch_reference(self, url: str) -> dict[str, Any]:
        result = await self._request("POST", "/mcp/references", json={"url": url})
        if not isinstance(result, Mapping):
            raise MemoryServiceError(
                "Memory service returned an unexpected reference response",
                kind="invalid_response",
            )
        return dict(result)
    async def call_tool(self, name: str, arguments: Mapping[str, Any] | None = None) -> Any:
        """Call a memory-service MCP tool and decode its text content."""
        payload = {
            "jsonrpc": "2.0",
            "id": f"ctfagent-{name}",
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": dict(arguments or {}),
            },
        }
        result = await self._request("POST", "/mcp", json=payload)
        if not isinstance(result, Mapping):
            raise MemoryServiceError(
                "Memory service returned an unexpected MCP response",
                kind="invalid_response",
            )
        if "error" in result:
            error = result["error"]
            message = error.get("message", "Memory MCP tool failed") if isinstance(error, Mapping) else str(error)
            raise MemoryServiceError(message, kind="mcp_error")
        rpc_result = result.get("result")
        if not isinstance(rpc_result, Mapping):
            raise MemoryServiceError(
                "Memory service MCP response omitted result",
                kind="invalid_response",
            )
        if rpc_result.get("isError"):
            raise MemoryServiceError(
                "Memory MCP tool returned an error",
                kind="mcp_error",
            )
        content = rpc_result.get("content", [])
        if not isinstance(content, list):
            raise MemoryServiceError(
                "Memory MCP result content is invalid",
                kind="invalid_response",
            )
        text = next(
            (item.get("text") for item in content if isinstance(item, Mapping) and item.get("type") == "text"),
            None,
        )
        if not isinstance(text, str):
            return content
        try:
            return json.loads(text)
        except ValueError:
            return text



memory_client = MemoryClient()
