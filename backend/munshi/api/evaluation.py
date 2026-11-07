"""
Munshi - Evaluation results API
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from munshi.api.schemas import EvalResultsOut
from munshi.db.models import SimRun
from munshi.db.session import get_session

router = APIRouter(tags=["evaluation"])


@router.get("/eval/results", response_model=EvalResultsOut)
def get_eval_results(session: Session = Depends(get_session)) -> EvalResultsOut:
    """Return completed evaluation results aggregated across arms A, B, C."""
    runs = session.exec(select(SimRun)).all()

    arms_data: Dict[str, Any] = {"A": {}, "B": {}, "C": {}}
    seeds_seen = set()

    for r in runs:
        arm_key = r.arm.value
        seeds_seen.add(r.seed)
        if arm_key not in arms_data:
            arms_data[arm_key] = {}
        arms_data[arm_key][f"seed_{r.seed}"] = r.metrics

    return EvalResultsOut(
        git_hash="",
        arms=arms_data,
        test_months=[4, 5, 6],
        seeds=sorted(list(seeds_seen)) if seeds_seen else [1, 2, 3],
    )

