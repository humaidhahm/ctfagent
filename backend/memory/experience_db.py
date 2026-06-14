import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from loguru import logger

from backend.config.settings import settings


class ExperienceRecord:
    def __init__(
        self,
        description: str,
        category: str,
        tools_used: list[dict],
        observations: list[str],
        final_flag: str,
        iteration_count: int,
        solved: bool = True,
        keywords: list[str] = None,
        record_id: str = None,
        created_at: str = None,
        target_host: str = None,
        target_port: int = None,
        workflow: str = None,
    ):
        self.id = record_id or str(uuid.uuid4())
        self.description = description
        self.category = category
        self.tools_used = tools_used
        self.observations = observations
        self.final_flag = final_flag
        self.iteration_count = iteration_count
        self.solved = solved
        self.keywords = keywords or self._extract_keywords(description)
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.target_host = target_host
        self.target_port = target_port
        self.workflow = workflow or self._generate_workflow()

    def _generate_workflow(self) -> str:
        """Derive a human-readable step-by-step workflow from the tool chain."""
        steps = []
        for t in (self.tools_used or []):
            tool = t.get("tool", t.get("tool_name", ""))
            args = t.get("tool_input", t.get("args", {}))
            data = args.get("data", args.get("expression", ""))
            newline = args.get("newline", False)
            if tool == "remote_connect":
                if data:
                    nls = " (with newline)" if newline else ""
                    steps.append(f"send '{data[:50]}'{nls}")
                else:
                    steps.append(f"connect & read prompt")
            elif tool == "binary_calc":
                expr = args.get("expression", "")
                steps.append(f"compute '{expr[:50]}'")
            elif tool == "session_read":
                steps.append(f"read prompt")
            elif tool == "download_file":
                url = args.get("url", "")
                steps.append(f"download {url[:50]}")
            elif tool == "file_reader":
                fp = args.get("filepath", "")
                steps.append(f"read file {fp[:40]}")
            elif tool == "password_profiler":
                steps.append(f"run password profiler")
            elif tool == "cupp":
                steps.append(f"run CUPP wordlist")
            elif tool == "pwntools_runner":
                steps.append(f"run pwntools exploit")
            elif tool == "file_decoder":
                steps.append(f"decode file")
            else:
                steps.append(f"{tool}(...)")
        deduped = []
        prev = None
        for s in steps:
            if s != prev:
                deduped.append(s)
            prev = s
        return " → ".join(deduped) if deduped else "No workflow available"

    def _extract_keywords(self, text: str) -> list[str]:
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-.]{2,}", text.lower())
        stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "have", "has",
            "was", "are", "not", "but", "you", "all", "can", "its", "our",
            "com", "org", "http", "https", "html", "php", "www",
        }
        seen = set()
        result = []
        for w in words:
            if w not in stopwords and w not in seen:
                seen.add(w)
                result.append(w)
        return result[:20]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description[:500],
            "category": self.category,
            "tools_used": [
                {"tool": t.get("tool_name", t.get("tool", "")), "args": t.get("tool_input", t.get("args", {}))}
                for t in (self.tools_used or [])
            ],
            "observations": self.observations[-5:],
            "final_flag": self.final_flag,
            "iteration_count": self.iteration_count,
            "solved": self.solved,
            "keywords": self.keywords,
            "created_at": self.created_at,
            "target_host": self.target_host,
            "target_port": self.target_port,
            "workflow": self.workflow,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExperienceRecord":
        return cls(
            description=d.get("description", ""),
            category=d.get("category", ""),
            tools_used=d.get("tools_used", []),
            observations=d.get("observations", []),
            final_flag=d.get("final_flag", ""),
            iteration_count=d.get("iteration_count", 0),
            solved=d.get("solved", True),
            keywords=d.get("keywords"),
            record_id=d.get("id"),
            created_at=d.get("created_at"),
            target_host=d.get("target_host"),
            target_port=d.get("target_port"),
            workflow=d.get("workflow"),
        )


