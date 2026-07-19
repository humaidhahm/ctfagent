import sqlite3
from pathlib import Path

from backend.tools.base import BaseTool
from loguru import logger


class SQLiteQueryTool(BaseTool):
    name = "sqlite_query"
    description = "Inspect a local SQLite database with read-only SELECT or PRAGMA queries"
    parameters = {
        "filepath": {"type": "string", "description": "Path to the SQLite database file"},
        "query": {
            "type": "string",
            "description": "Read-only SQL query. Defaults to listing tables.",
        },
    }

    async def run(self, filepath: str = "", query: str = "", **kwargs) -> dict:
        filepath = kwargs.pop("path", filepath) or filepath
        query = kwargs.pop("sql", query) or query

        if not filepath:
            return {
                "success": False,
                "output": "",
                "error": "No filepath provided",
                "command": "sqlite_query",
            }

        db_path = Path(filepath)
        if not db_path.exists():
            return {
                "success": False,
                "output": "",
                "error": f"File not found: {filepath}",
                "command": f"sqlite3 {filepath}",
            }

        query = (query or "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").strip()
        lowered = query.lower().lstrip()
        if not lowered.startswith(("select", "pragma")):
            return {
                "success": False,
                "output": "",
                "error": "Only read-only SELECT and PRAGMA queries are allowed",
                "command": f"sqlite3 {filepath}",
            }

        try:
            uri = f"file:{db_path.resolve()}?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=5) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(query).fetchmany(100)

            if not rows:
                output = "(no rows)"
            else:
                headers = rows[0].keys()
                lines = [" | ".join(headers)]
                lines.extend(
                    " | ".join(str(row[header]) for header in headers)
                    for row in rows
                )
                output = "\n".join(lines)

            logger.info(f"sqlite_query read {filepath}: {query}")
            return {
                "success": True,
                "output": output[:10000],
                "error": "",
                "command": f"sqlite3 {filepath} {query}",
            }
        except Exception as exc:
            logger.error(f"sqlite_query error: {exc}")
            return {
                "success": False,
                "output": "",
                "error": str(exc),
                "command": f"sqlite3 {filepath} {query}",
            }
