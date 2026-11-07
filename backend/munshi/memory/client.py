"""Hindsight SDK adapter. Only this module may import hindsight_client."""

import logging
from datetime import datetime
from typing import Any, Optional

from munshi.config import settings

logger = logging.getLogger(__name__)


class HindsightUnavailable(RuntimeError):
    """Raised when the Hindsight client is not configured or an operation fails."""


def _dump_response(response: Any) -> Any:
    if isinstance(response, (dict, list)):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    if hasattr(response, "__dict__"):
        return vars(response)
    return response


def _as_budget(value: int | str | None, default: str = "mid") -> str:
    if value in ("low", "mid", "high"):
        return value
    if isinstance(value, int):
        return "low" if value <= 2048 else "mid" if value <= 4096 else "high"
    return default


def _metadata_strings(metadata: dict[str, Any] | None) -> dict[str, str] | None:
    if metadata is None:
        return None
    return {str(key): str(value) for key, value in metadata.items() if value is not None}


class HindsightClient:
    """Configured singleton wrapping the official synchronous/async SDK client."""

    _instance: Optional["HindsightClient"] = None

    def __new__(cls) -> "HindsightClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._client: Any = None
        self._initialize()

    def _initialize(self) -> None:
        base_url = settings.HINDSIGHT_URL
        is_local = bool(settings.HINDSIGHT_LOCAL_URL)
        api_key = settings.HINDSIGHT_API_KEY
        if not base_url or (not is_local and not api_key):
            logger.info("Hindsight client is not configured")
            return

        try:
            from hindsight_client import Hindsight
        except ImportError:
            logger.warning("Hindsight SDK is not installed")
            return

        try:
            self._client = Hindsight(
                base_url=base_url,
                api_key=None if is_local else api_key,
                timeout=float(settings.HINDSIGHT_TIMEOUT),
            )
        except Exception as exc:
            logger.error("Hindsight client initialization failed (%s)", type(exc).__name__)

    @property
    def client(self) -> Any:
        if self._client is None:
            raise HindsightUnavailable("Hindsight is not configured")
        return self._client

    @property
    def is_available(self) -> bool:
        """Whether the SDK is configured; network health is checked asynchronously."""
        return self._client is not None

    async def check_available(self) -> bool:
        if not self.is_available:
            return False
        try:
            await self.client.aget_version()
            return True
        except Exception as exc:
            logger.warning("Hindsight health check failed (%s)", type(exc).__name__)
            return False

    def get_config(self, bank_name: str) -> dict[str, Any]:
        from munshi.memory.bank_setup import get_bank_config

        return get_bank_config(bank_name)

    async def aclose(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception as exc:
                logger.warning("Hindsight client close failed (%s)", type(exc).__name__)
            finally:
                self._client = None
                type(self)._instance = None

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception as exc:
                logger.warning("Hindsight client close failed (%s)", type(exc).__name__)
            finally:
                self._client = None
                type(self)._instance = None


def get_hindsight_client() -> HindsightClient:
    return HindsightClient()


def is_hindsight_available() -> bool:
    return get_hindsight_client().is_available


def _unavailable(operation: str, bank_id: str, exc: Exception) -> HindsightUnavailable:
    logger.warning(
        "Hindsight %s failed for bank %s (%s)",
        operation,
        bank_id,
        type(exc).__name__,
    )
    return HindsightUnavailable(f"Hindsight {operation} failed")


async def create_bank(
    bank_id: str,
    name: str | None = None,
    mission: str | None = None,
    background: str | None = None,
    disposition: dict[str, float] | None = None,
) -> dict[str, Any]:
    sdk = get_hindsight_client().client
    try:
        response = await sdk.acreate_bank(
            bank_id=bank_id,
            name=name,
            mission=mission,
            background=background,
            disposition=disposition,
        )
        return _dump_response(response)
    except Exception as exc:
        if getattr(exc, "status", None) == 409 or getattr(exc, "status_code", None) == 409:
            try:
                existing = await sdk.banks.get_bank_profile(bank_id=bank_id)
                return _dump_response(existing)
            except Exception:
                pass
        raise _unavailable("create bank", bank_id, exc) from exc


async def retain_event(
    bank_id: str,
    content: str,
    context: str | None = None,
    metadata: dict[str, Any] | None = None,
    timestamp: datetime | None = None,
    tags: list[str] | None = None,
    document_id: str | None = None,
) -> dict[str, Any]:
    sdk = get_hindsight_client().client
    try:
        response = await sdk.aretain(
            bank_id=bank_id,
            content=content,
            context=context,
            metadata=_metadata_strings(metadata),
            timestamp=timestamp,
            tags=tags,
            document_id=document_id,
        )
        result = _dump_response(response)
        if not result.get("success", False):
            raise HindsightUnavailable("Hindsight did not confirm memory retention")
        if document_id:
            result["document_id"] = document_id
        return result
    except HindsightUnavailable:
        raise
    except Exception as exc:
        raise _unavailable("retain", bank_id, exc) from exc


async def retain_events_batch(
    bank_id: str,
    items: list[dict[str, Any]],
    retain_async: bool = False,
) -> list[dict[str, Any]]:
    results = []
    for item in items:
        results.append(
            await retain_event(
                bank_id=bank_id,
                content=item["content"],
                context=item.get("context"),
                metadata=item.get("metadata"),
                timestamp=item.get("timestamp"),
                tags=item.get("tags"),
                document_id=item.get("document_id"),
            )
        )
    return results


async def recall_memories(
    bank_id: str,
    query: str,
    max_tokens: int = 4096,
    budget: int | str | None = None,
    types: list[str] | None = None,
    include_entities: bool = True,
    tags: list[str] | None = None,
    tags_match: str = "any",
) -> list[dict[str, Any]]:
    sdk = get_hindsight_client().client
    try:
        response = await sdk.arecall(
            bank_id=bank_id,
            query=query,
            max_tokens=max_tokens,
            budget=_as_budget(budget),
            types=types,
            include_entities=include_entities,
            tags=tags,
            tags_match=tags_match,
        )
        return [
            {
                **_dump_response(item),
                "content": item.text,
                "kind": item.type,
                "timestamp": getattr(item, "occurred_start", None)
                or getattr(item, "mentioned_at", None),
                "customer_id": (item.metadata or {}).get("customer_id"),
                "invoice_id": (item.metadata or {}).get("invoice_id"),
            }
            for item in response.results
        ]
    except Exception as exc:
        raise _unavailable("recall", bank_id, exc) from exc


_REFLECT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "description": {"type": "string"},
                    "required": {"type": "boolean"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "evidence_count": {"type": "integer"},
                },
                "required": ["code", "description"],
            },
        },
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "description": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["code", "description"],
            },
        },
        "playbook": {"type": "string"},
    },
    "required": ["requirements", "conflicts", "playbook"],
}


