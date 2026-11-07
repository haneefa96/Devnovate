"""
Munshi - Simulation / demo control API

Allows the demo script and tests to advance the simulated clock,
reset the database to a clean state, and inject synthetic events.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from munshi.api.schemas import SimInjectIn, SimInjectOut, SimResetIn, SimResetOut, SimTickOut
from munshi.config import clock, settings
from munshi.db.seed import seed_demo_data
from munshi.db.session import get_session, reset_db

router = APIRouter(tags=["simulation"])


@router.post("/sim/reset", response_model=SimResetOut)
def reset_simulation(
    body: Optional[SimResetIn] = None,
    session: Session = Depends(get_session),
) -> SimResetOut:
    """
    Drop and recreate the database, seed demo data, reset the clock.
    Only available when SIM_MODE=true.
    """
    if settings.IS_PRODUCTION or not settings.SIM_MODE:
        raise HTTPException(status_code=403, detail="Simulation reset not allowed in production (SIM_DISABLED)")

    reset_db(session.get_bind())
    clock.reset()
    seed_demo_data(session)
    return SimResetOut(clock=str(clock.now().date()))


@router.post("/sim/tick", response_model=SimTickOut)
def tick_simulation(days: int = 1) -> SimTickOut:
    """Advance the simulated clock by N days."""
    if settings.IS_PRODUCTION or not settings.SIM_MODE:
        raise HTTPException(status_code=403, detail="Simulation tick not allowed in production (SIM_DISABLED)")
    if days < 1 or days > 365:
        raise HTTPException(status_code=422, detail="days must be between 1 and 365")

    clock.tick(days)
    return SimTickOut(
        clock=str(clock.now().date()),
        drafts_created=0,
        alerts_raised=0,
    )


@router.post("/sim/inject", response_model=SimInjectOut)
def inject_event(body: SimInjectIn) -> SimInjectOut:
    """
    Inject a synthetic event for demo purposes.
    Supported types: CONTACT_CHANGE, REQUIREMENT_CHANGE, DISTRESS_START.
    """
    if settings.IS_PRODUCTION or not settings.SIM_MODE:
        raise HTTPException(status_code=403, detail="Event injection not allowed in production (SIM_DISABLED)")

    if not body.type:
        raise HTTPException(
            status_code=422,
            detail="type must be CONTACT_CHANGE, REQUIREMENT_CHANGE, or DISTRESS_START",
        )
    return SimInjectOut(ok=True)
