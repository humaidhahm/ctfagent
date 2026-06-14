import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from backend.memory.experience_db import ExperienceRecord, ExperienceDB


def _fresh_db(tmp_path):
    db = ExperienceDB()
    db._db_path = str(tmp_path / "test_experience.json")
    db.records = []
    return db


def _reload_db(tmp_path):
    """Force reload the singleton from disk (bypasses _initialized check)"""
    db = ExperienceDB()
    db._db_path = str(tmp_path / "test_experience.json")
    db.load()
    return db


class TestExperienceRecord:
    def test_extract_keywords(self):
        rec = ExperienceRecord(
            description="A web challenge with SQL injection on a login form at target site",
            category="web",
            tools_used=[],
            observations=[],
            final_flag="FLAG{test}",
            iteration_count=3,
        )
        assert "sql" in rec.keywords
        assert "injection" in rec.keywords
        assert "login" in rec.keywords
        assert "target" in rec.keywords
        assert "com" not in rec.keywords

    def test_to_dict_roundtrip(self):
        rec = ExperienceRecord(
            description="Test challenge",
            category="crypto",
            tools_used=[{"tool": "cipher_cracker", "args": {"ciphertext": "abc"}}],
            observations=["Found base64", "Decoded to flag"],
            final_flag="FLAG{test}",
            iteration_count=5,
        )
        d = rec.to_dict()
        assert d["category"] == "crypto"
        assert d["final_flag"] == "FLAG{test}"
        assert d["tools_used"][0]["tool"] == "cipher_cracker"

        rec2 = ExperienceRecord.from_dict(d)
        assert rec2.category == "crypto"
        assert rec2.final_flag == "FLAG{test}"
        assert rec2.id == rec.id
        assert rec2.iteration_count == 5
        assert rec2.tools_used[0]["tool"] == "cipher_cracker"


class TestExperienceDB:
    def test_add_and_find_similar(self, tmp_path):
        db = _fresh_db(tmp_path)

        db.add_record(ExperienceRecord(
            description="Command injection on a ping service",
            category="web",
            tools_used=[{"tool": "remote_connect", "args": {"host": "x", "port": 1, "data": "8.8.8.8; ls"}}],
            observations=[],
            final_flag="picoCTF{test1}",
            iteration_count=2,
        ))
        db.add_record(ExperienceRecord(
            description="RSA decryption challenge with large modulus",
            category="crypto",
            tools_used=[{"tool": "rsa_solver", "args": {}}],
            observations=[],
            final_flag="FLAG{rsa}",
            iteration_count=5,
        ))

        assert len(db.records) == 2

        results = db.find_similar("ping command injection server", top_k=5)
        assert len(results) >= 1
        best_rec, best_score = results[0]
        assert best_rec.category == "web"
        assert best_score > 0

        results_crypto = db.find_similar("RSA modulus decrypt", category="crypto", top_k=5)
        assert len(results_crypto) >= 1

    def test_find_by_tool(self, tmp_path):
        db = _fresh_db(tmp_path)

        db.add_record(ExperienceRecord(
            description="Test web challenge",
            category="web",
            tools_used=[{"tool": "sqlmap", "args": {}}],
            observations=[],
            final_flag="FLAG{x}",
            iteration_count=1,
        ))

        results = db.find_by_tool("sqlmap")
        assert len(results) == 1
        assert results[0][0].final_flag == "FLAG{x}"

        results = db.find_by_tool("gobuster")
        assert len(results) == 0

    def test_clear(self, tmp_path):
        db = _fresh_db(tmp_path)
        db.add_record(ExperienceRecord(
            description="test", category="web", tools_used=[],
            observations=[], final_flag="F", iteration_count=0,
        ))
        assert len(db.records) == 1
        db.clear()
        assert len(db.records) == 0

    def test_persist(self, tmp_path):
        db = _fresh_db(tmp_path)
        db.add_record(ExperienceRecord(
            description="Persist test", category="pwn", tools_used=[],
            observations=[], final_flag="FLAG{p}", iteration_count=3,
        ))
        db2 = _reload_db(tmp_path)
        assert len(db2.records) == 1
        assert db2.records[0].final_flag == "FLAG{p}"

    def test_stats(self, tmp_path):
        db = _fresh_db(tmp_path)
        db.add_record(ExperienceRecord(
            description="w1", category="web", tools_used=[{"tool": "a"}],
            observations=[], final_flag="F1", iteration_count=1,
        ))
        db.add_record(ExperienceRecord(
            description="w2", category="web", tools_used=[{"tool": "b"}],
            observations=[], final_flag="F2", iteration_count=2,
        ))
        db.add_record(ExperienceRecord(
            description="c1", category="crypto", tools_used=[{"tool": "a"}],
            observations=[], final_flag="F3", iteration_count=3,
        ))
        stats = db.get_stats()
        assert stats["total_records"] == 3
        assert stats["categories"]["web"] == 2
        assert stats["categories"]["crypto"] == 1

    @pytest.mark.asyncio
    async def test_add_solved_from_state(self, tmp_path):
        db = _fresh_db(tmp_path)
        state = {
            "manifest": {
                "description": "Ping command injection challenge",
                "target_host": "example.com",
                "target_port": 1234,
                "flag_format": "picoCTF{...}",
            },
            "category": "web",
            "tool_history": [
                {"tool_name": "remote_connect", "tool_input": {"host": "x", "port": 1}, "tool_output": "output1"},
            ],
            "observations": ["Got login prompt", "Sent payload"],
            "final_flag": "picoCTF{solved}",
            "iteration_count": 2,
        }

        record = db.add_solved(state)
        assert record.category == "web"
        assert record.final_flag == "picoCTF{solved}"
        assert record.iteration_count == 2
        assert record.target_host == "example.com"
        assert record.target_port == 1234
        assert len(db.records) == 1

        similar = db.find_similar("ping command injection")
        assert len(similar) >= 1
