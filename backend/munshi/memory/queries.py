"""
Munshi - Memory queries

This module handles reflect and recall operations for memory retrieval.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from munshi.memory.client import (
    get_hindsight_client,
    is_hindsight_available,
    recall_memories,
    reflect_on_memories,
    list_bank_memories,
    create_bank,
    retain_event,
)
from munshi.memory.parsing import parse_reflect_response, parse_memory_events

logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Memory store interface for Hindsight operations.
    
    This class wraps Hindsight's reflect and recall operations
    and provides a consistent interface for agents.
    """
    
    def __init__(self):
        self.client = None
        self._is_initialized = False
        self._banks = {}  # Cache of created banks
    
    def initialize(self) -> bool:
        """
        Initialize the memory store.
        
        Returns:
            True if Hindsight is available, False otherwise
        """
        if self._is_initialized:
            return self.is_available
        
        self._is_initialized = True
        return self.is_available
    
    @property
    def is_available(self) -> bool:
        """Check if Hindsight service is available."""
        return is_hindsight_available()
    
    def get_bank_name(self, business_slug: str, is_demo: bool = False) -> str:
        """
        Get bank name for a business.
        
        Args:
            business_slug: Business identifier
            is_demo: Use demo prefix
        
        Returns:
            Bank name
        """
        from munshi.memory.bank_setup import get_bank_name
        return get_bank_name(business_slug, is_demo=is_demo)

    async def _ensure_bank(self, bank_name: str) -> None:
        if bank_name in self._banks:
            return
        from munshi.memory.bank_setup import get_bank_config

        config = get_bank_config(bank_name)
        await create_bank(
            bank_id=bank_name,
            name=bank_name,
            mission=config["reflect_mission"],
            background=config["retained_mission"],
            disposition=config["disposition"],
        )
        self._banks[bank_name] = config
    
    async def create_bank(
        self,
        bank_name: str,
        business_name: str = None,
        is_demo: bool = False,
    ) -> dict:
        """
        Create a new memory bank for a business.
        
        Args:
            bank_name: Bank identifier
            business_name: Business name for configuration
            is_demo: Use demo configuration
        
        Returns:
            Bank creation response
        """
        from munshi.memory.bank_setup import get_bank_config

        config = get_bank_config(bank_name, business_name or "Demo Business")
        response = await create_bank(
            bank_id=bank_name,
            name=business_name or bank_name,
            mission=config["reflect_mission"],
            background=config["retained_mission"],
            disposition=config["disposition"],
        )
        self._banks[bank_name] = config
        logger.info("Created/accessed memory bank %s", bank_name)
        return response
    
    async def retain(
        self,
        bank_name: str,
        timestamp: datetime,
        customer_id: Optional[str],
        invoice_id: Optional[str],
        content: str,
        tags: List[str] = None,
        event_type: str = None,
        **metadata,
    ) -> dict:
        """
        Retain an event in Hindsight.
        
        Args:
            bank_name: Bank name
            timestamp: Event timestamp
            customer_id: Customer ID (optional)
            invoice_id: Invoice ID (optional)
            content: Event content
            tags: Event tags
            event_type: Type of event
            **metadata: Additional metadata
        
        Returns:
            Retain response with document_id
        """
        if tags is None:
            tags = []
        await self._ensure_bank(bank_name)
        
        # Build comprehensive tags
        all_tags = tags.copy()
        if customer_id:
            all_tags.append(f"customer:{customer_id}")
        if invoice_id:
            all_tags.append(f"invoice:{invoice_id}")
        if event_type:
            all_tags.append(f"kind:{event_type}")
        
        response = await retain_event(
            bank_id=bank_name,
            content=content,
            context=None,
            metadata={
                "event_type": event_type or "",
                "customer_id": customer_id or "",
                "invoice_id": invoice_id or "",
                **metadata,
            },
            timestamp=timestamp,
            tags=all_tags,
        )
        logger.debug("Retained memory event in bank %s", bank_name)
        return response
    
    async def retain_batch(
        self,
        bank_name: str,
        events: List[Dict[str, Any]],
    ) -> List[dict]:
        """
        Retain multiple events in batch.
        
        Args:
            bank_name: Bank name
            events: List of event dicts with content, timestamp, customer_id, etc.
        
        Returns:
            List of retain responses
        """
        items = []
        await self._ensure_bank(bank_name)
        for event in events:
            event_tags = list(event.get("tags", []))
            customer_id = event.get("customer_id")
            invoice_id = event.get("invoice_id")
            if customer_id:
                event_tags.append(f"customer:{customer_id}")
            if invoice_id:
                event_tags.append(f"invoice:{invoice_id}")
            if event.get("event_type"):
                event_tags.append(f"kind:{event['event_type']}")
            items.append({
                "content": event.get("content", ""),
                "context": event.get("context"),
                "metadata": event.get("metadata", {}),
                "timestamp": event.get("timestamp"),
                "tags": list(dict.fromkeys(event_tags)),
                "document_id": event.get("document_id"),
            })
        from munshi.memory.client import retain_events_batch

        response = await retain_events_batch(bank_id=bank_name, items=items)
        logger.info("Retained %d events in bank %s", len(events), bank_name)
        return response
    
    async def recall(
        self,
        bank_name: str,
        customer_id: Optional[str] = None,
        kind: str = None,
        query: str = None,
        k: int = 10,
        cutoff_days: int = 365,
    ) -> List[Dict[str, Any]]:
        """
        Recall facts/observations from Hindsight.
        
        Args:
            bank_name: Bank name
            customer_id: Filter by customer ID
            kind: Filter by memory type (action, observation, reminder, promise, payment)
            query: Search query
            k: Number of results
            cutoff_days: Lookback period
        
        Returns:
            List of memory events
        """
        # Build query with filters
        if query is None:
            query = ""
        await self._ensure_bank(bank_name)
        
        if customer_id:
            query = f"customer:{customer_id} {query}".strip()
        
        if kind:
            query = f"kind:{kind} {query}".strip()
        
        tags = []
        if customer_id:
            tags.append(f"customer:{customer_id}")
        if kind:
            tags.append(f"kind:{kind}")
        memories = await recall_memories(
            bank_id=bank_name,
            query=query,
            max_tokens=k * 400,
            tags=tags or None,
            tags_match="all",
        )
        parsed = parse_memory_events(memories)
        logger.debug("Recalled %d memories from bank %s", len(parsed), bank_name)
        return parsed
    
    async def reflect(
        self,
        bank_name: str,
        customer_id: Optional[str] = None,
        query: str = None,
        context: str = None,
    ) -> Dict[str, Any]:
        """
        Call reflect on Hindsight to derive insights.
        
        Args:
            bank_name: Bank name
            customer_id: Filter by customer ID
            query: Query string (e.g., "How do we get paid on time by Reddy Traders?")
            context: Additional context
        
        Returns:
            JSON with requirements[], conflicts[], playbook text
        """
        # Build query with customer filter
        full_query = query or ""
        await self._ensure_bank(bank_name)
        tags = []
        if customer_id:
            full_query = f"Customer: {customer_id}. {full_query}".strip()
            tags.append(f"customer:{customer_id}")
        response = await reflect_on_memories(
            bank_id=bank_name,
            query=full_query,
            context=context,
            tags=tags or None,
            tags_match="all",
        )
        parsed = parse_reflect_response(response)
        logger.debug("Reflected on memories in bank %s", bank_name)
        return {
            "requirements": [item.model_dump() for item in parsed.requirements],
            "conflicts": [item.model_dump() for item in parsed.conflicts],
            "playbook": parsed.playbook,
        }
    
    async def get_playbook(
        self,
        bank_name: str,
        customer_id: str,
    ) -> Dict[str, Any]:
        """
        Get customer's playbook (mental model).
        
        Args:
            bank_name: Bank name
            customer_id: Customer ID
        
        Returns:
            Playbook data
        """
        # Use reflect with playbook query
        query = f"How do we get paid on time by this customer? Customer ID: {customer_id}"
        return await self.reflect(bank_name=bank_name, customer_id=customer_id, query=query)
    
    async def list_memories(
        self,
        bank_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List all memories in a bank.
        
        Args:
            bank_name: Bank name
            limit: Maximum number of memories
            offset: Pagination offset
        
        Returns:
            List of memory documents
        """
        await self._ensure_bank(bank_name)
        memories = await list_bank_memories(
            bank_id=bank_name,
            limit=limit,
            offset=offset,
        )
        return parse_memory_events(memories)
    
    async def get_memory_for_readiness(
        self,
        bank_name: str,
        customer_id: str,
    ) -> Dict[str, Any]:
        """
        Get memory findings for readiness check.
        
        Args:
            bank_name: Bank name
            customer_id: Customer ID
        
        Returns:
            Memory findings dict
        """
        query = (
            "What details or documents has this customer required, "
            "why were past invoices held, and has any requirement changed?"
        )
        return await self.reflect(
            bank_name=bank_name,
            customer_id=customer_id,
            query=query,
        )
    
    async def get_memory_for_collector(
        self,
        bank_name: str,
        customer_id: str,
    ) -> Dict[str, Any]:
        """
        Get memory for Collector agent.
        
        Args:
            bank_name: Bank name
            customer_id: Customer ID
        
        Returns:
            Memory findings dict
        """
        query = "What is the best next step for this overdue invoice?"
        return await self.reflect(
            bank_name=bank_name,
            customer_id=customer_id,
            query=query,
        )
    
    async def get_memory_for_risk(
        self,
        bank_name: str,
        customer_id: str,
    ) -> Dict[str, Any]:
        """
        Get memory for Risk agent.
        
        Args:
            bank_name: Bank name
            customer_id: Customer ID
        
        Returns:
            Memory findings dict
        """
        query = "Has payment behaviour, contact or requirements changed recently?"
        return await self.reflect(
            bank_name=bank_name,
            customer_id=customer_id,
            query=query,
        )


# Global memory store instance
memory_store = MemoryStore()


async def get_memory_for_readiness(
    bank_name: str,
    customer_id: str,
) -> Dict[str, Any]:
    """Get memory findings for readiness check."""
    return await memory_store.get_memory_for_readiness(
        bank_name=bank_name,
        customer_id=customer_id,
    )


async def get_memory_for_collector(
    bank_name: str,
    customer_id: str,
) -> Dict[str, Any]:
    """Get memory for Collector agent."""
    return await memory_store.get_memory_for_collector(
        bank_name=bank_name,
        customer_id=customer_id,
    )


async def get_memory_for_risk(
    bank_name: str,
    customer_id: str,
) -> Dict[str, Any]:
    """Get memory for Risk agent."""
    return await memory_store.get_memory_for_risk(
        bank_name=bank_name,
        customer_id=customer_id,
    )
