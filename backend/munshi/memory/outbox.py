"""Retryable outbox for asynchronously retaining eligible memory events."""

import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlmodel import Session, select

from munshi.db.models import Business, Customer, MemoryEvent
from munshi.db.session import get_session

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?91[\s().-]*)?(?:0[\s().-]*)?[6-9](?:[\s().-]*\d){9}(?!\d)"
)
_ACCOUNT_RE = re.compile(
    r"(?i)\b(?:bank\s+)?(?:account|a/c)\s*(?:no\.?|number)?\s*[:#-]?\s*\d{6,18}\b"
)
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE)
_UPI_RE = re.compile(
    r"(?i)\b(?:upi(?:\s+id)?|vpa)\s*[:=-]\s*[a-z0-9._-]+@[a-z0-9.-]+\b"
)
_DRAFT_KINDS = {"draft", "action_draft", "reminder_draft", "unsent_draft"}


def _session() -> Session:
    return next(get_session())


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_content(event: MemoryEvent) -> str | None:
    if (event.kind or event.event_type or "").lower() in _DRAFT_KINDS:
        return None
    content = event.content or ""
    content = _PHONE_RE.sub("[phone redacted]", content)
    content = _ACCOUNT_RE.sub("[account number redacted]", content)
    content = _IFSC_RE.sub("[bank code redacted]", content)
    content = _UPI_RE.sub("[payment identifier redacted]", content)
    return content.strip() or None


