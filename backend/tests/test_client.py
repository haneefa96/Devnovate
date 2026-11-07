"""
Munshi - Test Hindsight client
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestHindsightClient:
    """Test HindsightClient class."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        from munshi.memory import client as client_module
        client_module.HindsightClient._instance = None
        yield
        client_module.HindsightClient._instance = None
    
    def test_client_singleton(self):
        """Test that client is a singleton."""
        from munshi.memory.client import get_hindsight_client, HindsightClient
        
        client1 = get_hindsight_client()
        client2 = get_hindsight_client()
        
        assert client1 is client2
        assert isinstance(client1, HindsightClient)
    
    def test_client_not_available_when_not_configured(self):
        """Test client is not available when not configured."""
        from munshi.memory.client import get_hindsight_client
        
        client = get_hindsight_client()
        
        # Hindsight should not be available without configuration
        assert client.is_available is False
    
    def test_client_raises_when_not_initialized(self):
        """Test client raises when not initialized."""
        from munshi.memory.client import HindsightClient
        
        client = HindsightClient()
        
        # Should raise RuntimeError when not initialized
        with pytest.raises(RuntimeError):
            _ = client.client
    
    @pytest.mark.asyncio
    async def test_client_aclose(self):
        """Test async client close."""
        from munshi.memory.client import HindsightClient
        
        client = HindsightClient()
        
        # Should not raise even if client not initialized
        await client.aclose()
    
    def test_client_close(self):
        """Test sync client close."""
        from munshi.memory.client import HindsightClient
        
        client = HindsightClient()
        
        # Should not raise even if client not initialized
        client.close()


class TestIsHindsightAvailable:
    """Test is_hindsight_available function."""
    
    def test_is_not_available_without_config(self):
        """Test that Hindsight is not available without config."""
        from munshi.memory.client import is_hindsight_available
        
        result = is_hindsight_available()
        
        assert result is False


class TestCreateBank:
    """Test create_bank function."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        from munshi.memory import client as client_module
        client_module.HindsightClient._instance = None
        yield
        client_module.HindsightClient._instance = None
    
    @pytest.mark.asyncio
    async def test_create_bank_hindsight_unavailable(self):
        """Test create_bank when Hindsight is unavailable."""
        from munshi.memory.client import create_bank
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = False
            mock_get_client.return_value = mock_client
            
            result = await create_bank(bank_id="test-bank")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_create_bank_success(self):
        """Test create_bank success."""
        from munshi.memory.client import create_bank
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_hindsight = AsyncMock()
            mock_hindsight.create_bank = AsyncMock(
                return_value={"bank_id": "test-bank", "name": "Test Bank"}
            )
            mock_client.client = mock_hindsight
            mock_get_client.return_value = mock_client
            
            result = await create_bank(
                bank_id="test-bank",
                name="Test Bank",
            )
            
            assert result is not None
            assert result["bank_id"] == "test-bank"
    
    @pytest.mark.asyncio
    async def test_create_bank_error(self):
        """Test create_bank error handling."""
        from munshi.memory.client import create_bank
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_hindsight = AsyncMock()
            mock_hindsight.create_bank = AsyncMock(
                side_effect=Exception("Connection error")
            )
            mock_client.client = mock_hindsight
            mock_get_client.return_value = mock_client
            
            result = await create_bank(bank_id="test-bank")
            
            assert result is None


class TestRetainEvent:
    """Test retain_event function."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        from munshi.memory import client as client_module
        client_module.HindsightClient._instance = None
        yield
        client_module.HindsightClient._instance = None
    
    @pytest.mark.asyncio
    async def test_retain_event_hindsight_unavailable(self):
        """Test retain_event when Hindsight is unavailable."""
        from munshi.memory.client import retain_event
        from datetime import datetime
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = False
            mock_get_client.return_value = mock_client
            
            result = await retain_event(
                bank_id="test-bank",
                content="Test content",
                timestamp=datetime.now(),
            )
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_retain_event_success(self):
        """Test retain_event success."""
        from munshi.memory.client import retain_event
        from datetime import datetime
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_hindsight = AsyncMock()
            mock_hindsight.retain = AsyncMock(
                return_value={"document_id": "doc_123"}
            )
            mock_client.client = mock_hindsight
            mock_get_client.return_value = mock_client
            
            result = await retain_event(
                bank_id="test-bank",
                content="Test content",
                timestamp=datetime.now(),
            )
            
            assert result is not None
            assert result["document_id"] == "doc_123"


