"""
Munshi - Hindsight client wrapper

This module wraps the Hindsight SDK client and provides initialization.
IMPORTANT: Only this file may import hindsight_client.
"""

import logging
from typing import Optional
from datetime import datetime

from munshi.config import settings

logger = logging.getLogger(__name__)


class HindsightClient:
    """
    Wrapper around Hindsight SDK client.
    
    This class handles:
    - Client initialization (Cloud or local)
    - Configuration
    - Error handling
    - Graceful degradation when Hindsight is unavailable
    
    Never import hindsight_client outside this file.
    """
    
    _instance: Optional["HindsightClient"] = None
    
    def __new__(cls):
        """Singleton pattern for client."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        self._client = None
        self._config = None
        self._is_available = False
        
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize Hindsight client based on configuration."""
        try:
            import hindsight_client
        except ImportError:
            logger.warning(
                "hindsight_client not installed. Memory operations will be disabled. "
                "Install with: pip install hindsight-client"
            )
            return
        
        # Try local URL first, then Cloud
        local_url = settings.HINDSIGHT_LOCAL_URL
        base_url = settings.HINDSIGHT_BASE_URL
        api_key = settings.HINDSIGHT_API_KEY
        timeout = settings.HINDSIGHT_TIMEOUT
        
        if local_url:
            try:
                self._client = hindsight_client.Client(
                    base_url=local_url,
                    timeout=timeout
                )
                self._is_available = True
                logger.info("Hindsight client initialized with local URL")
                return
            except Exception as e:
                logger.error(f"Failed to initialize local Hindsight: {e}")
        
        if api_key and base_url:
            try:
                self._client = hindsight_client.Client(
                    base_url=base_url,
                    api_key=api_key,
                    timeout=timeout
                )
                self._is_available = True
                logger.info("Hindsight client initialized with Cloud")
                return
            except Exception as e:
                logger.error(f"Failed to initialize Cloud Hindsight: {e}")
        
        # If we get here, Hindsight is unavailable
        logger.warning(
            "Hindsight client not configured. "
            "Set HINDSIGHT_LOCAL_URL or HINDSIGHT_BASE_URL + HINDSIGHT_API_KEY"
        )
    
    @property
    def client(self):
        """Get Hindsight client instance. Raises if not available."""
        if self._client is None:
            raise RuntimeError(
                "Hindsight client not initialized. "
                "Check HINDSIGHT_LOCAL_URL or HINDSIGHT_BASE_URL + HINDSIGHT_API_KEY env vars"
            )
        return self._client
    
    @property
    def is_available(self) -> bool:
        """Check if Hindsight service is available."""
        if not self._is_available:
            return False
        
        try:
            # Quick health check by listing banks
            self._client.list_banks()
            return True
        except Exception as e:
            logger.warning(f"Hindsight health check failed: {e}")
            self._is_available = False
            return False
    
    def get_config(self, bank_name: str) -> dict:
        """
        Get bank configuration with directives, missions, and disposition.
        
        Args:
            bank_name: Bank name (munshi-<slug> or eval-<run>-C-s<seed>)
        
        Returns:
            Configuration dict for bank setup
        """
        from munshi.memory.bank_setup import get_bank_config
        
        return get_bank_config(bank_name)
    
    async def aclose(self) -> None:
        """Async close of Hindsight client."""
        if self._client:
            try:
                await self._client.aclose()
            except Exception as e:
                logger.warning(f"Error closing Hindsight client: {e}")
    
    def close(self) -> None:
        """Sync close of Hindsight client."""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning(f"Error closing Hindsight client: {e}")


def get_hindsight_client() -> HindsightClient:
    """Get or create Hindsight client singleton."""
    return HindsightClient()


def is_hindsight_available() -> bool:
    """Check if Hindsight service is available."""
    client = get_hindsight_client()
    return client.is_available


