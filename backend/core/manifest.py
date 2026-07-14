from pydantic import BaseModel
from typing import Optional, Literal
from enum import Enum
import uuid
from datetime import datetime, timezone


class ChallengeCategory(str, Enum):
    WEB = "web"
    CRYPTO = "crypto"
    FORENSICS = "forensics"
    PWN = "pwn"
    RE = "re"
    OSINT = "osint"
    MISC = "misc"
    UNKNOWN = "unknown"


class FileAttachment(BaseModel):
    filename: str
    filepath: str
    mime_type: str
    size_bytes: int
    sha256: str


class ChallengeManifest(BaseModel):
    challenge_id: str
    name: str
    title: Optional[str] = None
    description: str
    category: ChallengeCategory = ChallengeCategory.UNKNOWN
    attachments: list[FileAttachment] = []
    target_url: Optional[str] = None
    target_host: Optional[str] = None
    target_port: Optional[int] = None
    flag_format: Optional[str] = None
    points: Optional[int] = None
    raw_input_type: Literal["text", "file", "url", "mixed"] = "text"
    created_at: str = ""

    @classmethod
    def create(cls,name: str, description: str, **kwargs) -> "ChallengeManifest":
        return cls(
            name=name,
            challenge_id=str(uuid.uuid4()),
            description=description,
            created_at=datetime.now(timezone.utc).isoformat(),
            **kwargs,
        )
