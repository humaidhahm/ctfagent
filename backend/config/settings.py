import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = str(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    nvidia_nim_api_key: str = ""
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"

    nim_models: dict[str, str] = {
        # Leave empty to let SmartLLM select based on load + speed
        # Override any role to pin a specific model
    }

    # Model tier overrides per role (defaults from model_registry)
    nim_model_tiers: dict[str, str] = {
        "classifier": "fast",
        "flag_detector": "fast",
        "difficulty_estimator": "fast",
        "supervisor": "capable",
        "web": "capable",
        "crypto": "fast",
        "forensics": "fast",
        "pwn": "capable",
        "re": "capable",
        "misc": "fast",
        "osint": "fast",
        "coordinator": "capable",
    }

    flag_format: str = ""
    max_agent_iterations: int = 20
    max_tool_timeout_seconds: int = 300
    agent_temperature: float = 0.1

    docker_sandbox_image: str = "ctfagent-sandbox:latest"
    docker_sandbox_memory_limit: str = "512m"
    docker_sandbox_cpu_limit: float = 1.0
    docker_sandbox_timeout_seconds: int = 30

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    upload_dir: str = "./uploads"
    session_ttl_seconds: int = 3600

    model_config = {"env_prefix": "", "extra": "ignore", "env_file": _ENV_PATH}


settings = Settings()

os.makedirs(settings.upload_dir, exist_ok=True)