async def create_bank(bank_id: str, name: str = None, background: str = None, disposition: dict = None) -> dict:
    """
    Create a new Hindsight bank.
    
    Args:
        bank_id: Unique bank identifier (munshi-<business-slug> or eval-<run>-C-s<seed>)
        name: Optional human-readable name
        background: Optional background context
        disposition: Optional personality disposition
    
    Returns:
        Bank creation response
    
    Note:
        Gracefully handles unavailable Hindsight - returns None
    """
    try:
        client = get_hindsight_client()
        if not client.is_available:
            logger.warning(f"Hindsight unavailable - skipping bank creation for {bank_id}")
            return None
        
        response = await client.client.create_bank(
            bank_id=bank_id,
            name=name,
            background=background,
            disposition=disposition
        )
        logger.info(f"Created Hindsight bank: {bank_id}")
        return response
    except Exception as e:
        logger.error(f"Failed to create bank {bank_id}: {e}")
        return None


async def retain_event(
    bank_id: str,
    content: str,
    context: str = None,
    metadata: dict = None,
    timestamp: datetime = None
) -> dict:
    """
    Retain a memory event in Hindsight.
    
    Args:
        bank_id: Bank identifier
        content: Event content to store
        context: Optional context string
        metadata: Optional metadata dict
        timestamp: Event timestamp
    
    Returns:
        Retain response with document_id
    
    Note:
        Gracefully handles unavailable Hindsight - returns None
    """
    try:
        client = get_hindsight_client()
        if not client.is_available:
            logger.warning(f"Hindsight unavailable - skipping retain for {bank_id}")
            return None
        
        response = await client.client.retain(
            bank_id=bank_id,
            content=content,
            context=context,
            metadata=metadata,
            timestamp=timestamp
        )
        logger.debug(f"Retained event in {bank_id}: {response.get('document_id', 'unknown')}")
        return response
    except Exception as e:
        logger.error(f"Failed to retain event in {bank_id}: {e}")
        return None


async def retain_events_batch(
    bank_id: str,
    items: list,
    retain_async: bool = False
) -> list:
    """
    Retain multiple memory events in batch.
    
    Args:
        bank_id: Bank identifier
        items: List of retain items with content, context, metadata, timestamp
        retain_async: Whether to process asynchronously
    
    Returns:
        List of retain responses
    
    Note:
        Gracefully handles unavailable Hindsight - returns empty list
    """
    try:
        client = get_hindsight_client()
        if not client.is_available:
            logger.warning(f"Hindsight unavailable - skipping batch retain for {bank_id}")
            return []
        
        response = await client.client.retain_batch(
            bank_id=bank_id,
            items=items,
            retain_async=retain_async
        )
        logger.info(f"Retained {len(items)} events in {bank_id}")
        return response
    except Exception as e:
        logger.error(f"Failed to batch retain events in {bank_id}: {e}")
        return []


async def recall_memories(
    bank_id: str,
    query: str,
    max_tokens: int = 4096,
    budget: int = None,
    types: list = None,
    include_entities: bool = True
) -> list:
    """
    Recall memories from Hindsight bank.
    
    Args:
        bank_id: Bank identifier
        query: Search query
        max_tokens: Maximum tokens in response
        budget: Token budget (overrides max_tokens)
        types: Filter by memory types
        include_entities: Include entity mentions
    
    Returns:
        List of matching memories
    
    Note:
        Gracefully handles unavailable Hindsight - returns empty list
    """
    try:
        client = get_hindsight_client()
        if not client.is_available:
            logger.warning(f"Hindsight unavailable - skipping recall for {bank_id}")
            return []
        
        response = await client.client.recall(
            bank_id=bank_id,
            query=query,
            max_tokens=max_tokens,
            budget=budget,
            types=types,
            include_entities=include_entities
        )
        return response
    except Exception as e:
        logger.error(f"Failed to recall memories from {bank_id}: {e}")
        return []


async def reflect_on_memories(
    bank_id: str,
    query: str,
    context: str = None,
    budget: int = 8192
) -> dict:
    """
    Reflect over memories to derive insights.
    
    Args:
        bank_id: Bank identifier
        query: Reflection query
        context: Optional context string
        budget: Token budget for reflection
    
    Returns:
        Reflection response with requirements, conflicts, playbook
    
    Note:
        Gracefully handles unavailable Hindsight - returns empty response
    """
    try:
        client = get_hindsight_client()
        if not client.is_available:
            logger.warning(f"Hindsight unavailable - skipping reflect for {bank_id}")
            return {"requirements": [], "conflicts": [], "playbook": ""}
        
        response = await client.client.reflect(
            bank_id=bank_id,
            query=query,
            context=context,
            budget=budget
        )
        return response
    except Exception as e:
        logger.error(f"Failed to reflect on memories in {bank_id}: {e}")
        return {"requirements": [], "conflicts": [], "playbook": ""}


