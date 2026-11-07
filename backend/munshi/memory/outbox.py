"""
Munshi - Memory outbox

This module handles retry mechanism for failed Hindsight retains.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlmodel import Session, select

from munshi.db.session import get_session
from munshi.db.models import MemoryEvent

logger = logging.getLogger(__name__)


class OutboxProcessor:
    """
    Process outbox for failed Hindsight retains.
    
    Memory events with retained_at = NULL are retried periodically.
    Failed events are retried up to MAX_RETRIES before being marked as permanently failed.
    """
    
    def __init__(self):
        self._running = False
        self._interval_seconds = int(os.getenv("OUTBOX_INTERVAL", "60"))
        self._max_retries = int(os.getenv("OUTBOX_MAX_RETRIES", "5"))
        self._retry_delay_seconds = int(os.getenv("OUTBOX_RETRY_DELAY", "300"))
    
    async def start(self) -> None:
        """Start outbox processor."""
        self._running = True
        logger.info("Memory outbox processor started")
        while self._running:
            await self.process_outbox()
            await asyncio.sleep(self._interval_seconds)
    
    async def stop(self) -> None:
        """Stop outbox processor."""
        self._running = False
        logger.info("Memory outbox processor stopped")
    
    async def process_outbox(self) -> None:
        """Process pending memory events."""
        session = next(get_session())
        try:
            # Get events that haven't been retained (or failed)
            statement = select(MemoryEvent).where(
                MemoryEvent.retained_at == None,
                MemoryEvent.failed_at == None
            ).order_by(MemoryEvent.created_at)
            
            results = session.exec(statement)
            pending_events = results.all()
            
            for event in pending_events:
                await self._attempt_retain(event, session)
        
        except Exception as e:
            logger.error(f"Error processing outbox: {e}")
        finally:
            session.close()
    
    async def _attempt_retain(self, event: MemoryEvent, session: Session) -> None:
        """
        Attempt to retain a single event.
        
        Args:
            event: MemoryEvent to retain
            session: Database session
        """
        try:
            # Check if Hindsight is available
            from munshi.memory.client import is_hindsight_available
            
            if not is_hindsight_available():
                logger.warning("Hindsight unavailable, skipping retain")
                return
            
            # Attempt to retain
            from munshi.memory.client import retain_event
            from munshi.memory.events import format_event_content, generate_event_tags
            
            bank_name = event.bank_name
            timestamp = event.timestamp
            content = event.content or format_event_content(event.event_type, event.details or {})
            tags = generate_event_tags(
                customer_id=event.customer_id,
                event_kind=event.event_type or "action",
                invoice_id=event.invoice_id,
            )
            
            response = await retain_event(
                bank_id=bank_name,
                content=content,
                context=event.context,
                metadata=event.metadata or {},
                timestamp=timestamp,
            )
            
            if response:
                # Success
                event.retained_at = datetime.now()
                event.document_id = response.get("document_id")
                event.retry_count = 0
                session.commit()
                session.refresh(event)
                logger.info(f"Retained memory event: {event.id}")
            else:
                # Retain returned None (Hindsight unavailable)
                self._increment_retry(event, session)
        
        except Exception as e:
            logger.error(f"Error retaining event {event.id}: {e}")
            self._increment_retry(event, session)
    
    def _increment_retry(self, event: MemoryEvent, session: Session) -> None:
        """
        Increment retry count and check if permanently failed.
        
        Args:
            event: MemoryEvent
            session: Database session
        """
        event.retry_count = (event.retry_count or 0) + 1
        
        if event.retry_count >= self._max_retries:
            event.failed_at = datetime.now()
            logger.error(
                f"Memory event {event.id} failed after {event.retry_count} retries"
            )
        else:
            # Schedule retry with exponential backoff
            next_retry = datetime.now().timestamp() + (
                self._retry_delay_seconds * (2 ** (event.retry_count - 1))
            )
            event.next_retry_at = datetime.fromtimestamp(next_retry)
        
        session.commit()
        session.refresh(event)
    
    async def get_pending_count(self) -> int:
        """
        Get count of pending events in outbox.
        
        Returns:
            Number of pending events
        """
        session = next(get_session())
        try:
            statement = select(MemoryEvent).where(
                MemoryEvent.retained_at == None,
                MemoryEvent.failed_at == None
            )
            results = session.exec(statement)
            return len(results.all())
        finally:
            session.close()
    
    async def get_failed_count(self) -> int:
        """
        Get count of permanently failed events.
        
        Returns:
            Number of failed events
        """
        session = next(get_session())
        try:
            statement = select(MemoryEvent).where(
                MemoryEvent.failed_at != None
            )
            results = session.exec(statement)
            return len(results.all())
        finally:
            session.close()


# Global outbox processor instance
outbox_processor = OutboxProcessor()


async def queue_memory_event(
    bank_name: str,
    content: str,
    timestamp: datetime,
    customer_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
    event_type: str = None,
    context: str = None,
    details: Dict[str, Any] = None,
    metadata: Dict[str, Any] = None,
) -> MemoryEvent:
    """
    Queue a memory event for retention.
    
    Args:
        bank_name: Bank name
        content: Event content
        timestamp: Event timestamp
        customer_id: Customer ID (optional)
        invoice_id: Invoice ID (optional)
        event_type: Type of event
        context: Context string
        details: Event details
        metadata: Additional metadata
    
    Returns:
        Created MemoryEvent
    """
    session = next(get_session())
    try:
        from munshi.db.models import MemoryEvent
        
        event = MemoryEvent(
            bank_name=bank_name,
            content=content,
            timestamp=timestamp,
            customer_id=customer_id,
            invoice_id=invoice_id,
            event_type=event_type,
            context=context,
            details=details,
            metadata=metadata,
            retained_at=None,
            failed_at=None,
            retry_count=0,
        )
        
        session.add(event)
        session.commit()
        session.refresh(event)
        logger.info(f"Queued memory event: {event.id}")
        return event
    finally:
        session.close()


async def mark_event_as_retained(event_id: int, document_id: str) -> bool:
    """
    Mark an event as successfully retained.
    
    Args:
        event_id: MemoryEvent ID
        document_id: Hindsight document ID
    
    Returns:
        True if successful
    """
    session = next(get_session())
    try:
        statement = select(MemoryEvent).where(MemoryEvent.id == event_id)
        result = session.exec(statement).first()
        
        if not result:
            return False
        
        result.retained_at = datetime.now()
        result.document_id = document_id
        session.commit()
        return True
    finally:
        session.close()


async def mark_event_as_failed(event_id: int, error: str) -> bool:
    """
    Mark an event as permanently failed.
    
    Args:
        event_id: MemoryEvent ID
        error: Error message
    
    Returns:
        True if successful
    """
    session = next(get_session())
    try:
        statement = select(MemoryEvent).where(MemoryEvent.id == event_id)
        result = session.exec(statement).first()
        
        if not result:
            return False
        
        result.failed_at = datetime.now()
        result.error = error
        session.commit()
        return True
    finally:
        session.close()


async def retry_failed_events() -> List[int]:
    """
    Retry all failed events.
    
    Returns:
        List of successfully retried event IDs
    """
    session = next(get_session())
    try:
        statement = select(MemoryEvent).where(
            MemoryEvent.failed_at != None
        )
        results = session.exec(statement)
        failed_events = results.all()
        
        retried = []
        for event in failed_events:
            event.failed_at = None
            event.retry_count = 0
            session.commit()
            retried.append(event.id)
        
        logger.info(f"Retried {len(retried)} failed events")
        return retried
    finally:
        session.close()
