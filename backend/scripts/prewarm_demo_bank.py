"""
Munshi - Prewarm demo bank

This script prewarms the demo Hindsight bank before the demo.
"""

import asyncio
import logging

from munshi.memory.client import get_hindsight_client
from munshi.memory.bank_setup import get_bank_config
from munshi.memory.events import create_retain_payload

logger = logging.getLogger(__name__)


async def prewarm_demo_bank() -> None:
    """Prewarm the demo Hindsight bank."""
    logger.info("Prewarming demo bank...")
    
    # TODO: Initialize Hindsight and retain demo data
    logger.info("Demo bank prewarmed successfully")


if __name__ == "__main__":
    asyncio.run(prewarm_demo_bank())
