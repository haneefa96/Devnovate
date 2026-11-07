"""Focused tests for Munshi's adapter to hindsight-client 1.x."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_singleton():
    from munshi.memory import client as client_module

    client_module.HindsightClient._instance = None
    yield
    client_module.HindsightClient._instance = None


def _client_with_sdk(sdk):
    wrapper = MagicMock()
    wrapper.is_available = True
    wrapper.client = sdk
    return wrapper


def test_client_initializes_official_sdk_with_configured_values(monkeypatch):
    from munshi.memory import client as client_module

    captured = {}

    class FakeHindsight:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(client_module.settings, "HINDSIGHT_LOCAL_URL", None)
    monkeypatch.setattr(client_module.settings, "HINDSIGHT_BASE_URL", "https://memory.example")
    monkeypatch.setattr(client_module.settings, "HINDSIGHT_API_KEY", "synthetic-key")
    monkeypatch.setattr(client_module.settings, "HINDSIGHT_TIMEOUT", 12)
    monkeypatch.setitem(
        __import__("sys").modules,
        "hindsight_client",
        SimpleNamespace(Hindsight=FakeHindsight),
    )

    client = client_module.HindsightClient()

    assert client.is_available
    assert captured == {
        "base_url": "https://memory.example",
        "api_key": "synthetic-key",
        "timeout": 12.0,
    }


def test_unconfigured_client_raises_explicit_error():
    from munshi.memory.client import HindsightClient, HindsightUnavailable

    client = HindsightClient()
    with pytest.raises(HindsightUnavailable, match="not configured"):
        _ = client.client


@pytest.mark.asyncio
async def test_health_check_uses_async_version_method():
    from munshi.memory.client import HindsightClient

    wrapper = HindsightClient()
    wrapper._client = MagicMock()
    wrapper._client.aget_version = AsyncMock(return_value=SimpleNamespace(api_version="1.1.0"))

    assert await wrapper.check_available() is True
    wrapper._client.aget_version.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_retain_passes_timestamp_tags_metadata_and_stable_document_id():
    from munshi.memory.client import retain_event

    timestamp = datetime(2026, 11, 7, 10, tzinfo=timezone.utc)
    sdk = MagicMock()
    sdk.aretain = AsyncMock(return_value=SimpleNamespace(success=True, model_dump=lambda **_: {
        "success": True,
        "bank_id": "munshi-demo",
        "items_count": 1,
    }))
    with patch(
        "munshi.memory.client.get_hindsight_client",
        return_value=_client_with_sdk(sdk),
    ):
        response = await retain_event(
            bank_id="munshi-demo",
            content="Synthetic payment preference fact",
            timestamp=timestamp,
            metadata={"customer_id": "cust-test", "source": "synthetic"},
            tags=["customer:cust-test", "kind:observation"],
            document_id="evt_test_1",
        )

    assert response["success"] is True
    assert response["document_id"] == "evt_test_1"
    kwargs = sdk.aretain.await_args.kwargs
    assert kwargs["timestamp"] == timestamp
    assert kwargs["document_id"] == "evt_test_1"
    assert kwargs["tags"] == ["customer:cust-test", "kind:observation"]
    assert kwargs["metadata"] == {"customer_id": "cust-test", "source": "synthetic"}


@pytest.mark.asyncio
async def test_retain_failure_is_explicit_and_does_not_expose_sdk_error():
    from munshi.memory.client import HindsightUnavailable, retain_event

    sdk = MagicMock()
    sdk.aretain = AsyncMock(side_effect=RuntimeError("secret response details"))
    with patch(
        "munshi.memory.client.get_hindsight_client",
        return_value=_client_with_sdk(sdk),
    ):
        with pytest.raises(HindsightUnavailable) as exc_info:
            await retain_event("munshi-demo", "synthetic fact")

    assert "secret response details" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_recall_uses_customer_tag_filter_and_maps_sdk_results():
    from munshi.memory.client import recall_memories

    result = SimpleNamespace(
        id="memory-1",
        document_id="evt-1",
        text="Synthetic fact",
        type="experience",
        occurred_start="2026-11-07T10:00:00Z",
        tags=["customer:cust-a"],
        metadata={"customer_id": "cust-a"},
        model_dump=lambda **_: {
            "id": "memory-1",
            "document_id": "evt-1",
            "text": "Synthetic fact",
            "type": "experience",
            "occurred_start": "2026-11-07T10:00:00Z",
            "tags": ["customer:cust-a"],
            "metadata": {"customer_id": "cust-a"},
        },
    )
    sdk = MagicMock()
    sdk.arecall = AsyncMock(return_value=SimpleNamespace(results=[result]))
    with patch(
        "munshi.memory.client.get_hindsight_client",
        return_value=_client_with_sdk(sdk),
    ):
        memories = await recall_memories(
            "munshi-demo",
            "payment preference",
            tags=["customer:cust-a"],
            tags_match="all",
        )

    assert memories[0]["content"] == "Synthetic fact"
    assert memories[0]["document_id"] == "evt-1"
    assert memories[0]["customer_id"] == "cust-a"
    assert sdk.arecall.await_args.kwargs["tags"] == ["customer:cust-a"]
    assert sdk.arecall.await_args.kwargs["tags_match"] == "all"
    assert sdk.arecall.await_args.kwargs["budget"] == "mid"


@pytest.mark.asyncio
async def test_reflect_uses_supported_schema_and_customer_tag():
    from munshi.memory.client import reflect_on_memories

    structured = {"requirements": [], "conflicts": [], "playbook": "Synthetic"}
    sdk = MagicMock()
    sdk.areflect = AsyncMock(return_value=SimpleNamespace(structured_output=structured))
    with patch(
        "munshi.memory.client.get_hindsight_client",
        return_value=_client_with_sdk(sdk),
    ):
        response = await reflect_on_memories(
            "munshi-demo",
            "synthetic query",
            tags=["customer:cust-a"],
            tags_match="all",
        )

    assert response == structured
    assert sdk.areflect.await_args.kwargs["response_schema"]["required"] == [
        "requirements",
        "conflicts",
        "playbook",
    ]
    assert sdk.areflect.await_args.kwargs["tags"] == ["customer:cust-a"]


@pytest.mark.asyncio
async def test_create_bank_uses_sdk_async_api():
    from munshi.memory.client import create_bank

    sdk = MagicMock()
    sdk.acreate_bank = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda **_: {"bank_id": "munshi-demo"})
    )
    with patch(
        "munshi.memory.client.get_hindsight_client",
        return_value=_client_with_sdk(sdk),
    ):
        response = await create_bank(
            "munshi-demo",
            name="Demo supplier",
            mission="Synthetic mission",
            background="Synthetic background",
        )

    assert response["bank_id"] == "munshi-demo"
    sdk.acreate_bank.assert_awaited_once()


@pytest.mark.asyncio
async def test_client_close_resets_singleton_for_next_application_lifespan():
    from munshi.memory.client import HindsightClient

    client = HindsightClient()
    client._client = MagicMock()
    client._client.aclose = AsyncMock()
    await client.aclose()

    assert HindsightClient._instance is None
