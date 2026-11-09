"""Central configuration for KnowledgeBridge.

The application intentionally has no mandatory external AI or database service.
SQLite and the deterministic local extraction engine are the zero-setup defaults.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
DATABASE_DIR = ROOT_DIR / "database"
SAMPLE_DATA_DIR = ROOT_DIR / "sample_data"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(ROOT_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "KnowledgeBridge")
    environment: str = os.getenv("ENVIRONMENT", "development")
    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{DATABASE_DIR / 'knowledgebridge.db'}"
    )
    jwt_secret: str = os.getenv(
        "JWT_SECRET", "development-only-change-me-knowledgebridge"
    )
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = _int("JWT_EXPIRE_MINUTES", 720)
    demo_password: str = os.getenv("DEMO_PASSWORD", "DemoPass!2026")
    seed_demo_data: bool = _bool("SEED_DEMO_DATA", True)
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    github_api_base: str = os.getenv("GITHUB_API_BASE", "https://api.github.com")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    stale_after_days: int = _int("STALE_AFTER_DAYS", 120)
    is_demo_mode: bool = _bool("SEED_DEMO_DATA", True)


settings = Settings()
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
