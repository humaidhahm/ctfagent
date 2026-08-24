from __future__ import annotations

import json
from typing import Any

from backend.services.memory_client import memory_client
from backend.tools.base import BaseTool


class _MemoryMcpTool(BaseTool):
    mcp_name = ""

    async def _call(self, **arguments: Any) -> dict[str, Any]:
        result = await memory_client.call_tool(self.mcp_name, arguments)
        output = json.dumps(result, ensure_ascii=False, default=str)
        return {"success": True, "output": output, "result": result}

class MemorySearchWriteupsTool(_MemoryMcpTool):
    name = "memory_search_writeups"
    description = "Search the MCP memory writeup index by challenge text and optional domain or difficulty."
    mcp_name = "search_writeups"

    async def run(
        self,
        query: str = "",
        domain: str | None = None,
        difficulty: str | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            arguments["query"] = query
        if domain is not None:
            arguments["domain"] = domain
        if difficulty is not None:
            arguments["difficulty"] = difficulty
        return await self._call(**arguments)


class MemoryGetWriteupTool(_MemoryMcpTool):
    name = "memory_get_writeup"
    description = "Retrieve a complete stored writeup and provenance by numeric memory id."
    mcp_name = "get_writeup"

    async def run(self, id: int) -> dict[str, Any]:
        return await self._call(id=id)


class MemoryListDomainsTool(_MemoryMcpTool):
    name = "memory_list_domains"
    description = "List challenge domains and their stored writeup counts from MCP memory."
    mcp_name = "list_domains"

    async def run(self) -> dict[str, Any]:
        return await self._call()


class MemorySearchSourceDocumentsTool(_MemoryMcpTool):
    name = "memory_search_source_documents"
    description = "Search imported picoCTF repository source documents."
    mcp_name = "search_source_documents"

    async def run(self, query: str = "", limit: int = 5, offset: int = 0) -> dict[str, Any]:
        arguments: dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            arguments["query"] = query
        return await self._call(**arguments)


class MemoryGetSourceDocumentTool(_MemoryMcpTool):
    name = "memory_get_source_document"
    description = "Retrieve a complete imported source document by numeric memory id."
    mcp_name = "get_source_document"

    async def run(self, id: int) -> dict[str, Any]:
        return await self._call(id=id)


class MemoryFetchWebReferenceTool(_MemoryMcpTool):
    name = "memory_fetch_web_reference"
    description = "Fetch a bounded, allow-listed web reference through MCP memory."
    mcp_name = "fetch_web_reference"

    async def run(self, url: str) -> dict[str, Any]:
        return await self._call(url=url)
