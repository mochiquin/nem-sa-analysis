"""Runtime settings, read from environment variables (or a local .env file)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# AEMO moved NEMweb to HTTPS in April 2026; paths are now case-sensitive.
NEMWEB_BASE_URL = "https://nemweb.com.au/Reports"


@dataclass(frozen=True)
class Settings:
    database_url: str
    region: str
    cache_dir: Path


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "postgresql://nemsa:nemsa@localhost:5432/nemsa"),
        region=os.getenv("NEMSA_REGION", "SA1"),
        cache_dir=Path(os.getenv("NEMSA_CACHE_DIR", "data/raw")),
    )
