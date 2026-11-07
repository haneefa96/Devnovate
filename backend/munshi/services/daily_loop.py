"""
Munshi - Daily loop service

This module runs the daily check loop.
"""

import asyncio
import logging
from datetime import datetime

from sqlmodel import Session

from munshi.config import settings, clock
from munshi.agents.collector import CollectorAgent
from munshi.agents.risk import RiskAgent

logger = logging.getLogger(__name__)


class DailyLoop:
    """
    Daily loop service.
    
    Runs at regular intervals to check:
    - Overdue invoices
    - Customer status
    - Risk levels
    """
    
    def __init__(self):
        self.collector = None
        self.risk = None
        self._running = False
        self._interval_hours = 24  # Check every 24 hours
    
    async def run(self) -> None:
        """Run daily loop."""
        self._running = True
        logger.info("Daily loop started")
        
        while self._running:
            await self._check_day()
            await asyncio.sleep(self._interval_hours * 3600)  # Convert hours to seconds
    
    async def stop(self) -> None:
        """Stop daily loop."""
        self._running = False
        logger.info("Daily loop stopped")
    
    async def _check_day(self) -> None:
        """Run daily checks."""
        current_date = clock.now()
        logger.info(f"Running daily check for {current_date.date()}")
        
        # TODO: Implement daily check logic
        # - Get overdue invoices
        # - Run collector and risk agents
        # - Process results


# Global instance
daily_loop = DailyLoop()
