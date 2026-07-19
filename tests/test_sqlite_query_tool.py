import sqlite3

import pytest

from backend.agents.tool_registry import get_tool, list_tools
from backend.tools.general.sqlite_query import SQLiteQueryTool


@pytest.mark.asyncio
async def test_sqlite_query_lists_and_reads_tables(tmp_path):
    db_path = tmp_path / "users.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (username TEXT, two_fa INTEGER)")
        conn.execute("INSERT INTO users VALUES ('admin', 1)")

    tool = SQLiteQueryTool()
    tables = await tool.run(filepath=str(db_path))
    rows = await tool.run(
        filepath=str(db_path),
        query="SELECT username, two_fa FROM users",
    )

    assert tables["success"] is True
    assert "users" in tables["output"]
    assert rows["success"] is True
    assert "admin | 1" in rows["output"]


@pytest.mark.asyncio
async def test_sqlite_query_rejects_writes(tmp_path):
    db_path = tmp_path / "users.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (username TEXT)")

    result = await SQLiteQueryTool().run(
        filepath=str(db_path),
        query="DROP TABLE users",
    )

    assert result["success"] is False
    assert "read-only" in result["error"]


def test_sqlite_query_is_registered():
    assert "sqlite_query" in list_tools()
    assert get_tool("sqlite_query").name == "sqlite_query"