def _event_hash(
    bank_name: str,
    content: str,
    timestamp: datetime,
    customer_id: int | None,
    invoice_id: int | None,
    event_type: str | None,
) -> str:
    identity = "\0".join(
        (
            bank_name,
            content,
            timestamp.isoformat(),
            str(customer_id or ""),
            str(invoice_id or ""),
            event_type or "",
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


class OutboxProcessor:
    """Single-process, bounded retry worker for pending memory events."""

    def __init__(self) -> None:
        self._running = False
        self._interval_seconds = int(os.getenv("OUTBOX_INTERVAL", "60"))
        self._max_retries = int(os.getenv("OUTBOX_MAX_RETRIES", "5"))
        self._retry_delay_seconds = int(os.getenv("OUTBOX_RETRY_DELAY", "300"))
        self._process_lock = asyncio.Lock()

    async def start(self) -> None:
        if self._running:
            logger.info("Memory outbox worker is already running")
            return
        self._running = True
        logger.info("Memory outbox worker started")
        try:
            while self._running:
                await self.process_outbox()
                await asyncio.sleep(self._interval_seconds)
        finally:
            self._running = False
            logger.info("Memory outbox worker stopped")

    async def stop(self) -> None:
        self._running = False

    async def process_outbox(self) -> None:
        if self._process_lock.locked():
            return
        async with self._process_lock:
            session = _session()
            try:
                now = datetime.now(timezone.utc)
                statement = (
                    select(MemoryEvent)
                    .where(
                        MemoryEvent.retained_at.is_(None),
                        MemoryEvent.failed_at.is_(None),
                        or_(
                            MemoryEvent.next_retry_at.is_(None),
                            MemoryEvent.next_retry_at <= now,
                        ),
                    )
                    .order_by(MemoryEvent.created_at)
                )
                for event in session.exec(statement).all():
                    await self._attempt_retain(event, session)
            except Exception as exc:
                logger.error("Memory outbox pass failed (%s)", type(exc).__name__)
                session.rollback()
            finally:
                session.close()

    async def _attempt_retain(self, event: MemoryEvent, session: Session) -> None:
        from munshi.memory.client import HindsightUnavailable, is_hindsight_available, retain_event
        from munshi.memory.events import generate_event_tags

        if not is_hindsight_available():
            return

        content = _safe_content(event)
        if content is None:
            event.failed_at = datetime.now(timezone.utc)
            session.add(event)
            session.commit()
            logger.warning("Skipped ineligible memory event %s", event.id)
            return

        metadata = event.metadata_ or {}
        customer_id = metadata.get("customer_id") or event.customer_id
        invoice_id = metadata.get("invoice_id") or event.invoice_id
        bank_name = event.bank_name
        if not bank_name and event.customer_id is not None:
            customer = session.get(Customer, event.customer_id)
            business = (
                session.get(Business, customer.business_id)
                if customer is not None
                else None
            )
            bank_name = business.bank_id if business is not None else None
        if not bank_name:
            self._increment_retry(event, session)
            logger.warning("Memory event %s has no supplier memory bank", event.id)
            return
        event_kind = event.event_type or event.kind or "action"
        tags = generate_event_tags(
            customer_id=str(customer_id) if customer_id is not None else None,
            event_kind=event_kind,
            invoice_id=str(invoice_id) if invoice_id is not None else None,
        )
        occurred_at = event.timestamp or datetime.combine(
            event.occurred_on,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        safe_metadata = {
            "event_type": event_kind,
            "customer_id": str(customer_id) if customer_id is not None else "",
            "invoice_id": str(invoice_id) if invoice_id is not None else "",
        }

        try:
            from munshi.memory.queries import memory_store

            await memory_store._ensure_bank(bank_name)
            response = await retain_event(
                bank_id=bank_name,
                content=content,
                context=event.context,
                metadata=safe_metadata,
                timestamp=occurred_at,
                tags=tags,
                document_id=event.id,
            )
            if not response or response.get("success") is not True:
                raise HindsightUnavailable("Hindsight did not confirm retention")
            event.retained_at = datetime.now(timezone.utc)
            event.document_id = event.id
            event.next_retry_at = None
            event.failed_at = None
            session.add(event)
            session.commit()
        except Exception as exc:
            logger.warning(
                "Memory event %s retain failed (%s)",
                event.id,
                type(exc).__name__,
            )
            self._increment_retry(event, session)

    def _increment_retry(self, event: MemoryEvent, session: Session) -> None:
        event.retry_count = (event.retry_count or 0) + 1
        if event.retry_count >= self._max_retries:
            event.failed_at = datetime.now(timezone.utc)
            event.next_retry_at = None
            logger.error("Memory event %s exhausted bounded retries", event.id)
        else:
            delay = self._retry_delay_seconds * (2 ** (event.retry_count - 1))
            event.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        session.add(event)
        session.commit()

    async def get_pending_count(self) -> int:
        session = _session()
        try:
            statement = select(MemoryEvent).where(
                MemoryEvent.retained_at.is_(None),
                MemoryEvent.failed_at.is_(None),
            )
            return len(session.exec(statement).all())
        finally:
            session.close()

    async def get_failed_count(self) -> int:
        session = _session()
        try:
            return len(
                session.exec(
                    select(MemoryEvent).where(MemoryEvent.failed_at.is_not(None))
                ).all()
            )
        finally:
            session.close()


outbox_processor = OutboxProcessor()


async def queue_memory_event(
    bank_name: str,
    content: str,
    timestamp: datetime,
    customer_id: int | str | None = None,
    invoice_id: int | str | None = None,
    event_type: str | None = None,
    context: str | None = None,
    details: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MemoryEvent:
    session = _session()
    try:
        customer_fk = int(customer_id) if str(customer_id or "").isdigit() else None
        invoice_fk = int(invoice_id) if str(invoice_id or "").isdigit() else None
        event_hash = _event_hash(
            bank_name,
            content,
            timestamp,
            customer_fk,
            invoice_fk,
            event_type,
        )
        existing = session.exec(
            select(MemoryEvent).where(MemoryEvent.content_hash == event_hash)
        ).first()
        if existing:
            return existing

        event_metadata = dict(metadata or {})
        if customer_id is not None:
            event_metadata["customer_id"] = str(customer_id)
        if invoice_id is not None:
            event_metadata["invoice_id"] = str(invoice_id)
        event = MemoryEvent(
            bank_name=bank_name,
            content=content,
            timestamp=_utc_datetime(timestamp),
            customer_id=customer_fk,
            invoice_id=invoice_fk,
            kind=event_type or "action",
            event_type=event_type,
            context=context,
            details=details,
            metadata_=event_metadata,
            content_hash=event_hash,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        logger.info("Queued memory event %s", event.id)
        return event
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def mark_event_as_retained(event_id: str, document_id: str) -> bool:
    session = _session()
    try:
        event = session.exec(
            select(MemoryEvent).where(MemoryEvent.id == event_id)
        ).first()
        if event is None:
            return False
        event.retained_at = datetime.now(timezone.utc)
        event.document_id = document_id
        event.next_retry_at = None
        session.add(event)
        session.commit()
        return True
    finally:
        session.close()


async def mark_event_as_failed(event_id: str, error: str) -> bool:
    del error
    session = _session()
    try:
        event = session.exec(
            select(MemoryEvent).where(MemoryEvent.id == event_id)
        ).first()
        if event is None:
            return False
        event.failed_at = datetime.now(timezone.utc)
        event.next_retry_at = None
        session.add(event)
        session.commit()
        return True
    finally:
        session.close()


async def retry_failed_events() -> list[str]:
    session = _session()
    try:
        events = session.exec(
            select(MemoryEvent).where(MemoryEvent.failed_at.is_not(None))
        ).all()
        for event in events:
            event.failed_at = None
            event.retry_count = 0
            event.next_retry_at = None
            session.add(event)
        session.commit()
        return [event.id for event in events]
    finally:
        session.close()
