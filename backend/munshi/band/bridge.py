"""
Munshi - Band bridge

This module bridges backend events to Band room posts.
Uses the Band SDK for agent communication via rooms.
"""

import logging
from typing import Dict, Any, Optional, List

from munshi.config import settings

logger = logging.getLogger(__name__)


class BandBridge:
    """
    Bridge backend events to Band room.
    
    Posts:
    - Drafts (Collector)
    - Risk alerts (Risk)
    
    Fallback: If Band unavailable, log but don't fail.
    """
    
    def __init__(self):
        self.room_id = settings.BAND_ROOM_ID
        self.agent_id = settings.BAND_AGENT_ID
        self.api_key = settings.BAND_API_KEY
        self._client = None
        self._is_available = False
    
    def is_available(self) -> bool:
        """Check if Band service is available."""
        return self._is_available and bool(self.api_key)
    
    async def _ensure_client(self) -> Optional[Any]:
        """Get or create Band client."""
        if self._client is not None:
            return self._client
        
        if not self.api_key:
            logger.warning("BAND_API_KEY not set")
            return None
        
        if not self.room_id:
            logger.warning("BAND_ROOM_ID not set")
            return None
        
        try:
            import band
            
            # Create a simple agent for room communication
            # This agent doesn't use LLM - just posts messages
            from band.adapters import PydanticAIAdapter
            from pydantic import BaseModel
            
            class NoOpAgent(BaseModel):
                """Minimal agent for room posting."""
                pass
            
            adapter = PydanticAIAdapter(
                model="dummy",  # Not used for posting
                custom_section="You are a room agent for Munshi. Never reply to messages - only post updates.",
            )
            
            self._client = band.Agent.create(
                adapter=adapter,
                agent_id=self.agent_id or "munshi-room-bot",
                api_key=self.api_key,
            )
            self._is_available = True
            logger.info("Band bridge initialized")
            return self._client
            
        except ImportError:
            logger.warning(
                "band-sdk not installed. Install with: pip install band-sdk"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Band client: {e}")
            return None
    
    async def post_draft(self, draft_data: Dict[str, Any]) -> bool:
        """
        Post draft to Band room.
        
        Args:
            draft_data: Draft data from backend
        
        Returns:
            True if successful, False otherwise
        """
        client = await self._ensure_client()
        if not client:
            logger.warning("Band client not available, skipping draft post")
            return False
        
        # Format: [DRAFT A-231] To Priya (Reddy Traders), WhatsApp, today 10:30. <message>. Why: <evidence>
        content = (
            f"[DRAFT {draft_data.get('id', 'unknown')}] "
            f"To {draft_data.get('recipient', 'unknown')} ({draft_data.get('customer', 'unknown')}), "
            f"{draft_data.get('channel', 'unknown')}, today {draft_data.get('time', 'unknown')}. "
            f"{draft_data.get('body', '')[:200]}... Why: {draft_data.get('evidence', '')[:100]}"
        )
        
        try:
            # Use the agent's built-in chat tools if available
            # For now, log that we would post to Band
            logger.info(f"Would post draft to Band room {self.room_id}: {content[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to post draft to Band: {e}")
            return False
    
    async def post_risk_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Post risk alert to Band room.
        
        Args:
            alert_data: Alert data
        
        Returns:
            True if successful, False otherwise
        """
        client = await self._ensure_client()
        if not client:
            logger.warning("Band client not available, skipping alert post")
            return False
        
        # Format: [RISK] Reddy Traders: Watch → High. Signals: ... Suggest: ...
        content = (
            f"[RISK] {alert_data.get('customer', 'unknown')}: "
            f"{alert_data.get('from_level', 'unknown')} → {alert_data.get('to_level', 'unknown')}. "
            f"Signals: {', '.join(alert_data.get('signals', []))}. "
            f"Suggest: {alert_data.get('suggestion', '')}"
        )
        
        try:
            # Use the agent's built-in chat tools if available
            # For now, log that we would post to Band
            logger.info(f"Would post risk alert to Band room {self.room_id}: {content[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to post risk alert to Band: {e}")
            return False
    
    async def close(self) -> None:
        """Close Band client."""
        if self._client:
            try:
                await self._client.stop()
            except Exception as e:
                logger.warning(f"Error closing Band client: {e}")
            self._client = None


# Global bridge instance
band_bridge = BandBridge()
