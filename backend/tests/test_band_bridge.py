"""
Munshi - Test Band bridge
"""

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def isolate_band_credentials(monkeypatch):
    """Keep Band configuration test-only and avoid developer credentials."""
    from munshi.config import settings

    for name in (
        "BAND_API_KEY",
        "BAND_ROOM_ID",
        "BAND_AGENT_ID",
        "BAND_COLLECTOR_AGENT_ID",
        "BAND_COLLECTOR_API_KEY",
        "BAND_RISK_AGENT_ID",
        "BAND_RISK_API_KEY",
    ):
        monkeypatch.setattr(settings, name, None)


class TestBandBridge:
    """Test BandBridge class."""
    
    @pytest.fixture
    def bridge(self):
        """Create BandBridge instance."""
        from munshi.band.bridge import BandBridge
        return BandBridge()
    
    def test_bridge_initialization(self, bridge):
        """Test BandBridge initialization."""
        assert bridge.room_id is None
        assert bridge.agent_id is None
        assert bridge.api_key is None
        assert bridge._client is None
        assert bridge._is_available is False
    
    def test_bridge_with_env_vars(self):
        """Test BandBridge reads central backend settings."""
        from munshi.config import settings
        from munshi.band.bridge import BandBridge

        with patch.multiple(
            settings,
            BAND_ROOM_ID="room_123",
            BAND_AGENT_ID="agent_123",
            BAND_API_KEY="key_123",
        ):
            bridge = BandBridge()
            
            assert bridge.room_id == "room_123"
            assert bridge.agent_id == "agent_123"
            assert bridge.api_key == "key_123"
    
    def test_post_draft_without_client(self, bridge):
        """Test post_draft when client is not available."""
        import asyncio
        
        result = asyncio.run(bridge.post_draft({"id": "A-231"}))
        
        assert result is False
    
    def test_post_risk_without_client(self, bridge):
        """Test post_risk_alert when client is not available."""
        import asyncio
        
        result = asyncio.run(bridge.post_risk_alert({"customer": "Reddy Traders"}))
        
        assert result is False
    
    def test_close(self, bridge):
        """Test bridge close."""
        import asyncio
        
        # Should not raise even with no client
        asyncio.run(bridge.close())


class TestIsBandAvailable:
    """Test is_band_available function."""
    
    def test_not_available_by_default(self):
        """Test that Band is not available by default."""
        from munshi.band.run_agents import is_band_available
        import asyncio
        
        result = asyncio.run(is_band_available())
        
        # Not available without BAND_ROOM_ID
        assert result is False


class TestBandMessageRouter:
    """Test BandMessageRouter class."""
    
    @pytest.fixture
    def router(self):
        """Create BandMessageRouter instance."""
        from munshi.band.run_agents import BandMessageRouter
        return BandMessageRouter()
    
    def test_route_draft(self, router):
        """Test routing draft message."""
        import asyncio
        
        result = asyncio.run(router.route_message("draft", {"draft_id": "A-231"}))
        
        assert result["status"] == "pending_approval"
        assert result["draft_id"] == "A-231"
    
    def test_route_risk(self, router):
        """Test routing risk message."""
        import asyncio
        
        result = asyncio.run(router.route_message("risk", {"customer": "Reddy Traders"}))
        
        assert result["status"] == "alerted"
        assert result["customer"] == "Reddy Traders"
    
    def test_route_handoff(self, router):
        """Test routing handoff message."""
        import asyncio
        
        result = asyncio.run(router.route_message("handoff", {"invoice_id": "INV-1060"}))
        
        assert result["status"] == "assessing"
        assert result["invoice_id"] == "INV-1060"
    
    def test_route_collector_handoff(self, router):
        """Test routing collector handoff message."""
        import asyncio
        
        result = asyncio.run(router.route_message("collector_handoff", {"invoice_id": "INV-1060"}))
        
        assert result["status"] == "following_up"
        assert result["invoice_id"] == "INV-1060"
    
    def test_route_command_approve(self, router):
        """Test routing approve command."""
        import asyncio
        
        result = asyncio.run(router.route_message("command", {"action": "approve", "draft_id": "A-231"}))
        
        assert result["status"] == "approved"
        assert result["draft_id"] == "A-231"
    
    def test_route_command_reject(self, router):
        """Test routing reject command."""
        import asyncio
        
        result = asyncio.run(router.route_message("command", {"action": "reject", "draft_id": "A-231"}))
        
        assert result["status"] == "rejected"
        assert result["draft_id"] == "A-231"
    
    def test_route_unknown_command(self, router):
        """Test routing unknown command."""
        import asyncio
        
        result = asyncio.run(router.route_message("command", {"action": "unknown", "draft_id": "A-231"}))
        
        assert result["status"] == "unknown_command"


