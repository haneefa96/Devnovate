"""
Munshi - Test memory queries
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


class TestMemoryStore:
    """Test MemoryStore class."""
    
    @pytest.fixture
    def memory_store(self):
        """Create MemoryStore instance."""
        from munshi.memory.queries import MemoryStore
        return MemoryStore()
    
    @pytest.mark.asyncio
    async def test_memory_store_initialization(self, memory_store):
        """Test MemoryStore initialization."""
        assert memory_store.client is None
        assert memory_store._is_initialized is False
    
    @pytest.mark.asyncio
    async def test_memory_store_is_available(self, memory_store):
        """Test is_available property."""
        # Hindsight will be unavailable in test environment
        assert memory_store.is_available is False
    
    @pytest.mark.asyncio
    async def test_memory_store_get_bank_name(self, memory_store):
        """Test bank name generation."""
        bank_name = memory_store.get_bank_name("test-business")
        assert bank_name == "munshi-test-business"
    
    @pytest.mark.asyncio
    async def test_memory_store_get_bank_name_demo(self, memory_store):
        """Test bank name generation for demo."""
        bank_name = memory_store.get_bank_name("test-business", is_demo=True)
        assert bank_name == "munshi-test-business"


class TestReflectOperations:
    """Test reflect operations."""
    
    @pytest.mark.asyncio
    async def test_get_memory_for_readiness(self):
        """Test get_memory_for_readiness function."""
        from munshi.memory.queries import get_memory_for_readiness
        
        with patch('munshi.memory.queries.memory_store') as mock_store:
            mock_store.get_memory_for_readiness = AsyncMock(
                return_value={
                    "requirements": [],
                    "conflicts": [],
                    "playbook": "",
                }
            )
            
            result = await get_memory_for_readiness(
                bank_name="munshi-test",
                customer_id="cust_123",
            )
            
            assert result is not None
            mock_store.get_memory_for_readiness.assert_called_once()


class TestParseReflectResponse:
    """Test response parsing."""
    
    def test_parse_reflect_response_valid(self):
        """Test parsing valid reflect response."""
        from munshi.memory.parsing import parse_reflect_response
        
        raw = {
            "requirements": [
                {"code": "req_1", "description": "Need GSTIN"},
            ],
            "conflicts": [
                {"code": "conf_1", "description": "GSTIN not provided"},
            ],
            "playbook": "Ask for GSTIN first",
        }
        
        result = parse_reflect_response(raw)
        assert len(result.requirements) == 1
        assert len(result.conflicts) == 1
        assert result.playbook == "Ask for GSTIN first"
    
    def test_parse_reflect_response_empty(self):
        """Test parsing empty reflect response."""
        from munshi.memory.parsing import parse_reflect_response
        
        raw = {}
        result = parse_reflect_response(raw)
        
        assert result.requirements == []
        assert result.conflicts == []
        assert result.playbook == ""
    
    def test_parse_reflect_response_string_requirements(self):
        """Test parsing requirements as strings."""
        from munshi.memory.parsing import parse_reflect_response
        
        raw = {
            "requirements": ["Need GSTIN", "Need delivery address"],
            "conflicts": [],
            "playbook": "",
        }
        
        result = parse_reflect_response(raw)
        assert len(result.requirements) == 2
        assert result.requirements[0].code == "req_0"
        assert "Need GSTIN" in result.requirements[0].description


class TestParseMemoryEvents:
    """Test memory event parsing."""
    
    def test_parse_memory_events_basic(self):
        """Test basic memory event parsing."""
        from munshi.memory.parsing import parse_memory_events
        
        events = [
            {
                "document_id": "doc_1",
                "timestamp": datetime(2024, 1, 15, 10, 30, 0),
                "content": "Sent invoice INV-001",
                "tags": ["customer:cust_1", "kind:action"],
            },
        ]
        
        result = parse_memory_events(events)
        
        assert len(result) == 1
        assert result[0]["id"] == "doc_1"
        assert "customer:cust_1" in result[0]["tags"]
    
    def test_parse_memory_events_missing_fields(self):
        """Test parsing with missing fields."""
        from munshi.memory.parsing import parse_memory_events
        
        events = [
            {
                "content": "Sent invoice",
            },
        ]
        
        result = parse_memory_events(events)
        
        assert len(result) == 1
        assert result[0]["content"] == "Sent invoice"
        assert result[0]["id"] is None


class TestParsePlaybook:
    """Test playbook parsing."""
    
    def test_parse_playbook_json(self):
        """Test parsing JSON playbook."""
        from munshi.memory.parsing import parse_playbook
        
        playbook = {
            "title": "Payment Collection",
            "steps": ["Call customer", "Send reminder"],
            "key_points": ["Be polite"],
            "warnings": ["Don't threaten legal action"],
        }
        
        result = parse_playbook(str(playbook))
        
        assert result.title == "Payment Collection"
    
    def test_parse_playbook_text(self):
        """Test parsing text playbook."""
        from munshi.memory.parsing import parse_playbook
        
        playbook = """
Steps:
- Call customer
- Send reminder
Key Points:
- Be polite
Warnings:
- Don't threaten legal action
"""
        
        result = parse_playbook(playbook)
        
        assert len(result.steps) == 2
        assert len(result.key_points) == 1
        assert len(result.warnings) == 1


class TestValidateTimestamp:
    """Test timestamp validation."""
    
    def test_validate_timestamp_datetime(self):
        """Test with datetime object."""
        from munshi.memory.parsing import validate_timestamp
        
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = validate_timestamp(dt)
        
        assert result == dt
    
    def test_validate_timestamp_iso_string(self):
        """Test with ISO string."""
        from munshi.memory.parsing import validate_timestamp
        
        result = validate_timestamp("2024-01-15T10:30:00")
        
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
    
    def test_validate_timestamp_invalid(self):
        """Test with invalid timestamp."""
        from munshi.memory.parsing import validate_timestamp
        
        result = validate_timestamp("invalid")
        
        assert result is None
