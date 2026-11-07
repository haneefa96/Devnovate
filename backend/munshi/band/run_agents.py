"""
Munshi - Band agent orchestration

This module orchestrates Band agent collaboration.
Uses the Band SDK for multi-agent coordination in shared rooms.

NOTE: Band AI provides a Python SDK (`band-sdk`) that connects agents to a shared platform.
Agents communicate via @mentions in shared rooms. Each agent connects independently
with its own agent_id and api_key.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable

from munshi.config import settings

logger = logging.getLogger(__name__)


class BandAgentManager:
    """
    Manages Band agent connections and coordination.
    
    Supports:
    - Collector agent for payment follow-ups
    - Risk agent for payment risk detection
    
    Fallback: If Band unavailable, agents work locally with Hindsight/Groq.
    """
    
    def __init__(self):
        self.room_id = settings.BAND_ROOM_ID
        self._agents: Dict[str, Any] = {}
        self._running = False
        self._callbacks: Dict[str, List[Callable]] = {}
        self._is_available = False
    
    def is_available(self) -> bool:
        """Check if Band service is available."""
        return self._is_available and bool(self.room_id)
    
    async def _initialize_agent(self, agent_type: str) -> Optional[Any]:
        """Initialize a Band agent."""
        if not self.room_id:
            logger.warning(f"BAND_ROOM_ID not set, cannot initialize {agent_type}")
            return None
        
        agent_id = (
            settings.BAND_COLLECTOR_AGENT_ID
            if agent_type == "collector"
            else settings.BAND_RISK_AGENT_ID
        )
        api_key = (
            settings.BAND_COLLECTOR_API_KEY
            if agent_type == "collector"
            else settings.BAND_RISK_API_KEY
        )
        
        if not agent_id:
            logger.warning(f"BAND_{agent_type.upper()}_AGENT_ID not set")
            return None
        
        if not api_key:
            logger.warning(f"BAND_{agent_type.upper()}_API_KEY not set")
            return None
        
        try:
            import band
            from band.adapters import PydanticAIAdapter
            from pydantic import BaseModel
            
            # Create adapter with custom instructions
            if agent_type == "collector":
                custom_section = """
You are Munshi's Collector Agent. Help the owner get paid on time by:
1. Checking customer payment history and patterns
2. Planning follow-up reminders
3. Generating reminder drafts for owner approval
4. Explaining why each follow-up is appropriate

Always ask for owner approval before sending messages.
Use the evidence from SQLite and Hindsight memories.
Never invent payment history - rely on ledger data.
"""
            else:  # risk
                custom_section = """
You are Munshi's Risk Agent. Detect payment risks by:
1. Analyzing missed payment promises
2. Identifying changes in customer behavior
3. Recognizing signs of financial distress
4. Recommending risk alerts