class TestBandAgentManager:
    """Test BandAgentManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create BandAgentManager instance."""
        from munshi.band.run_agents import BandAgentManager
        return BandAgentManager()
    
    def test_manager_initialization(self, manager):
        """Test BandAgentManager initialization."""
        assert manager.room_id is None
        assert manager._agents == {}
        assert manager._running is False
        assert manager._callbacks == {}
        assert manager._is_available is False
    
    def test_manager_with_env_vars(self):
        """Test BandAgentManager reads central backend settings."""
        from munshi.config import settings
        from munshi.band.run_agents import BandAgentManager

        with patch.multiple(
            settings,
            BAND_ROOM_ID="room_123",
            BAND_COLLECTOR_AGENT_ID="collector_123",
            BAND_COLLECTOR_API_KEY="collector-key",
            BAND_RISK_AGENT_ID="risk_123",
            BAND_RISK_API_KEY="risk-key",
        ):
            manager = BandAgentManager()
            
            assert manager.room_id == "room_123"
    
    def test_start_collector_without_credentials(self, manager):
        """Test starting collector agent without credentials."""
        import asyncio
        
        result = asyncio.run(manager.start_collector_agent())
        
        # Should return None without error
        assert result is None

    @pytest.mark.asyncio
    async def test_agents_use_agent_specific_api_keys(self, monkeypatch):
        from munshi.config import settings
        from munshi.band.run_agents import BandAgentManager

        with patch.multiple(
            settings,
            BAND_ROOM_ID="room-test",
            BAND_COLLECTOR_AGENT_ID="collector-test",
            BAND_COLLECTOR_API_KEY="collector-key",
            BAND_RISK_AGENT_ID="risk-test",
            BAND_RISK_API_KEY="risk-key",
        ):
            fake_band = ModuleType("band")
            fake_band.Agent = MagicMock()
            fake_adapters = ModuleType("band.adapters")
            fake_adapters.PydanticAIAdapter = MagicMock()
            monkeypatch.setitem(sys.modules, "band", fake_band)
            monkeypatch.setitem(sys.modules, "band.adapters", fake_adapters)

            manager = BandAgentManager()
            await manager._initialize_agent("collector")
            await manager._initialize_agent("risk")

        calls = fake_band.Agent.create.call_args_list
        assert calls[0].kwargs["agent_id"] == "collector-test"
        assert calls[0].kwargs["api_key"] == "collector-key"
        assert calls[1].kwargs["agent_id"] == "risk-test"
        assert calls[1].kwargs["api_key"] == "risk-key"
    
    def test_stop_agent(self, manager):
        """Test stopping agent."""
        import asyncio
        
        result = asyncio.run(manager.stop_agent("collector"))
        
        # Should return False for non-existent agent
        assert result is False
    
    def test_stop_all_agents(self, manager):
        """Test stopping all agents."""
        import asyncio
        
        # Should not raise even with no agents
        asyncio.run(manager.stop_all_agents())
    
    def test_register_callback(self, manager):
        """Test registering callback."""
        def mock_callback(data):
            pass
        
        manager.register_callback("collector", mock_callback)
        
        assert "collector" in manager._callbacks
        assert mock_callback in manager._callbacks["collector"]
    
    def test_set_room_id(self, manager):
        """Test setting room ID."""
        manager.set_room_id("new_room_123")
        
        assert manager.room_id == "new_room_123"