async def list_bank_memories(
    bank_id: str,
    limit: int = 100,
    offset: int = 0
) -> list:
    """
    List all memories in a bank.
    
    Args:
        bank_id: Bank identifier
        limit: Maximum number of memories
        offset: Pagination offset
    
    Returns:
        List of memory documents
    """
    try:
        client = get_hindsight_client()
        if not client.is_available:
            logger.warning(f"Hindsight unavailable - skipping list_memories for {bank_id}")
            return []
        
        response = await client.client.list_memories(
            bank_id=bank_id,
            limit=limit,
            offset=offset
        )
        return response
    except Exception as e:
        logger.error(f"Failed to list memories in {bank_id}: {e}")
        return []


async def create_mental_model(
    bank_id: str,
    name: str,
    source_query: str,
    tags: list = None,
    max_tokens: int = 8192,
    trigger: dict = None
) -> dict:
    """
    Create a mental model (playbook) for a bank.
    
    Args:
        bank_id: Bank identifier
        name: Model name
        source_query: Query to derive model from
        tags: Model tags
        max_tokens: Token budget
        trigger: Optional trigger configuration
    
    Returns:
        Created mental model
    """
    try:
        client = get_hindsight_client()
        if not client.is_available:
            logger.warning(f"Hindsight unavailable - skipping mental_model creation for {bank_id}")
            return None
        
        response = await client.client.create_mental_model(
            bank_id=bank_id,
            name=name,
            source_query=source_query,
            tags=tags,
            max_tokens=max_tokens,
            trigger=trigger
        )
        return response
    except Exception as e:
        logger.error(f"Failed to create mental model in {bank_id}: {e}")
        return None


async def list_mental_models(bank_id: str, tags: list = None) -> list:
    """
    List mental models in a bank.
    
    Args:
        bank_id: Bank identifier
        tags: Filter by tags
    
    Returns:
        List of mental models
    """
    try:
        client = get_hindsight_client()
        if not client.is_available:
            logger.warning(f"Hindsight unavailable - skipping list_mental_models for {bank_id}")
            return []
        
        response = await client.client.list_mental_models(
            bank_id=bank_id,
            tags=tags
        )
        return response
    except Exception as e:
        logger.error(f"Failed to list mental models in {bank_id}: {e}")
        return []


async def get_mental_model(bank_id: str, mental_model_id: str) -> dict:
    """
    Get a specific mental model.
    
    Args:
        bank_id: Bank identifier
        mental_model_id: Model ID
    
    Returns:
        Mental model details
    """
    try:
        client = get_hindsight_client()
        if not client.is_available:
            logger.warning(f"Hindsight unavailable - skipping get_mental_model for {bank_id}")
            return None
        
        response = await client.client.get_mental_model(
            bank_id=bank_id,
            mental_model_id=mental_model_id
        )
        return response
    except Exception as e:
        logger.error(f"Failed to get mental model {mental_model_id} in {bank_id}: {e}")
        return None


async def refresh_mental_model(bank_id: str, mental_model_id: str) -> dict:
    """
    Refresh a mental model with new data.
    
    Args:
        bank_id: Bank identifier
        mental_model_id: Model ID
    
    Returns:
        Refreshed mental model
    """
    try:
        client = get_hindsight_client()
        if not client.is_available:
            logger.warning(f"Hindsight unavailable - skipping refresh_mental_model for {bank_id}")
            return None
        
        response = await client.client.refresh_mental_model(
            bank_id=bank_id,
            mental_model_id=mental_model_id
        )
        return response
    except Exception as e:
        logger.error(f"Failed to refresh mental model {mental_model_id} in {bank_id}: {e}")
        return None
