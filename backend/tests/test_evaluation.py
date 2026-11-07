"""Tests for A/B/C evaluation fairness, metrics, and persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlmodel import Session, create_engine, select
from sqlalchemy.pool import StaticPool

from eval.arms.arm_a_fixed import ArmAPolicy
from eval.arms.arm_b_structured import ArmBPolicy
from eval.arms.common import EvaluationCustomer
from eval.metrics import compute_metrics
from eval.report import generate_report
from eval.run_eval import run_all_evaluations, run_evaluation
from munshi.db.models import SimRun
from munshi.db.session import init_db


class FakeMemoryStore:
    """Isolated in-memory Hindsight stand-in for deterministic tests."""

    def __init__(
        self,
        available: bool = True,
        cross_customer_recall: bool = False,
        empty_recall: bool = False,
    ):
        self.is_available = available
        self.cross_customer_recall = cross_customer_recall
        self.empty_recall = empty_recall
        self.banks: set[str] = set()
        self.events: list[dict[str, Any]] = []
        self.operations: list[str] = []

    async def create_bank(self, bank_name: str, **kwargs: Any) -> dict[str, str] | None:
        self.operations.append("create_bank")
        if not self.is_available:
            return None
        self.banks.add(bank_name)
        return {"bank_id": bank_name}

    async def retain(self, **kwargs: Any) -> dict[str, str] | None:
        self.operations.append("retain")
        if not self.is_available:
            return None
        event_id = f"memory-{len(self.events) + 1}"
        self.events.append(
            {
                "id": event_id,
                "bank_name": kwargs["bank_name"],
                "customer_id": kwargs["customer_id"],
                "content": kwargs["content"],
            }
        )
        return {"document_id": event_id}

    async def recall(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.operations.append("recall")
        if not self.is_available or self.empty_recall:
            return []
        return [
            {"id": event["id"], "content": event["content"]}
            for event in self.events
            if event["bank_name"] == kwargs["bank_name"]
            and (
                self.cross_customer_recall
                or event["customer_id"] == kwargs["customer_id"]
            )
        ]

    async def reflect(self, **kwargs: Any) -> dict[str, Any]:
        self.operations.append("reflect")
        return {"requirements": [], "conflicts": [], "playbook": ""}


@pytest.mark.asyncio
async def test_same_seed_reproduces_arm_outcomes():
    first = await run_evaluation("A", seed=2, run_id="stable")
    second = await run_evaluation("A", seed=2, run_id="stable")
    assert first["status"] == second["status"] == "complete"
    assert first["source_fingerprint"] == second["source_fingerprint"]
    assert first["invoice_results"] == second["invoice_results"]
    assert first["metrics"] == second["metrics"]


@pytest.mark.asyncio
async def test_every_arm_receives_identical_scenario_per_seed(tmp_path: Path):
    memory = FakeMemoryStore()
    path = tmp_path / "evaluation.json"
    result = await run_all_evaluations(
        seeds=[1, 3],
        memory_store=memory,
        result_path=path,
        run_id="fair-comparison",
    )
    for seed in result["seeds"]:
        fingerprints = {
            result["arms"][arm][str(seed)]["source_fingerprint"]
            for arm in ("A", "B", "C")
        }
        assert len(fingerprints) == 1
    assert all(
        result["arms"][arm][str(seed)]["status"] == "complete"
        for arm in ("A", "B", "C")
        for seed in result["seeds"]
    )
    assert path.is_file()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["report"]["simulation_only"] is True
    assert saved["report"]["real_world_results"] is False


@pytest.mark.asyncio
async def test_arm_a_and_b_do_not_access_hindsight():
    memory = FakeMemoryStore()
    await run_evaluation("A", seed=1, memory_store=memory)
    await run_evaluation("B", seed=1, memory_store=memory)
    assert memory.operations == []


@pytest.mark.asyncio
async def test_arm_c_uses_scoped_training_memory_only():
    memory = FakeMemoryStore()
    result = await run_evaluation(
        "C",
        seed=1,
        memory_store=memory,
        run_id="scope-check",
    )
    assert result["status"] == "complete"
    assert result["hindsight_bank"] == "eval-scope-check-C-s1"
    assert "retain" in memory.operations
    assert "recall" in memory.operations
    assert "reflect" in memory.operations
    assert memory.events
    retained = [json.loads(event["content"]) for event in memory.events]
    assert all(event["observed_on"][:7] <= "2026-03" for event in retained)
    assert all(
        event["customer_key"] in {
            "reddy-traders",
            "sharma-suppliers",
            "patel-enterprises",
            "gupta-electronics",
            "sharma-traders",
            "patel-suppliers",
        }
        for event in retained
    )
    assert {event["bank_name"] for event in memory.events} == {result["hindsight_bank"]}


@pytest.mark.asyncio
async def test_arm_c_ignores_cross_customer_recall_results():
    scoped = await run_evaluation(
        "C",
        seed=2,
        memory_store=FakeMemoryStore(),
        run_id="scoped",
    )
    broad = await run_evaluation(
        "C",
        seed=2,
        memory_store=FakeMemoryStore(cross_customer_recall=True),
        run_id="broad",
    )
    assert [row["known_facts"] for row in scoped["learning_curve"]] == [
        row["known_facts"] for row in broad["learning_curve"]
    ]
    assert scoped["invoice_results"] == broad["invoice_results"]


@pytest.mark.asyncio
async def test_arm_c_unavailable_is_reported_not_replaced_by_arm_b():
    result = await run_evaluation(
        "C",
        seed=1,
        memory_store=FakeMemoryStore(available=False),
        run_id="unavailable",
    )
    assert result["status"] == "failed"
    assert "Hindsight is unavailable" in result["error"]
    assert result["invoice_results"] == []


@pytest.mark.asyncio
async def test_arm_c_reports_missing_memory_evidence():
    result = await run_evaluation(
        "C",
        seed=1,
        memory_store=FakeMemoryStore(empty_recall=True),
        run_id="empty-memory",
    )
    assert result["status"] == "complete"
    assert result["memory_evidence_count"] == 0
    assert result["memory_customers_missing_evidence"] == 6
    assert result["metrics"]["early_warning_missing_count"] == 18


def test_structured_arm_knows_documented_columns_but_fixed_arm_does_not():
    customer = EvaluationCustomer(
        key="customer",
        name="Customer",
        payment_run_days=(5, 20),
        po_required=True,
        required_docs=("SIGNED_CHALLAN",),
        credit_days=30,
    )
    fixed = ArmAPolicy()
    fixed.initialize([customer])
    structured = ArmBPolicy()
    structured.initialize([customer])
    assert fixed.known_documents == {}
    assert fixed.known_po_required == {}
    assert structured.known_documents["customer"] == {"SIGNED_CHALLAN"}
    assert structured.known_po_required["customer"] is True
    assert structured.known_payment_run_days == {}


def test_metric_calculations_preserve_missing_values_and_denominators():
    metrics = compute_metrics(
        [
            {
                "status": "complete",
                "invoice_results": [
                    {
                        "month": 4,
                        "days_late": 3,
                        "warning_lead_days": 5,
                        "actual_blocker": True,
                        "blocker_caught": True,
                    },
                    {
                        "month": 4,
                        "days_late": 7,
                        "warning_lead_days": None,
                        "actual_blocker": True,
                        "blocker_caught": False,
                    },
                    {
                        "month": 5,
                        "days_late": 2,
                        "warning_lead_days": -1,
                        "actual_blocker": False,
                        "blocker_caught": False,
                        "blocker_false_positive": True,
                    },
                ],
                "learning_curve": [
                    {"month": 1, "known_facts": 1, "total_facts": 2},
                    {"month": 2, "known_facts": 2, "total_facts": 2},
                ],
            }
        ]
    )
    assert metrics["average_days_late"] == 4
    assert metrics["avg_days_late_by_month"] == {"4": 5, "5": 2}
    assert metrics["early_warning_lead_time"] == 2
    assert metrics["early_warning_missing_count"] == 1
    assert metrics["blocker_catch_rate"] == 0.5
    assert metrics["blockers_caught"] == 1
    assert metrics["blocker_cases"] == 2
    assert metrics["blocker_false_positives"] == 1
    assert metrics["blocker_false_positive_rate"] == 1
    assert [row["coverage"] for row in metrics["learning_curve"]] == [0.5, 1.0]


def test_metrics_return_null_when_no_measurement_has_a_denominator():
    metrics = compute_metrics(
        [
            {
                "status": "complete",
                "invoice_results": [
                    {
                        "month": 4,
                        "days_late": None,
                        "warning_lead_days": None,
                        "actual_blocker": False,
                        "blocker_caught": False,
                    }
                ],
                "learning_curve": [],
            }
        ]
    )
    assert metrics["average_days_late"] is None
    assert metrics["early_warning_lead_time"] is None
    assert metrics["blocker_catch_rate"] is None
    assert metrics["missing_data_count"] == 2


def test_report_identifies_failures_and_simulation_provenance():
    report = generate_report(
        {
            "seeds": [1],
            "arms": {
                "A": {
                    "1": {
                        "arm": "A",
                        "arm_name": "Fixed rules, no memory",
                        "seed": 1,
                        "status": "complete",
                        "invoice_results": [],
                        "learning_curve": [],
                    }
                },
                "B": {},
                "C": {
                    "1": {
                        "arm": "C",
                        "seed": 1,
                        "status": "failed",
                        "error": "Hindsight unavailable",
                    }
                },
            },
        }
    )
    assert report["simulation_only"] is True
    assert report["real_world_results"] is False
    assert report["arms"]["C"]["status"] == "failed"
    assert report["arms"]["C"]["failures"][0]["error"] == "Hindsight unavailable"
    assert report["comparison"]["blocker_catch_rate"]["comparable"] is False
    assert "Insufficient comparable data" in report["conclusion"]


@pytest.mark.asyncio
async def test_run_is_persisted_as_sim_run_without_committing_caller_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    with Session(engine) as session:
        result = await run_evaluation("B", seed=1, session=session)
        assert result["status"] == "complete"
        assert len(session.exec(select(SimRun)).all()) == 1
        session.rollback()
        assert session.exec(select(SimRun)).all() == []
    engine.dispose()
