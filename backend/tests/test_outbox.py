"""
Munshi - Test memory outbox
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, MagicMock as Mock


class TestOutboxProcessor:
    """Test OutboxProcessor class."""
    
    @pytest.fixture
    def outbox_processor(self):
        """Create OutboxProcessor instance."""
        from munshi.memory.outbox import OutboxProcessor
        processor = OutboxProcessor()
        return processor
    
    def test_outbox_processor_initialization(self, outbox_processor):
        """Test OutboxProcessor initialization."""
        assert outbox_processor._running is False
        assert outbox_processor._interval_seconds == 60
        assert outbox_processor._max_retries == 5
    
    def test_outbox_processor_custom_config(self):
        """Test OutboxProcessor with custom config."""
        import os
        from munshi.memory.outbox import OutboxProcessor
        
        with patch.dict(os.environ, {
            "OUTBOX_INTERVAL": "120",
            "OUTBOX_MAX_RETRIES": "3",
            "OUTBOX_RETRY_DELAY": "600",
        }):
            processor = OutboxProcessor()
            assert processor._interval_seconds == 120
            assert processor._max_retries == 3
            assert processor._retry_delay_seconds == 600


class TestOutboxOperations:
    """Test outbox operations."""
    
    @pytest.mark.asyncio
    async def test_queue_memory_event(self):
        """Test queuing a memory event."""
        from munshi.memory.outbox import queue_memory_event
        
        with patch('munshi.memory.outbox.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = iter([mock_session])
            
            # Mock MemoryEvent
            with patch('munshi.memory.outbox.MemoryEvent') as MockMemoryEvent:
                mock_event = MagicMock()
                mock_event.id = 1
                MockMemoryEvent.return_value = mock_event
                
                result = await queue_memory_event(
                    bank_name="munshi-test",
                    content="Test content",
                    timestamp=datetime.now(),
                )
                
                assert result is not None


class TestMarkEventStatus:
    """Test marking event status."""
    
    @pytest.mark.asyncio
    async def test_mark_event_as_retained(self):
        """Test marking event as retained."""
        from munshi.memory.outbox import mark_event_as_retained
        
        with patch('munshi.memory.outbox.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = iter([mock_session])
            
            # Mock select and result
            mock_result = MagicMock()
            mock_event = MagicMock()
            mock_event.id = 1
            mock_result.first.return_value = mock_event
            mock_session.exec.return_value = mock_result
            
            result = await mark_event_as_retained(
                event_id=1,
                document_id="doc_123",
            )
            
            assert result is True
            mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_mark_event_as_retained_not_found(self):
        """Test marking non-existent event as retained."""
        from munshi.memory.outbox import mark_event_as_retained
        
        with patch('munshi.memory.outbox.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = iter([mock_session])
            
            mock_result = MagicMock()
            mock_result.first.return_value = None
            mock_session.exec.return_value = mock_result
            
            result = await mark_event_as_retained(
                event_id=999,
                document_id="doc_123",
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_mark_event_as_failed(self):
        """Test marking event as failed."""
        from munshi.memory.outbox import mark_event_as_failed
        
        with patch('munshi.memory.outbox.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = iter([mock_session])
            
            mock_result = MagicMock()
            mock_event = MagicMock()
            mock_event.id = 1
            mock_result.first.return_value = mock_event
            mock_session.exec.return_value = mock_result
            
            result = await mark_event_as_failed(
                event_id=1,
                error="Hindsight unavailable",
            )
            
            assert result is True
            mock_session.commit.assert_called_once()


class TestRetryFailedEvents:
    """Test retrying failed events."""
    
    @pytest.mark.asyncio
    async def test_retry_failed_events(self):
        """Test retrying failed events."""
        from munshi.memory.outbox import retry_failed_events
        
        with patch('munshi.memory.outbox.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = iter([mock_session])
            
            # Mock failed events
            mock_result = MagicMock()
            mock_event1 = MagicMock()
            mock_event1.id = 1
            mock_event2 = MagicMock()
            mock_event2.id = 2
            mock_result.all.return_value = [mock_event1, mock_event2]
            mock_session.exec.return_value = mock_result
            
            result = await retry_failed_events()
            
            assert len(result) == 2
            assert result == [1, 2]


class TestGetPendingCount:
    """Test getting pending event count."""
    
    @pytest.mark.asyncio
    async def test_get_pending_count(self):
        """Test getting pending count."""
        from munshi.memory.outbox import OutboxProcessor
        
        processor = OutboxProcessor()
        
        with patch('munshi.memory.outbox.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = iter([mock_session])
            
            mock_result = MagicMock()
            mock_event1 = MagicMock()
            mock_event2 = MagicMock()
            mock_result.all.return_value = [mock_event1, mock_event2]
            mock_session.exec.return_value = mock_result
            
            count = await processor.get_pending_count()
            
            assert count == 2


class TestGetFailedCount:
    """Test getting failed event count."""
    
    @pytest.mark.asyncio
    async def test_get_failed_count(self):
        """Test getting failed count."""
        from munshi.memory.outbox import OutboxProcessor
        
        processor = OutboxProcessor()
        
        with patch('munshi.memory.outbox.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = iter([mock_session])
            
            mock_result = MagicMock()
            mock_event1 = MagicMock()
            mock_result.all.return_value = [mock_event1]
            mock_session.exec.return_value = mock_result
            
            count = await processor.get_failed_count()
            
            assert count == 1
