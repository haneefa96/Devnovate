"""Bounded daily Collector and Risk workflow."""

import asyncio
import logging

from munshi.agents.collector import CollectorAgent
from munshi.agents.risk import RiskAgent
from munshi.config import clock
from munshi.db.session import session_scope

logger = logging.getLogger(__name__)


class DailyLoop:
    """Run one bounded, idempotent ledger review per worker interval."""

    def __init__(self) -> None:
        self.collector = CollectorAgent()
        self.risk = RiskAgent()
        self.collector.set_agents(self.collector, self.risk)
        self._running = False
        self._interval_hours = 24

    async def run(self) -> None:
        if self._running:
            logger.info("Daily workflow is already running")
            return
        self._running = True
        logger.info("Daily workflow started")
        try:
            while self._running:
                await self._check_day()
                await asyncio.sleep(self._interval_hours * 3600)
        finally:
            self._running = False
            logger.info("Daily workflow stopped")

    async def stop(self) -> None:
        self._running = False

    async def _check_day(self) -> dict[str, int]:
        run_at = clock.now()
        drafts_created = 0
        assessments_completed = 0
        alerts_raised = 0
        try:
            with session_scope() as session:
                drafts = await self.collector.on_daily_check(session, run_at)
            drafts_created = len(drafts)
        except Exception as error:
            logger.error("Daily Collector pass failed (%s)", type(error).__name__)
        try:
            with session_scope() as session:
                assessments = await self.risk.on_daily_check(session, run_at)
            assessments_completed = len(assessments)
            alerts_raised = sum(bool(result.get("alert_id")) for result in assessments)
        except Exception as error:
            logger.error("Daily Risk pass failed (%s)", type(error).__name__)
        logger.info(
            "Daily workflow completed: drafts=%s risk_assessments=%s alerts=%s",
            drafts_created,
            assessments_completed,
            alerts_raised,
        )
        return {
            "drafts_created": drafts_created,
            "risk_assessments": assessments_completed,
            "alerts_raised": alerts_raised,
        }


daily_loop = DailyLoop()