Always base your analysis on actual evidence from memories.
Flag changes in payment patterns, contact changes, or unusual behavior.
"""
            
            adapter = PydanticAIAdapter(
                model="openai/gpt-oss-120b",
                custom_section=custom_section.strip(),
            )
            
            agent = band.Agent.create(
                adapter=adapter,
                agent_id=agent_id,
                api_key=api_key,
            )
            
            self._agents[agent_type] = agent
            logger.info(f"Initialized Band {agent_type} agent")
            return agent
            
        except ImportError:
            logger.warning(
                "band-sdk not installed. Install with: pip install band-sdk"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Band {agent_type} agent: {e}")
            return None
    
    async def start_collector_agent(self) -> Optional[Any]:
        """Start the Collector agent."""
        agent = await self._initialize_agent("collector")
        if agent:
            self._is_available = True
            await agent.run()
        return agent
    
    async def start_risk_agent(self) -> Optional[Any]:
        """Start the Risk agent."""
        agent = await self._initialize_agent("risk")
        if agent:
            self._is_available = True
            await agent.run()
        return agent
    
    async def start_all_agents(self) -> Dict[str, Optional[Any]]:
        """Start all Band agents."""
        results = {
            "collector": await self.start_collector_agent(),
            "risk": await self.start_risk_agent(),
        }
        return results
    
    async def stop_agent(self, agent_type: str) -> bool:
        """Stop a specific agent."""
        agent = self._agents.get(agent_type)
        if agent:
            try:
                await agent.stop()
                del self._agents[agent_type]
                logger.info(f"Stopped {agent_type} agent")
                return True
            except Exception as e:
                logger.error(f"Error stopping {agent_type} agent: {e}")
                return False
        return False
    
    async def stop_all_agents(self) -> None:
        """Stop all agents."""
        for agent_type in list(self._agents.keys()):
            await self.stop_agent(agent_type)
        self._is_available = False
    
    def register_callback(
        self,
        agent_type: str,
        callback: Callable[[Dict[str, Any]], None],
    ) -> None:
        """
        Register a callback for agent events.
        
        Args:
            agent_type: "collector" or "risk"
            callback: Function to call with event data
        """
        if agent_type not in self._callbacks:
            self._callbacks[agent_type] = []
        self._callbacks[agent_type].append(callback)
    
    async def notify_callbacks(
        self,
        agent_type: str,
        event_data: Dict[str, Any],
    ) -> None:
        """Notify all callbacks for an agent."""
        for callback in self._callbacks.get(agent_type, []):
            try:
                await callback(event_data)
            except Exception as e:
                logger.error(f"Error in callback for {agent_type}: {e}")
    
    def set_room_id(self, room_id: str) -> None:
        """Set the Band room ID."""
        self.room_id = room_id
        logger.info(f"Band room ID set: {room_id}")


# Global agent manager instance
band_agent_manager = BandAgentManager()


async def start_band_agents() -> Dict[str, Optional[Any]]:
    """Start all Band agents."""
    return await band_agent_manager.start_all_agents()


async def stop_band_agents() -> None:
    """Stop all Band agents."""
    await band_agent_manager.stop_all_agents()


async def is_band_available() -> bool:
    """Check if Band service is available."""
    return band_agent_manager.is_available()


class BandMessageRouter:
    """
    Routes messages to appropriate agents.
    
    Handles:
    - Collector handoffs to Risk
    - Risk handoffs to Collector
    - Owner approval messages
    """
    
    def __init__(self):
        self._agents: Dict[str, Any] = {}
        self._message_handlers: Dict[str, Callable] = {}
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Setup message handlers."""
        self._message_handlers = {
            "draft": self._handle_draft,
            "risk": self._handle_risk,
            "handoff": self._handle_handoff,
            "collector_handoff": self._handle_collector_handoff,
            "command": self._handle_command,
        }
    
    async def route_message(self, message_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route a message to the appropriate handler.
        
        Args:
            message_type: Type of message
            data: Message data
        
        Returns:
            Handler result
        """
        handler = self._message_handlers.get(message_type, self._handle_unknown)
        return await handler(data)
    
    async def _handle_draft(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle draft message."""
        # Collector generates draft, waits for owner approval
        return {
            "status": "pending_approval",
            "draft_id": data.get("draft_id"),
        }
    
    async def _handle_risk(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle risk alert."""
        # Risk agent detects risk, posts alert
        return {
            "status": "alerted",
            "customer": data.get("customer"),
        }
    
    async def _handle_handoff(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Collector → Risk handoff."""
        # Risk agent assesses the situation
        return {
            "status": "assessing",
            "invoice_id": data.get("invoice_id"),
            "description": data.get("description"),
        }
    
    async def _handle_collector_handoff(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Risk → Collector handoff."""
        # Collector follows up on the issue
        return {
            "status": "following_up",
            "invoice_id": data.get("invoice_id"),
            "description": data.get("description"),
        }
    
    async def _handle_command(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle owner approval command."""
        action = data.get("action")
        draft_id = data.get("draft_id")
        
        if action == "approve":
            return {"status": "approved", "draft_id": draft_id}
        elif action == "reject":
            return {"status": "rejected", "draft_id": draft_id}
        elif action == "edit":
            return {"status": "edit_requested", "draft_id": draft_id}
        
        return {"status": "unknown_command"}
    
    async def _handle_unknown(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle unknown message type."""
        logger.warning(f"Unknown message type: {data}")
        return {"status": "unhandled"}


# Global message router instance
band_message_router = BandMessageRouter()
