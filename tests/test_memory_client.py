import httpx
import pytest

from backend.services.memory_client import MemoryClient, MemoryServiceError


@pytest.mark.asyncio
async def test_memory_client_maps_search_and_retrieval_routes() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/writeups"):
            return httpx.Response(200, json={"items": [], "total": 0})
        return httpx.Response(200, json={"id": 7, "markdown": "# writeup"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        memory = MemoryClient(
            base_url="http://memory:3000",
            enabled=True,
            http_client=client,
        )
        assert await memory.search_writeups("buffer overflow", domain="Pwn") == {
            "items": [],
            "total": 0,
        }
        assert await memory.get_writeup(7) == {"id": 7, "markdown": "# writeup"}

    assert requests[0].url.path == "/mcp/writeups"
    assert requests[0].url.params["query"] == "buffer overflow"
    assert requests[0].url.params["domain"] == "Pwn"
    assert requests[1].url.path == "/mcp/writeups/7"


@pytest.mark.asyncio
async def test_disabled_memory_client_fails_explicitly() -> None:
    memory = MemoryClient(enabled=False)

    with pytest.raises(MemoryServiceError) as error:
        await memory.health()

    assert error.value.kind == "disabled"

@pytest.mark.asyncio
async def test_memory_client_calls_json_rpc_tool() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/mcp"
        payload = request.read()
        assert b"search_writeups" in payload
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "ctfagent-search_writeups",
                "result": {
                    "content": [
                        {"type": "text", "text": '{"items": [{"id": 2}]}'}],
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await MemoryClient(
            base_url="http://memory:3000",
            enabled=True,
            http_client=client,
        ).call_tool("search_writeups", {"query": "perceptron"})

    assert result == {"items": [{"id": 2}]}