async def reflect_on_memories(
    bank_id: str,
    query: str,
    context: str | None = None,
    budget: int | str = "low",
    tags: list[str] | None = None,
    tags_match: str = "any",
) -> dict[str, Any]:
    sdk = get_hindsight_client().client
    try:
        response = await sdk.areflect(
            bank_id=bank_id,
            query=query,
            context=context,
            budget=_as_budget(budget, default="low"),
            max_tokens=budget if isinstance(budget, int) else None,
            response_schema=_REFLECT_RESPONSE_SCHEMA,
            tags=tags,
            tags_match=tags_match,
        )
        if response.structured_output:
            return response.structured_output
        return {
            "requirements": [],
            "conflicts": [],
            "playbook": response.text or "",
        }
    except Exception as exc:
        raise _unavailable("reflect", bank_id, exc) from exc


async def list_bank_memories(
    bank_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    sdk = get_hindsight_client().client
    try:
        response = await sdk.alist_memories(
            bank_id=bank_id,
            limit=limit,
            offset=offset,
        )
        return [
            {
                **_dump_response(item),
                "content": item.text,
                "kind": item.fact_type,
                "timestamp": getattr(item, "occurred_start", None)
                or getattr(item, "var_date", None)
                or getattr(item, "mentioned_at", None),
            }
            for item in response.items
        ]
    except Exception as exc:
        raise _unavailable("list memories", bank_id, exc) from exc


async def create_mental_model(
    bank_id: str,
    name: str,
    source_query: str,
    tags: list[str] | None = None,
    max_tokens: int = 8192,
    trigger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sdk = get_hindsight_client().client
    try:
        return _dump_response(
            await sdk.acreate_mental_model(
                bank_id=bank_id,
                name=name,
                source_query=source_query,
                tags=tags,
                max_tokens=max_tokens,
                trigger=trigger,
            )
        )
    except Exception as exc:
        raise _unavailable("create mental model", bank_id, exc) from exc


async def list_mental_models(bank_id: str, tags: list[str] | None = None) -> list[Any]:
    sdk = get_hindsight_client().client
    try:
        response = await sdk.alist_mental_models(bank_id=bank_id, tags=tags)
        if hasattr(response, "items"):
            return [_dump_response(item) for item in response.items]
        return _dump_response(response)
    except Exception as exc:
        raise _unavailable("list mental models", bank_id, exc) from exc


async def get_mental_model(bank_id: str, mental_model_id: str) -> dict[str, Any]:
    sdk = get_hindsight_client().client
    try:
        return _dump_response(
            await sdk.aget_mental_model(bank_id=bank_id, mental_model_id=mental_model_id)
        )
    except Exception as exc:
        raise _unavailable("get mental model", bank_id, exc) from exc


async def refresh_mental_model(bank_id: str, mental_model_id: str) -> dict[str, Any]:
    sdk = get_hindsight_client().client
    try:
        return _dump_response(
            await sdk.arefresh_mental_model(
                bank_id=bank_id,
                mental_model_id=mental_model_id,
            )
        )
    except Exception as exc:
        raise _unavailable("refresh mental model", bank_id, exc) from exc