class TestRecallMemories:
    """Test recall_memories function."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        from munshi.memory import client as client_module
        client_module.HindsightClient._instance = None
        yield
        client_module.HindsightClient._instance = None
    
    @pytest.mark.asyncio
    async def test_recall_memories_hindsight_unavailable(self):
        """Test recall_memories when Hindsight is unavailable."""
        from munshi.memory.client import recall_memories
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = False
            mock_get_client.return_value = mock_client
            
            result = await recall_memories(bank_id="test-bank", query="test")
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_recall_memories_success(self):
        """Test recall_memories success."""
        from munshi.memory.client import recall_memories
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_hindsight = AsyncMock()
            mock_hindsight.recall = AsyncMock(
                return_value=[
                    {"document_id": "doc_1", "content": "Event 1"},
                    {"document_id": "doc_2", "content": "Event 2"},
                ]
            )
            mock_client.client = mock_hindsight
            mock_get_client.return_value = mock_client
            
            result = await recall_memories(bank_id="test-bank", query="test")
            
            assert len(result) == 2
            assert result[0]["document_id"] == "doc_1"


class TestReflectOnMemories:
    """Test reflect_on_memories function."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        from munshi.memory import client as client_module
        client_module.HindsightClient._instance = None
        yield
        client_module.HindsightClient._instance = None
    
    @pytest.mark.asyncio
    async def test_reflect_memories_hindsight_unavailable(self):
        """Test reflect_memories when Hindsight is unavailable."""
        from munshi.memory.client import reflect_on_memories
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = False
            mock_get_client.return_value = mock_client
            
            result = await reflect_on_memories(bank_id="test-bank", query="test")
            
            assert result == {"requirements": [], "conflicts": [], "playbook": ""}
    
    @pytest.mark.asyncio
    async def test_reflect_memories_success(self):
        """Test reflect_memories success."""
        from munshi.memory.client import reflect_on_memories
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_hindsight = AsyncMock()
            mock_hindsight.reflect = AsyncMock(
                return_value={
                    "requirements": [{"code": "req_1", "description": "Test req"}],
                    "conflicts": [],
                    "playbook": "Playbook text",
                }
            )
            mock_client.client = mock_hindsight
            mock_get_client.return_value = mock_client
            
            result = await reflect_on_memories(bank_id="test-bank", query="test")
            
            assert "requirements" in result
            assert len(result["requirements"]) == 1
            assert result["playbook"] == "Playbook text"


class TestListBankMemories:
    """Test list_bank_memories function."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        from munshi.memory import client as client_module
        client_module.HindsightClient._instance = None
        yield
        client_module.HindsightClient._instance = None
    
    @pytest.mark.asyncio
    async def test_list_memories_hindsight_unavailable(self):
        """Test list_memories when Hindsight is unavailable."""
        from munshi.memory.client import list_bank_memories
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = False
            mock_get_client.return_value = mock_client
            
            result = await list_bank_memories(bank_id="test-bank")
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_list_memories_success(self):
        """Test list_memories success."""
        from munshi.memory.client import list_bank_memories
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_hindsight = AsyncMock()
            mock_hindsight.list_memories = AsyncMock(
                return_value=[
                    {"document_id": "doc_1", "content": "Event 1"},
                ]
            )
            mock_client.client = mock_hindsight
            mock_get_client.return_value = mock_client
            
            result = await list_bank_memories(bank_id="test-bank")
            
            assert len(result) == 1
            assert result[0]["document_id"] == "doc_1"


class TestMentalModels:
    """Test mental model operations."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        from munshi.memory import client as client_module
        client_module.HindsightClient._instance = None
        yield
        client_module.HindsightClient._instance = None
    
    @pytest.mark.asyncio
    async def test_create_mental_model_unavailable(self):
        """Test create_mental_model when Hindsight is unavailable."""
        from munshi.memory.client import create_mental_model
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = False
            mock_get_client.return_value = mock_client
            
            result = await create_mental_model(
                bank_id="test-bank",
                name="Test Model",
                source_query="test",
            )
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_list_mental_models_success(self):
        """Test list_mental_models success."""
        from munshi.memory.client import list_mental_models
        
        with patch('munshi.memory.client.get_hindsight_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_hindsight = AsyncMock()
            mock_hindsight.list_mental_models = AsyncMock(
                return_value=[
                    {"id": "model_1", "name": "Test Model"},
                ]
            )
            mock_client.client = mock_hindsight
            mock_get_client.return_value = mock_client
            
            result = await list_mental_models(bank_id="test-bank")
            
            assert len(result) == 1
            assert result[0]["name"] == "Test Model"
