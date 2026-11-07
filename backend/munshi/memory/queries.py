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
        if not self.is_available:
            logger.warning(f"Cannot create bank {bank_name}: Hindsight unavailable")
            return None
        
        try:
            from munshi.memory.bank_setup import get_bank_config
            
            config = get_bank_config(bank_name, business_name or "Demo Business")
            
            response = await create_bank(
                bank_id=bank_name,
                name=business_name or bank_name,
                background=config["retained_mission"],
                disposition=config["disposition"],
            )
            
            if response:
                self._banks[bank_name] = config
                logger.info(f"Created memory bank: {bank_name}")
            
            return response
        except Exception as e:
            logger.error(f"Failed to create bank {bank_name}: {e}")
            return None
    
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
        if not self.is_available:
            logger.warning(f"Hindsight unavailable - skipping retain for {bank_name}")
            return None
        
        if tags is None:
            tags = []
        
        # Build comprehensive tags
        all_tags = tags.copy()
        if customer_id:
            all_tags.append(f"customer:{customer_id}")
        if invoice_id:
            all_tags.append(f"invoice:{invoice_id}")
        if event_type:
            all_tags.append(f"kind:{event_type}")
        
        try:
            response = await retain_event(
                bank_id=bank_name,
                content=content,
                context=None,
                metadata={
                    "event_type": event_type,
                    "customer_id": customer_id,
                    "invoice_id": invoice_id,
                    **metadata,
                },
                timestamp=timestamp,
            )
            
            if response:
                logger.debug(f"Retained event in {bank_name}: {response.get('document_id', 'unknown')}")
            
            return response
        except Exception as e:
            logger.error(f"Failed to retain event in {bank_name}: {e}")
            return None
    
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
        if not self.is_available:
            logger.warning(f"Hindsight unavailable - skipping batch retain for {bank_name}")
            return []
        
        items = []
        for event in events:
            items.append({
                "content": event.get("content", ""),
                "context": event.get("context"),
                "metadata": event.get("metadata", {}),
                "timestamp": event.get("timestamp"),
            })
        
        try:
            from munshi.memory.client import retain_events_batch
            response = await retain_events_batch(bank_id=bank_name, items=items)
            logger.info(f"Retained {len(events)} events in {bank_name}")
            return response
        except Exception as e:
            logger.error(f"Failed to batch retain events in {bank_name}: {e}")
            return []
    
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
        if not self.is_available:
            logger.warning(f"Hindsight unavailable - skipping recall for {bank_name}")
            return []
        
        # Build query with filters
        if query is None:
            query = ""
        
        if customer_id:
            query = f"customer:{customer_id} {query}".strip()
        
        if kind:
            query = f"kind:{kind} {query}".strip()
        
        try:
            max_tokens = k * 400  # Approximate tokens per result
            
            memories = await recall_memories(
                bank_id=bank_name,
                query=query,
                max_tokens=max_tokens,
            )
            
            parsed = parse_memory_events(memories)
            logger.debug(f"Recalled {len(parsed)} memories from {bank_name}")
            return parsed
        except Exception as e:
            logger.error(f"Failed to recall memories from {bank_name}: {e}")
            return []
    
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
        if not self.is_available:
            logger.warning(f"Hindsight unavailable - skipping reflect for {bank_name}")
            return {"requirements": [], "conflicts": [], "playbook": ""}
        
        # Build query with customer filter
        full_query = query or ""
        if customer_id:
            full_query = f"Customer: {customer_id}. {full_query}".strip()
        
        try:
            response = await reflect_on_memories(
                bank_id=bank_name,
                query=full_query,
                context=context,
            )
            
            parsed = parse_reflect_response(response)
            logger.debug(f"Reflected on memories in {bank_name}")
            return {
                "requirements": parsed.requirements,
                "conflicts": parsed.conflicts,
                "playbook": parsed.playbook,
            }
        except Exception as e:
            logger.error(f"Failed to reflect on memories in {bank_name}: {e}")
            return {"requirements": [], "conflicts": [], "playbook": ""}
    
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
        if not self.is_available:
            logger.warning(f"Hindsight unavailable - skipping list_memories for {bank_name}")
            return []
        
        try:
            memories = await list_bank_memories(
                bank_id=bank_name,
                limit=limit,
                offset=offset,
            )
            return parse_memory_events(memories)
        except Exception as e:
            logger.error(f"Failed to list memories in {bank_name}: {e}")
            return []
    
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
