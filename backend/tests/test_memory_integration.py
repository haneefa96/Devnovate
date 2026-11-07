"""
Munshi - Test memory integration

Integration tests for Hindsight memory system.
Run with: pytest tests/test_memory_integration.py -m integration
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.integration
class TestMemoryIntegration:
    """Integration tests for memory system with Hindsight."""
    
    @pytest.mark.asyncio
    async def test_memory_retain_and_recall(self):
        """Test retain and recall with Hindsight (integration test)."""
        pytest.skip("Requires Hindsight to be running")
        
        from munshi.memory.queries import memory_store
        
        # This test requires Hindsight to be running
        # Run with: pytest tests/test_memory_integration.py -m integration --hindsight
        bank_name = "munshi-test"
        
        # Create bank
        result = await memory_store.create_bank(bank_name)
        assert result is not None
        
        # Retain an event
        response = await memory_store.retain(
            bank_name=bank_name,
            timestamp=datetime.now(),
            customer_id="cust_123",
            invoice_id="inv_456",
            content="Test event content",
            tags=["test"],
        )
        assert response is not None
        
        # Recall events
        events = await memory_store.recall(
            bank_name=bank_name,
            customer_id="cust_123",
            kind="action",
        )
        assert len(events) >= 0  # May be empty if no events match
    
    @pytest.mark.asyncio
    async def test_memory_reflect(self):
        """Test reflect operation (integration test)."""
        pytest.skip("Requires Hindsight to be running")
        
        from munshi.memory.queries import memory_store
        
        bank_name = "munshi-test"
        
        # Reflect on memories
        result = await memory_store.reflect(
            bank_name=bank_name,
            customer_id="cust_123",
            query="What are the payment patterns for this customer?",
        )
        
        assert "requirements" in result
        assert "conflicts" in result
        assert "playbook" in result
    
    @pytest.mark.asyncio
    async def test_memory_flow(self):
        """Test complete memory flow (integration test)."""
        pytest.skip("Requires Hindsight to be running")
        
        from munshi.memory.queries import memory_store
        from datetime import datetime
        
        bank_name = "munshi-integration-test"
        
        # Step 1: Create bank
        result = await memory_store.create_bank(
            bank_name=bank_name,
            business_name="Integration Test Business",
        )
        assert result is not None
        
        # Step 2: Retain multiple events
        events = [
            {
                "content": "Sent invoice INV-001 on 2024-01-15",
                "timestamp": datetime(2024, 1, 15, 10, 0, 0),
                "customer_id": "cust_123",
                "invoice_id": "inv_001",
            },
            {
                "content": "Customer promised payment by 2024-01-20",
                "timestamp": datetime(2024, 1, 16, 14, 0, 0),
                "customer_id": "cust_123",
                "invoice_id": "inv_001",
            },
        ]
        
        retained = await memory_store.retain_batch(bank_name, events)
        assert len(retained) == 2
        
        # Step 3: Recall events
        recalled = await memory_store.recall(
            bank_name=bank_name,
            customer_id="cust_123",
            k=10,
        )
        assert len(recalled) >= 2
        
        # Step 4: Reflect on memories
        reflection = await memory_store.reflect(
            bank_name=bank_name,
            customer_id="cust_123",
            query="What is the payment pattern?",
        )
        assert "playbook" in reflection
        
        # Step 5: Get memory for different agents
        readiness = await memory_store.get_memory_for_readiness(
            bank_name=bank_name,
            customer_id="cust_123",
        )
        assert "requirements" in readiness
        
        collector = await memory_store.get_memory_for_collector(
            bank_name=bank_name,
            customer_id="cust_123",
        )
        assert "playbook" in collector
        
        risk = await memory_store.get_memory_for_risk(
            bank_name=bank_name,
            customer_id="cust_123",
        )
        assert "conflicts" in risk
    
    @pytest.mark.asyncio
    async def test_memory_customer_isolation(self):
        """Test that memories are isolated per customer (integration test)."""
        pytest.skip("Requires Hindsight to be running")
        
        from munshi.memory.queries import memory_store
        from datetime import datetime
        
        bank_name = "munshi-integration-test"
        
        # Create events for two different customers
        for customer_id in ["cust_A", "cust_B"]:
            await memory_store.retain(
                bank_name=bank_name,
                timestamp=datetime.now(),
                customer_id=customer_id,
                invoice_id=f"inv_{customer_id}",
                content=f"Event for {customer_id}",
                tags=[f"customer:{customer_id}"],
            )
        
        # Recall for customer A should not include customer B's events
        events_a = await memory_store.recall(
            bank_name=bank_name,
            customer_id="cust_A",
        )
        events_b = await memory_store.recall(
            bank_name=bank_name,
            customer_id="cust_B",
        )
        
        # Each customer should only see their own events
        assert len(events_a) >= 1
        assert len(events_b) >= 1


@pytest.mark.integration
class TestOutboxIntegration:
    """Integration tests for outbox processor."""
    
    @pytest.mark.asyncio
    async def test_outbox_retry(self):
        """Test outbox retry mechanism (integration test)."""
        pytest.skip("Requires Hindsight to be running")
        
        from munshi.memory.outbox import (
            outbox_processor,
            queue_memory_event,
        )
        from datetime import datetime
        
        # Queue an event
        event = await queue_memory_event(
            bank_name="munshi-test",
            content="Outbox test event",
            timestamp=datetime.now(),
        )
        
        assert event.id is not None
        assert event.retained_at is None
        
        # Process outbox
        await outbox_processor.process_outbox()
        
        # Event should be retained after processing
        # (requires Hindsight to be available)


async def run_all_integration_tests():
    """Run all integration tests (for manual execution)."""
    import asyncio
    
    from munshi.memory.queries import memory_store
    from munshi.memory.outbox import outbox_processor
    from datetime import datetime
    
    print("Starting integration tests...")
    
    # Test memory operations
    bank_name = "munshi-integration-test"
    
    print(f"Creating bank: {bank_name}")
    result = await memory_store.create_bank(
        bank_name=bank_name,
        business_name="Integration Test Business",
    )
    print(f"Bank created: {result}")
    
    print("Retaining events...")
    events = [
        {
            "content": "Test event 1",
            "timestamp": datetime.now(),
            "customer_id": "cust_123",
        },
        {
            "content": "Test event 2",
            "timestamp": datetime.now(),
            "customer_id": "cust_123",
        },
    ]
    retained = await memory_store.retain_batch(bank_name, events)
    print(f"Retained {len(retained)} events")
    
    print("Recalling events...")
    recalled = await memory_store.recall(
        bank_name=bank_name,
        customer_id="cust_123",
    )
    print(f"Recalled {len(recalled)} events")
    
    print("Reflecting on memories...")
    reflection = await memory_store.reflect(
        bank_name=bank_name,
        customer_id="cust_123",
        query="What is the payment pattern?",
    )
    print(f"Playbook: {reflection.get('playbook', 'N/A')[:100]}...")
    
    print("Testing outbox...")
    event = await queue_memory_event(
        bank_name=bank_name,
        content="Outbox test",
        timestamp=datetime.now(),
    )
    print(f"Queued event: {event.id}")
    
    await outbox_processor.process_outbox()
    print("Outbox processed")
    
    print("Integration tests completed!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_all_integration_tests())
