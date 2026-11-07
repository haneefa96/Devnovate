"""Opt-in synthetic tests against the configured Hindsight Cloud service.

Run explicitly with MUNSHI_RUN_HINDSIGHT_INTEGRATION=1. Never use real customer data.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from munshi.config import settings


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_wrapper_retain_recall_and_customer_isolation():
    if os.getenv("MUNSHI_RUN_HINDSIGHT_INTEGRATION") != "1":
        pytest.skip("Set MUNSHI_RUN_HINDSIGHT_INTEGRATION=1 for synthetic Cloud verification")
    if not settings.HINDSIGHT_BASE_URL or not settings.HINDSIGHT_API_KEY:
        pytest.skip("Hindsight Cloud credentials are not configured")

    from munshi.memory.client import (
        create_bank,
        get_hindsight_client,
        recall_memories,
        reflect_on_memories,
        retain_event,
    )

    client = get_hindsight_client()
    assert await client.check_available()

    bank_id = f"eval-munshi-{uuid.uuid4().hex}-C-s1"
    other_bank_id = f"eval-munshi-other-{uuid.uuid4().hex}-C-s2"
    document_id = f"synthetic-{uuid.uuid4().hex}"
    occurred_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    customer_tag = f"customer:synthetic-{uuid.uuid4().hex[:12]}"
    await create_bank(
        bank_id=bank_id,
        name="Synthetic Munshi integration test",
        mission="Store only synthetic test facts.",
        background="No real customer, financial, or contact information.",
    )
    await create_bank(
        bank_id=other_bank_id,
        name="Synthetic second business integration test",
        mission="Store only synthetic test facts.",
        background="Separate synthetic supplier bank.",
    )
    await create_bank(
        bank_id=bank_id,
        name="Synthetic Munshi integration test",
        mission="Store only synthetic test facts.",
        background="No real customer, financial, or contact information.",
    )

    try:
        retained = await retain_event(
            bank_id=bank_id,
            content="Synthetic customer prefers invoices grouped before the monthly payment run.",
            timestamp=occurred_at,
            context="Synthetic integration verification",
            metadata={"source": "synthetic-test", "customer_id": customer_tag.split(":", 1)[1]},
            tags=[customer_tag, "kind:observation"],
            document_id=document_id,
        )
        assert retained["success"] is True
        assert retained["document_id"] == document_id

        recalled = await recall_memories(
            bank_id,
            "synthetic customer invoice grouping payment run preference",
            tags=[customer_tag],
            tags_match="all",
        )
        matching = [item for item in recalled if item.get("document_id") == document_id]
        assert matching
        assert matching[0]["metadata"]["source"] == "synthetic-test"
        assert matching[0]["timestamp"] is not None
        reflection = await reflect_on_memories(
            bank_id,
            "Summarize the synthetic customer's invoice preference.",
            tags=[customer_tag],
            tags_match="all",
        )
        assert {"requirements", "conflicts", "playbook"} <= reflection.keys()

        other_customer = await recall_memories(
            bank_id,
            "synthetic customer invoice grouping payment run preference",
            tags=["customer:synthetic-other"],
            tags_match="all",
        )
        assert all(item.get("document_id") != document_id for item in other_customer)
        other_business = await recall_memories(
            other_bank_id,
            "synthetic customer invoice grouping payment run preference",
            tags=[customer_tag],
            tags_match="all",
        )
        assert all(item.get("document_id") != document_id for item in other_business)
    finally:
        await client.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_wrapper_outbox_processing(monkeypatch):
    if os.getenv("MUNSHI_RUN_HINDSIGHT_INTEGRATION") != "1":
        pytest.skip("Set MUNSHI_RUN_HINDSIGHT_INTEGRATION=1 for synthetic Cloud verification")
    if not settings.HINDSIGHT_BASE_URL or not settings.HINDSIGHT_API_KEY:
        pytest.skip("Hindsight Cloud credentials are not configured")

    from munshi.db.models import MemoryEvent
    from munshi.memory import outbox
    from munshi.memory.client import get_hindsight_client

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    bank_id = f"eval-outbox-{uuid.uuid4().hex}-C-s1"
    event_id = f"evt_synthetic_{uuid.uuid4().hex[:12]}"

    with Session(engine) as session:
        session.add(
            MemoryEvent(
                id=event_id,
                bank_name=bank_id,
                kind="observation",
                event_type="observation",
                content="Synthetic customer prefers a monthly grouped invoice.",
                timestamp=datetime.now(timezone.utc),
                metadata_={"customer_id": "synthetic-outbox-customer"},
            )
        )
        session.commit()

    def test_session():
        with Session(engine) as session:
            yield session

    client = get_hindsight_client()
    try:
        monkeypatch.setattr(outbox, "get_session", test_session)
        await outbox.OutboxProcessor().process_outbox()
        with Session(engine) as session:
            event = session.exec(
                select(MemoryEvent).where(MemoryEvent.id == event_id)
            ).one()
            assert event.retained_at is not None
            assert event.document_id == event_id
    finally:
        await client.aclose()
        engine.dispose()
