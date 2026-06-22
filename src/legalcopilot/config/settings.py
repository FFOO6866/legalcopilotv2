"""Application settings — all config from environment variables."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

_logger = logging.getLogger(__name__)


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def get_int(key: str, default: int = 0) -> int:
    return int(os.environ.get(key, str(default)))


def get_bool(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).lower() in ("true", "1", "yes")


def get_list(key: str, default: str = "") -> list:
    val = os.environ.get(key, default)
    return [s.strip() for s in val.split(",") if s.strip()] if val else []


# App
APP_ENV = get("APP_ENV", "production")
DEBUG = get_bool("DEBUG", False)
LOG_LEVEL = get("LOG_LEVEL", "INFO")

# Database
DATABASE_URL = get("DATABASE_URL", "sqlite:///legalcopilot_dev.db")
REDIS_URL = get("REDIS_URL", "redis://localhost:6379/0")

# Auth
JWT_ALGORITHM = get("JWT_ALGORITHM", "HS256")

_JWT_DEFAULT = "change-this-to-a-random-string-at-least-32-chars"
JWT_SECRET = get("JWT_SECRET_KEY", _JWT_DEFAULT)
if JWT_SECRET == _JWT_DEFAULT:
    if APP_ENV != "development":
        raise RuntimeError(
            "JWT_SECRET_KEY must be set to a secure value in non-development environments. "
            "Set JWT_SECRET_KEY in your .env file."
        )
    _logger.warning("JWT_SECRET_KEY is using the default value — set a secure secret in .env")

# API
API_HOST = get("API_HOST", "0.0.0.0")
API_PORT = get_int("API_PORT", 8000)
CORS_ORIGINS = get_list("CORS_ORIGINS", "http://localhost:3000")
RATE_LIMIT_RPM = get_int("RATE_LIMIT_RPM", 100)

# LLM
OPENAI_API_KEY = get("OPENAI_API_KEY")
DEFAULT_LLM_MODEL = get("DEFAULT_LLM_MODEL", "gpt-4o")

# Vector DB
QDRANT_URL = get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = get("QDRANT_API_KEY")
QDRANT_COLLECTION = get("QDRANT_COLLECTION", "legalcopilot_cases")

# Embedding
EMBEDDING_MODEL = get("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = get_int("EMBEDDING_DIMENSIONS", 1536)

# Storage
S3_BUCKET = get("S3_BUCKET", "legalcopilot-documents")
S3_REGION = get("S3_REGION", "ap-southeast-1")
