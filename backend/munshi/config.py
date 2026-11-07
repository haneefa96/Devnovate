"""
Munshi - Application configuration

Settings are loaded from environment variables (.env file or shell).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(BACKEND_ENV_FILE, override=False)


class Settings(BaseSettings):
    """Application settings — loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────
    APP_ENV:      str       = "development"
    DEBUG:        bool      = False
    LOG_LEVEL:    str       = "INFO"
    APP_VERSION:  str       = "0.1.0"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ── Database ──────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./munshi.db"

    # ── Hindsight (Memory) ────────────────────────────────
    HINDSIGHT_API_KEY:   Optional[str] = None
    HINDSIGHT_BASE_URL:  Optional[str] = None
    HINDSIGHT_LOCAL_URL: Optional[str] = None
    HINDSIGHT_TIMEOUT:   int = 30

    # ── Groq (LLM) ───────────────────────────────────────
    GROQ_API_KEY:        Optional[str] = None
    GROQ_AGENT_MODEL:    str           = "openai/gpt-oss-120b"
    GROQ_CUSTOMER_MODEL: str           = "qwen/qwen3-32b"
    GROQ_BASE_URL:       str           = "https://api.groq.com"

    # ── Band (Agent collaboration) ────────────────────────
    BAND_API_KEY:              Optional[str] = None
    BAND_ROOM_ID:              Optional[str] = None
    BAND_AGENT_ID:             Optional[str] = None
    BAND_COLLECTOR_AGENT_ID:   Optional[str] = None
    BAND_COLLECTOR_API_KEY:    Optional[str] = None
    BAND_RISK_AGENT_ID:        Optional[str] = None
    BAND_RISK_API_KEY:         Optional[str] = None
    BAND_WEBHOOK_URL:          Optional[str] = None

    # ── Simulation ────────────────────────────────────────
    SIM_MODE: bool = True

    # ── Derived properties ────────────────────────────────
    @property
    def IS_PRODUCTION(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def HINDSIGHT_URL(self) -> str:
        return (
            self.HINDSIGHT_LOCAL_URL
            or self.HINDSIGHT_BASE_URL
            or "https://api.hindsight.vectorize.io"
        )


# ─── global singleton ────────────────────────────────────────────────────────
settings = Settings()


class Clock:
    """
    Simulated clock for reproducible tests and the demo scenario.

    In SIM_MODE the clock starts at 2026-01-01 00:00:00 and advances
    only when tick() is called. Datetimes use the documented IST offset.
    """

    _TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="IST")
    _START: datetime = datetime(2026, 1, 1, 0, 0, 0, tzinfo=_TIMEZONE)

    def __init__(self, start: datetime | None = None):
        self._start = self._in_timezone(start or self._START)
        self._current = self._start

    def now(self) -> datetime:
        if settings.SIM_MODE:
            return self._current
        return datetime.now(self._TIMEZONE)

    def tick(self, days: int = 1, hours: int = 0) -> datetime:
        """Advance the simulated clock by the requested days and hours."""
        if settings.SIM_MODE:
            self._current = self._current + timedelta(days=days, hours=hours)
        return self.now()

    def reset(self, start: datetime | None = None) -> datetime:
        """Reset the clock to its start time (or a new one)."""
        if start:
            self._start = self._in_timezone(start)
        self._current = self._start
        return self.now()

    def advance_to(self, target: datetime) -> datetime:
        """Jump to a specific datetime (must be ≥ current)."""
        target = self._in_timezone(target)
        if settings.SIM_MODE and target >= self._current:
            self._current = target
        return self.now()

    @classmethod
    def _in_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=cls._TIMEZONE)
        return value.astimezone(cls._TIMEZONE)


# ─── global singleton ────────────────────────────────────────────────────────
clock = Clock()
