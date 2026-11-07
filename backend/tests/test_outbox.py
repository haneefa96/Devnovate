"""Tests for outbox persistence, retries, idempotency, and lifecycle."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from munshi.db.models import MemoryEvent


@pytest.fixture
def outbox_db(monkeypatch):
    from munshi.memory import outbox

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def session_generator():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(outbox, "get_session", session_generator)
    monkeypatch.setattr(
        "munshi.memory.queries.memory_store._ensure_bank",
        AsyncMock(),
    )
    yield engine
    engine.dispose()


def _insert_event(engine, **values):
    defaults = {
        "id": "evt_test_123",
        "bank_name": "munshi-synthetic",
        "kind": "payment_received",
        "event_type": "payment_received",
        "content": "Synthetic payment preference fact",
        "timestamp": datetime.now(timezone.utc),
    }
    defaults.update(values)
    with Session(engine) as session:
        event = MemoryEvent(**defaults)
        session.add(event)
        session.commit()
        session.refresh(event)
        return event.id


def _read_event(engine, event_id):
    with Session(engine) as session:
        return session.exec(
            select(MemoryEvent).where(MemoryEvent.id == event_id)
        ).one()


def test_processor_defaults_and_custom_configuration(monkeypatch):
    from munshi.memory.outbox import OutboxProcessor

    processor = OutboxProcessor()
    assert processor._running is False
    assert processor._interval_seconds == 60
    assert processor._max_retries == 5

    monkeypatch.setenv("OUTBOX_INTERVAL", "120")
    monkeypatch.setenv("OUTBOX_MAX_RETRIES", "3")
    monkeypatch.setenv("OUTBOX_RETRY_DELAY", "600")
    configured = OutboxProcessor()
    assert configured._interval_seconds == 120
    assert configured._max_retries == 3
    assert configured._retry_delay_seconds == 600


@pytest.mark.asyncio
async def test_queue_event_deduplicates_and_uses_actual_model_fields(outbox_db):
    from munshi.memory.outbox import queue_memory_event

    timestamp = datetime(2026, 11, 7, 10, tzinfo=timezone.utc)
    first = await queue_memory_event(
        bank_name="munshi-synthetic",
        content="Synthetic payment preference",
        timestamp=timestamp,
        customer_id="cust-synthetic",
        event_type="observation",
        metadata={"source": "synthetic"},
    )
    second = await queue_memory_event(
        bank_name="munshi-synthetic",
        content="Synthetic payment preference",
        timestamp=timestamp,
        customer_id="cust-synthetic",
        event_type="observation",
        metadata={"source": "synthetic"},
    )

    assert first.id == second.id
    persisted = _read_event(outbox_db, first.id)
    assert persisted.metadata_["customer_id"] == "cust-synthetic"
    assert persisted.content_hash


@pytest.mark.asyncio
async def test_successful_retain_is_confirmed_and_redacts_sensitive_values(
    outbox_db, monkeypatch
):
    from munshi.memory import outbox

    event_id = _insert_event(
        outbox_db,
        content=(
            "Synthetic contact +91 (98765) 43210 and 09876-543210; "
            "account number 123456789012 IFSC ABCD0123456; "
            "UPI ID: user.name@upi"
        ),
        metadata_={"customer_id": "cust-synthetic"},
    )
    retain = AsyncMock(return_value={"success": True, "document_id": "ignored"})
    monkeypatch.setattr(outbox, "get_session", outbox.get_session)
    with (
        patch("munshi.memory.client.is_hindsight_available", return_value=True),
        patch("munshi.memory.client.retain_event", retain),
    ):
        await outbox.OutboxProcessor().process_outbox()

    persisted = _read_event(outbox_db, event_id)
    assert persisted.retained_at is not None
    assert persisted.document_id == event_id
    assert persisted.retry_count == 0
    kwargs = retain.await_args.kwargs
    assert kwargs["document_id"] == event_id
    assert kwargs["tags"] == ["customer:cust-synthetic", "kind:payment_received"]
    assert "+91 (98765) 43210" not in kwargs["content"]
    assert "09876-543210" not in kwargs["content"]
    assert "123456789012" not in kwargs["content"]
    assert "ABCD0123456" not in kwargs["content"]
    assert "user.name@upi" not in kwargs["content"]


@pytest.mark.asyncio
async def test_failed_retain_schedules_bounded_retry(outbox_db):
    from munshi.memory import outbox
    from munshi.memory.client import HindsightUnavailable

    event_id = _insert_event(outbox_db)
    processor = outbox.OutboxProcessor()
    processor._max_retries = 2
    processor._retry_delay_seconds = 3600
    retain = AsyncMock(side_effect=HindsightUnavailable("service unavailable"))
    with (
        patch("munshi.memory.client.is_hindsight_available", return_value=True),
        patch("munshi.memory.client.retain_event", retain),
    ):
        await processor.process_outbox()
        scheduled = _read_event(outbox_db, event_id)
        assert scheduled.retry_count == 1
        retry_at = scheduled.next_retry_at
        if retry_at.tzinfo is not None:
            retry_at = retry_at.replace(tzinfo=None)
        assert retry_at > datetime.now()

        await processor.process_outbox()
        assert retain.await_count == 1

        with Session(outbox_db) as session:
            due = session.get(MemoryEvent, event_id)
            due.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            session.add(due)
            session.commit()
        await processor.process_outbox()

    failed = _read_event(outbox_db, event_id)
    assert failed.retry_count == 2
    assert failed.failed_at is not None
    assert failed.retained_at is None
    assert retain.await_count == 2


@pytest.mark.asyncio
async def test_repeated_and_concurrent_processing_do_not_duplicate_retains(outbox_db):
    from munshi.memory import outbox

    event_id = _insert_event(outbox_db)

    async def retain_once(**_kwargs):
        await asyncio.sleep(0.02)
        return {"success": True}

    retain = AsyncMock(side_effect=retain_once)
    processor = outbox.OutboxProcessor()
    with (
        patch("munshi.memory.client.is_hindsight_available", return_value=True),
        patch("munshi.memory.client.retain_event", retain),
    ):
        await asyncio.gather(
            processor.process_outbox(),
            processor.process_outbox(),
        )
        await processor.process_outbox()

    assert retain.await_count == 1
    assert _read_event(outbox_db, event_id).retained_at is not None


@pytest.mark.asyncio
async def test_draft_events_are_never_retained(outbox_db):
    from munshi.memory import outbox

    event_id = _insert_event(
        outbox_db,
        kind="reminder_draft",
        event_type="reminder_draft",
        content="Synthetic unsent draft",
    )
    retain = AsyncMock(return_value={"success": True})
    with (
        patch("munshi.memory.client.is_hindsight_available", return_value=True),
        patch("munshi.memory.client.retain_event", retain),
    ):
        await outbox.OutboxProcessor().process_outbox()

    assert retain.await_count == 0
    assert _read_event(outbox_db, event_id).failed_at is not None


@pytest.mark.asyncio
async def test_worker_start_stop_is_idempotent():
    from munshi.memory.outbox import OutboxProcessor

    processor = OutboxProcessor()
    processor._interval_seconds = 0.001
    processor.process_outbox = AsyncMock()
    first_worker = asyncio.create_task(processor.start())
    await asyncio.sleep(0.01)
    second_worker = asyncio.create_task(processor.start())
    await second_worker
    await processor.stop()
    await first_worker

    assert processor._running is False
    assert processor.process_outbox.await_count >= 1


@pytest.mark.asyncio
async def test_fastapi_lifespan_starts_and_stops_worker(monkeypatch):
    import munshi.main as main
    from munshi.memory import outbox

    started = asyncio.Event()
    stopping = AsyncMock()
    waiting_start = AsyncMock(side_effect=started.wait)
    closing = AsyncMock()
    monkeypatch.setattr(main, "init_db", MagicMock())
    monkeypatch.setattr(outbox.outbox_processor, "start", waiting_start)
    monkeypatch.setattr(outbox.outbox_processor, "stop", stopping)
    monkeypatch.setattr(
        "munshi.memory.client.get_hindsight_client",
        MagicMock(return_value=MagicMock(aclose=closing)),
    )

    async with main.app.router.lifespan_context(main.app):
        await asyncio.sleep(0)
        started.set()
    assert waiting_start.await_count == 1
    stopping.assert_awaited_once()
    closing.assert_awaited_once()