class ExperienceDB:
    _instance = None
    MAX_RECORDS = 500

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.records: list[ExperienceRecord] = []
        self._find_similar_cache: dict[str, list[tuple[ExperienceRecord, float]]] = {}
        self._db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data",
            "experience_db.json",
        )
        self.load()

    @property
    def db_path(self) -> str:
        return self._db_path

    def load(self):
        if os.path.exists(self._db_path):
            try:
                with open(self._db_path, "r") as f:
                    data = json.load(f)
                self.records = [ExperienceRecord.from_dict(r) for r in data.get("records", [])]
                logger.info(f"Loaded {len(self.records)} records from experience DB")
            except Exception as e:
                logger.warning(f"Failed to load experience DB: {e}")
                self.records = []
        else:
            self.records = []

    def save(self):
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with open(self._db_path, "w") as f:
            json.dump({"records": [r.to_dict() for r in self.records]}, f, indent=2)
        logger.info(f"Saved {len(self.records)} records to experience DB")

    def add_record(self, record: ExperienceRecord):
        self.records.append(record)
        if len(self.records) > self.MAX_RECORDS:
            self.records = self.records[-self.MAX_RECORDS:]
        self._find_similar_cache.clear()
        self.save()

    def add_solved(self, state: dict) -> ExperienceRecord:
        manifest = state.get("manifest", {})
        description = manifest.get("description", "")
        category = state.get("category", "unknown")
        tool_history = state.get("tool_history", [])
        observations = state.get("observations", [])
        final_flag = state.get("final_flag", "")
        iteration_count = state.get("iteration_count", 0)
        target_host = manifest.get("target_host")
        target_port = manifest.get("target_port")

        record = ExperienceRecord(
            description=description,
            category=category,
            tools_used=tool_history,
            observations=observations,
            final_flag=final_flag or "",
            iteration_count=iteration_count,
            solved=True,
            target_host=target_host,
            target_port=target_port,
        )
        self.add_record(record)
        logger.info(f"Added solved challenge to experience DB: {record.id[:8]}")
        return record

    def find_similar(self, description: str, category: str = None, top_k: int = 5) -> list[tuple[ExperienceRecord, float]]:
        cache_key = f"{description[:100]}|{category}|{top_k}"
        cached = self._find_similar_cache.get(cache_key)
        if cached is not None:
            return cached
        if not self.records:
            return []

        query_keywords = self._extract_keywords_from(description)
        query_set = set(query_keywords)

        scored: list[tuple[ExperienceRecord, float]] = []

        for record in self.records:
            score = 0.0
            kw_set = set(record.keywords)
            overlap = len(query_set & kw_set)
            if overlap > 0:
                score = overlap / max(len(query_set), len(kw_set))
                score += 0.2 * (overlap / max(len(query_set), 1))

            if category and record.category == category:
                score += 1.0

            if score > 0:
                scored.append((record, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        result = scored[:top_k]
        self._find_similar_cache[cache_key] = result
        return result

    def find_by_tool(self, tool_name: str, top_k: int = 5) -> list[tuple[ExperienceRecord, float]]:
        results = []
        for record in self.records:
            used = record.tools_used or []
            for t in used:
                if isinstance(t, dict) and t.get("tool") == tool_name:
                    results.append((record, 1.0))
                    break
        return results[:top_k]

    def _extract_keywords_from(self, text: str) -> list[str]:
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-.]{2,}", text.lower())
        stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "have", "has",
            "was", "are", "not", "but", "you", "all", "can", "its", "our",
            "com", "org", "http", "https", "html", "php", "www",
        }
        seen = set()
        result = []
        for w in words:
            if w not in stopwords and w not in seen:
                seen.add(w)
                result.append(w)
        return result[:20]

    def get_stats(self) -> dict:
        categories = {}
        tool_counts = {}
        for r in self.records:
            categories[r.category] = categories.get(r.category, 0) + 1
            for t in (r.tools_used or []):
                tname = t.get("tool", t.get("tool_name", "?"))
                tool_counts[tname] = tool_counts.get(tname, 0) + 1
        return {
            "total_records": len(self.records),
            "categories": dict(sorted(categories.items())),
            "tools_used": dict(sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)),
        }

    def clear(self):
        self.records = []
        self._find_similar_cache.clear()
        self.save()
        logger.info("Experience DB cleared")


experience_db = ExperienceDB()
