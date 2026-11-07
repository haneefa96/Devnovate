"""Shared, validated policies and schemas for Collector and Risk."""

import re
from abc import ABC, abstractmethod
from datetime import datetime, time, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlmodel import Session


RiskLevel = Literal["NORMAL", "WATCH", "HIGH"]

_UNSAFE_LANGUAGE = (
    "legal action",
    "lawsuit",
    "court action",
    "final warning",
    "pay immediately",
    "pay now",
    "otherwise we will",
    "or else",
    "stop supply",
    "hold dispatch",
    "blacklist",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReminderWording(StrictModel):
    """Untrusted wording returned by the LLM; ledger facts are added by code."""

    greeting: str = Field(min_length=1, max_length=120)
    request: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(default_factory=list)


class ReminderPlan(StrictModel):
    """Validated Collector proposal; this is a draft, never a send command."""

    invoice_id: int
    customer_id: int
    send_on: datetime
    recipient: str
    channel: str = "WHATSAPP"
    body: str
    attachments: list[str] = Field(default_factory=list)
    tone: str = "gentle"
    reason: str
    evidence_ids: list[str] = Field(min_length=1)
    memory_supported: bool
    owner_approval_required: Literal[True] = True
    status: Literal["DRAFTED"] = "DRAFTED"

    @field_validator("evidence_ids")
    @classmethod
    def evidence_must_be_unique(cls, values: list[str]) -> list[str]:
        if any(not value for value in values):
            raise ValueError("evidence IDs must be non-empty")
        return list(dict.fromkeys(values))

    @field_validator("body")
    @classmethod
    def body_must_be_non_coercive(cls, value: str) -> str:
        if contains_coercive_language(value):
            raise ValueError("Reminder body cannot contain threats or coercive language")
        return value


class RiskSignal(StrictModel):
    """One deterministic or customer-scoped memory signal with traceable support."""

    code: str
    description: str
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator("evidence_ids")
    @classmethod
    def evidence_must_be_unique(cls, values: list[str]) -> list[str]:
        if any(not value for value in values):
            raise ValueError("evidence IDs must be non-empty")
        return list(dict.fromkeys(values))


class RiskAssessment(StrictModel):
    """Risk result for owner review, not a credit or dispatch decision."""

    customer_id: int
    level: RiskLevel
    signals: list[RiskSignal] = Field(default_factory=list)
    suggestion: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    memory_status: Literal["AVAILABLE", "UNAVAILABLE"] = "UNAVAILABLE"
    owner_decision_required: Literal[True] = True

    @field_validator("evidence_ids")
    @classmethod
    def evidence_must_be_unique(cls, values: list[str]) -> list[str]:
        if any(not value for value in values):
            raise ValueError("evidence IDs must be non-empty")
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def enforce_risk_threshold(self) -> "RiskAssessment":
        signal_count = len({signal.code for signal in self.signals})
        expected_level = "HIGH" if signal_count >= 2 else "WATCH" if signal_count else "NORMAL"
        if self.level != expected_level:
            raise ValueError(
                f"Risk level must be {expected_level} for {signal_count} qualifying signals"
            )
        if self.suggestion and contains_coercive_language(self.suggestion):
            raise ValueError("Risk suggestion cannot contain coercive language")
        return self


def has_evidence(evidence_ids: list[str]) -> bool:
    """Return whether a recommendation has at least one traceable evidence ID."""
    return bool([value for value in evidence_ids if value])


def contains_coercive_language(text: str) -> bool:
    """Detect explicit threats and coercive collection phrases."""
    normalized = re.sub(r"\s+", " ", text.lower())
    return any(phrase in normalized for phrase in _UNSAFE_LANGUAGE)


def normalize_ist(value: datetime, reference: datetime) -> datetime:
    """Convert a time to the timezone of the simulated-clock reference."""
    if value.tzinfo is None:
        return value.replace(tzinfo=reference.tzinfo)
    return value.astimezone(reference.tzinfo)


def is_contact_time_allowed(value: datetime, reference: datetime) -> bool:
    """Check that the planned contact time is within 09:00–19:00 IST."""
    local = normalize_ist(value, reference)
    return time(9) <= local.timetz().replace(tzinfo=None) < time(19)


def clamp_contact_time(value: datetime, reference: datetime) -> datetime:
    """Move a proposed contact time into the documented local contact window."""
    local = normalize_ist(value, reference)
    local = max(local, normalize_ist(reference, reference))
    if local.timetz().replace(tzinfo=None) < time(9):
        return local.replace(hour=9, minute=0, second=0, microsecond=0)
    if local.timetz().replace(tzinfo=None) >= time(19):
        return (local + timedelta(days=1)).replace(
            hour=9,
            minute=0,
            second=0,
            microsecond=0,
        )
    return local


class Policy(ABC):
    """Policy interface shared by the app and evaluation code."""

    @abstractmethod
    async def on_invoice_due(
        self,
        session: Session,
        invoice_id: int,
    ) -> list[dict[str, Any]]:
        """Return proposed draft actions for a due invoice."""
        raise NotImplementedError

    @abstractmethod
    async def on_customer_reply(
        self,
        session: Session,
        message_id: int,
    ) -> list[dict[str, Any]]:
        """Return follow-up actions for a customer reply."""
        raise NotImplementedError

    @abstractmethod
    async def on_payment(
        self,
        session: Session,
        payment_id: int,
    ) -> dict[str, Any]:
        """Return a risk assessment after a ledger payment."""
        raise NotImplementedError

    @abstractmethod
    async def on_daily_check(
        self,
        session: Session,
        date: datetime,
    ) -> list[dict[str, Any]]:
        """Return proposed actions from the daily ledger check."""
        raise NotImplementedError


class BasePolicy(Policy):
    """Base policy implementation with optional peer-agent links."""

    def __init__(self) -> None:
        self.collector_agent: Any | None = None
        self.risk_agent: Any | None = None

    def set_agents(self, collector: Any, risk: Any) -> None:
        """Set agent instances for documented Collector-to-Risk handoffs."""
        self.collector_agent = collector
        self.risk_agent = risk
