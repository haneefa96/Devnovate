"""Reproducible A/B/C evaluation orchestration."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlmodel import Session

from munshi.config import clock
from munshi.db.models import SimArm, SimRun
from sim.world import SimulationWorld

from .arms.arm_a_fixed import ArmAPolicy
from .arms.arm_b_structured import ArmBPolicy
from .arms.arm_c_hindsight import ArmCPolicy
from .arms.common import EvaluationArm, EvaluationCustomer, EvaluationInvoice
from .metrics import compute_metrics
from .report import generate_report

logger = logging.getLogger(__name__)
_ARMS = {
    "A": ArmAPolicy,
    "B": ArmBPolicy,
    "C": ArmCPolicy,
}
_TEST_MONTHS = (4, 5, 6)
_LEARNING_MONTHS = (1, 2, 3)
_INVOICE_PDF_PATTERN_MODULUS = 5


async def run_evaluation(
    arm: str,
    seed: int,
    months: int = 6,
    *,
    scenario: str | Path = "eval",
    customer_count: int = 6,
    memory_store: Any | None = None,
    session: Session | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run one arm/seed against the fixed six-month synthetic scenario.

    Database persistence is optional and uses the caller's transaction. Arm C
    uses a unique Hindsight bank; an unavailable service produces a failed run,
    not a substitution with structured database knowledge.
    """
    arm = arm.upper()
    if arm not in _ARMS:
        raise ValueError(f"unknown evaluation arm {arm!r}; expected A, B, or C")
    if months != 6:
        raise ValueError("the documented evaluation is fixed at six months")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if isinstance(customer_count, bool) or not isinstance(customer_count, int):
        raise ValueError("customer_count must be an integer")
    if not 1 <= customer_count <= 12:
        raise ValueError("customer_count must be between 1 and 12")

    run_id = run_id or uuid.uuid4().hex[:12]
    started_at = clock.now()
    run_result: dict[str, Any] = {
        "arm": arm,
        "run_id": run_id,
        "arm_name": {
            "A": "Fixed rules, no memory",
            "B": "Structured database memory",
            "C": "Hindsight customer memory",
        }[arm],
        "seed": seed,
        "status": "failed",
        "scenario": Path(scenario).stem,
        "source_fingerprint": None,
        "learning_months": list(_LEARNING_MONTHS),
        "testing_months": list(_TEST_MONTHS),
        "customer_count": customer_count,
        "invoice_results": [],
        "learning_curve": [],
        "metrics": {},
        "started_at": started_at.isoformat(),
        "finished_at": None,
    }

    try:
        world = SimulationWorld.from_scenario(
            scenario,
            seed=seed,
            customer_count=customer_count,
        )
        world.run_scenario()
        customers = _evaluation_customers(world)
        invoices = _evaluation_invoices(world, customers)
        run_result["scenario"] = world.scenario_name
        run_result["customer_count"] = len(customers)
        run_result["source_fingerprint"] = _source_fingerprint(
            seed,
            world.scenario_name or str(scenario),
            invoices,
        )
        if arm == "A":
            policy: EvaluationArm = ArmAPolicy()
            policy.initialize(customers)
        elif arm == "B":
            policy = ArmBPolicy()
            policy.initialize(customers)
        else:
            bank_name = f"eval-{run_id}-C-s{seed}"
            policy = ArmCPolicy(memory_store, bank_name=bank_name)
            policy.initialize(customers)
            await policy.start()
            run_result["hindsight_bank"] = bank_name

        training_events = _training_events(invoices, customers, world.start_date)
        retained_training_keys: set[tuple[str, str, str, str]] = set()
        for month in _LEARNING_MONTHS:
            month_end = _month_end(world.start_date, month)
            eligible = [
                event
                for event in training_events
                if date.fromisoformat(event["observed_on"]) <= month_end
                and _training_event_key(event) not in retained_training_keys
            ]
            if arm == "C":
                await policy.observe_training(eligible)
            else:
                policy.observe_training(eligible)
            retained_training_keys.update(_training_event_key(event) for event in eligible)
            run_result["learning_curve"].append(
                policy.knowledge_snapshot(customers, month)
            )

        if arm == "C":
            final_memory = policy.knowledge_snapshot(customers, 3)
            run_result["memory_evidence_count"] = final_memory["evidence_count"]
            run_result["memory_customers_with_evidence"] = final_memory[
                "customers_with_memory"
            ]
            run_result["memory_customers_missing_evidence"] = (
                len(customers) - final_memory["customers_with_memory"]
            )
        run_result["invoice_results"] = _evaluate_test_invoices(
            policy,
            invoices,
            customers,
        )
        run_result["status"] = "complete"
        run_result["metrics"] = compute_metrics([run_result])
    except Exception as exc:
        logger.exception("Evaluation arm %s failed for seed %s", arm, seed)
        run_result["error"] = f"{type(exc).__name__}: {exc}"
        run_result["failure_stage"] = "arm execution"
        run_result["metrics"] = compute_metrics([run_result])

    run_result["finished_at"] = clock.now().isoformat()
    if session is not None:
        _persist_run(session, run_result)
    return run_result


async def run_all_evaluations(
    *,
    seeds: tuple[int, ...] | list[int] = (1, 2, 3),
    scenario: str | Path = "eval",
    customer_count: int = 6,
    memory_store: Any | None = None,
    session: Session | None = None,
    result_path: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run each arm on identical seeds, then aggregate and optionally persist."""
    if not seeds:
        raise ValueError("seeds must be a non-empty sequence of unique integers")
    if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds):
        raise ValueError("all seeds must be integers")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique")
    if isinstance(customer_count, bool) or not isinstance(customer_count, int):
        raise ValueError("customer_count must be an integer")
    if not 1 <= customer_count <= 12:
        raise ValueError("customer_count must be between 1 and 12")

    run_id = run_id or uuid.uuid4().hex[:12]
    results: dict[str, Any] = {
        "run_id": run_id,
        "scenario": Path(scenario).stem if isinstance(scenario, Path) else Path(scenario).stem,
        "learning_months": 3,
        "testing_months": 3,
        "test_months": list(_TEST_MONTHS),
        "seeds": list(seeds),
        "customers_per_seed": customer_count,
        "simulation_only": True,
        "data_separation": {
            "training_months": list(_LEARNING_MONTHS),
            "testing_months": list(_TEST_MONTHS),
            "same_seed_and_scenario_for_each_arm": True,
            "test_outcomes_visible_during_training": False,
        },
        "arm_methodology": {
            "A": {
                "memory": "none",
                "blocker_knowledge": "fixed universal invoice-document checks only",
                "warning_rule": "two days before invoice due date",
            },
            "B": {
                "memory": "structured customer columns",
                "columns": ["credit_days", "po_required", "required_docs"],
                "warning_rule": (
                    "two days before invoice due date; payment-run days are not "
                    "structured columns"
                ),
            },
            "C": {
                "memory": (
                    "Hindsight-retained training experience with customer-scoped "
                    "recall and reflection"
                ),
                "warning_rule": (
                    "two days before the next payment-run day learned from "
                    "training evidence"
                ),
            },
        },
        "synthetic_blocker_case_generation": {
            "invoice_pdf_missing": "customer index + scenario month divisible by 5",
            "customer_document_missing": (
                "first required document omitted when customer index + "
                "scenario month is even"
            ),
            "po_missing": (
                "PO-required invoice omitted its PO when customer index + "
                "scenario month is divisible by 3"
            ),
        },
        "arms": {arm: {} for arm in _ARMS},
        "metrics": {},
    }
    for arm in _ARMS:
        for seed in seeds:
            run_result = await run_evaluation(
                arm,
                seed,
                scenario=scenario,
                customer_count=customer_count,
                memory_store=memory_store,
                session=session,
                run_id=run_id,
            )
            results["arms"][arm][str(seed)] = run_result

    for arm, runs in results["arms"].items():
        results["metrics"][arm] = compute_metrics(list(runs.values()))

    results["source_fingerprints"] = {
        seed: {
            arm: results["arms"][arm][str(seed)]["source_fingerprint"]
            for arm in _ARMS
        }
        for seed in seeds
    }
    results["report"] = generate_report(results)
    if result_path is None:
        result_path = Path(__file__).parent / "results" / "evaluation.json"
    _write_results(Path(result_path), results)
    return results


def _evaluation_customers(world: SimulationWorld) -> list[EvaluationCustomer]:
    return [
        EvaluationCustomer(
            key=customer.key,
            name=customer.name,
            payment_run_days=customer.profile.payment_run_days,
            po_required=customer.profile.po_required,
            required_docs=customer.profile.required_docs,
            credit_days=customer.profile.credit_days,
        )
        for customer in world.customers.values()
    ]


def _evaluation_invoices(
    world: SimulationWorld,
    customers: list[EvaluationCustomer],
) -> list[EvaluationInvoice]:
    customer_index = {customer.key: index for index, customer in enumerate(customers, start=1)}
    customer_lookup = {customer.key: customer for customer in customers}
    invoices: list[EvaluationInvoice] = []
    for invoice in world.invoices.values():
        month = (invoice.issue_date.year - world.start_date.year) * 12
        month += invoice.issue_date.month - world.start_date.month + 1
        if not 1 <= month <= 6:
            continue
        customer = customer_lookup[invoice.customer_key]
        pattern = month + customer_index[invoice.customer_key]
        missing_documents = (
            (customer.required_docs[0],)
            if customer.required_docs and pattern % 2 == 0
            else ()
        )
        attached_docs = tuple(
            doc for doc in customer.required_docs if doc not in missing_documents
        )
        missing_po = customer.po_required and pattern % 3 == 0
        fixed_missing = (
            ("INVOICE_PDF",)
            if pattern % _INVOICE_PDF_PATTERN_MODULUS == 0
            else ()
        )
        actual_missing = tuple(dict.fromkeys((*missing_documents, *fixed_missing)))
        invoices.append(
            EvaluationInvoice(
                customer_key=invoice.customer_key,
                invoice_number=invoice.number,
                month_index=month,
                issue_date=invoice.issue_date,
                due_date=invoice.due_date,
                payment_run_date=invoice.promised_date,
                payment_date=invoice.payment_date,
                amount_paise=invoice.amount_paise,
                required_docs=customer.required_docs,
                po_required=customer.po_required,
                attached_docs=attached_docs,
                po_number_present=not missing_po,
                missing_documents=actual_missing,
                fixed_missing_documents=fixed_missing,
                missing_po=missing_po,
            )
        )
    return sorted(invoices, key=lambda invoice: (invoice.issue_date, invoice.customer_key))


def _training_events(
    invoices: list[EvaluationInvoice],
    customers: list[EvaluationCustomer],
    start_date: date,
) -> list[dict[str, Any]]:
    customer_keys = {customer.key for customer in customers}
    events: list[dict[str, Any]] = []
    learning_end = _month_end(start_date, 3)
    for invoice in invoices:
        if invoice.month not in _LEARNING_MONTHS or invoice.customer_key not in customer_keys:
            continue
        customer_key = invoice.customer_key
        if invoice.payment_run_date <= learning_end:
            events.append(
                _training_fact(
                    customer_key,
                    invoice,
                    "payment_run_day",
                    invoice.payment_run_date.day,
                    invoice.payment_run_date,
                )
            )
        for doc in invoice.required_docs:
            if doc in invoice.missing_documents:
                events.append(
                    _training_fact(
                        customer_key,
                        invoice,
                        "required_document",
                        doc,
                        invoice.issue_date,
                    )
                )
        if invoice.missing_po:
            events.append(
                _training_fact(
                    customer_key,
                    invoice,
                    "po_required",
                    True,
                    invoice.issue_date,
                )
            )
    return sorted(
        events,
        key=lambda event: (
            event["observed_on"],
            event["customer_key"],
            event["fact_type"],
            str(event["value"]),
        ),
    )


def _training_fact(
    customer_key: str,
    invoice: EvaluationInvoice,
    fact_type: str,
    value: Any,
    observed_on: date,
) -> dict[str, Any]:
    return {
        "customer_key": customer_key,
        "invoice_number": invoice.invoice_number,
        "fact_type": fact_type,
        "value": value,
        "observed_on": observed_on.isoformat(),
    }


def _training_event_key(event: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(event["customer_key"]),
        str(event["invoice_number"]),
        str(event["fact_type"]),
        str(event["value"]),
    )


def _evaluate_test_invoices(
    policy: EvaluationArm,
    invoices: list[EvaluationInvoice],
    customers: list[EvaluationCustomer],
) -> list[dict[str, Any]]:
    customer_keys = {customer.key for customer in customers}
    results = []
    for invoice in invoices:
        if invoice.month not in _TEST_MONTHS or invoice.customer_key not in customer_keys:
            continue
        decision = policy.decide(invoice)
        warning_lead_days = (
            (invoice.payment_run_date - decision.warning_date).days
            if decision.warning_date is not None
            else None
        )
        results.append(
            {
                "customer_key": invoice.customer_key,
                "invoice_number": invoice.invoice_number,
                "month": invoice.month,
                "due_date": invoice.due_date.isoformat(),
                "payment_run_date": invoice.payment_run_date.isoformat(),
                "payment_date": invoice.payment_date.isoformat(),
                "days_late": max(0, (invoice.payment_date - invoice.due_date).days),
                "actual_blocker": invoice.is_blocker,
                "blocker_caught": invoice.is_blocker and decision.blocker_detected,
                "blocker_false_positive": (
                    not invoice.is_blocker and decision.blocker_detected
                ),
                "warning_date": (
                    decision.warning_date.isoformat()
                    if decision.warning_date is not None
                    else None
                ),
                "warning_lead_days": warning_lead_days,
                "detected_codes": decision.detected_codes,
                "actual_missing_codes": [
                    *invoice.missing_documents,
                    *(["PO_REF"] if invoice.missing_po else []),
                ],
            }
        )
    return results


def _month_end(start_date: date, month_number: int) -> date:
    month_index = start_date.year * 12 + start_date.month - 1 + month_number
    year, month = divmod(month_index, 12)
    next_month = date(year, month + 1, 1)
    return next_month - timedelta(days=1)


def _source_fingerprint(
    seed: int,
    scenario: str,
    invoices: list[EvaluationInvoice],
) -> str:
    payload = {
        "seed": seed,
        "scenario": scenario,
        "invoices": [
            {
                "customer": invoice.customer_key,
                "number": invoice.invoice_number,
                "issue_date": invoice.issue_date.isoformat(),
                "due_date": invoice.due_date.isoformat(),
                "payment_run_date": invoice.payment_run_date.isoformat(),
                "payment_date": invoice.payment_date.isoformat(),
                "amount_paise": invoice.amount_paise,
                "actual_missing_codes": [
                    *invoice.missing_documents,
                    *(["PO_REF"] if invoice.missing_po else []),
                ],
            }
            for invoice in invoices
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _persist_run(session: Session, result: dict[str, Any]) -> None:
    row = SimRun(
        arm=SimArm(result["arm"]),
        seed=result["seed"],
        config={
            "scenario": result.get("scenario"),
            "source_fingerprint": result.get("source_fingerprint"),
            "learning_months": result.get("learning_months"),
            "testing_months": result.get("testing_months"),
            "customer_count": result.get("customer_count"),
            "run_id": result.get("run_id"),
            "status": result.get("status"),
        },
        metrics=result.get("metrics", {}),
        started_at=datetime.fromisoformat(result["started_at"]),
        finished_at=datetime.fromisoformat(result["finished_at"]),
    )
    session.add(row)
    session.flush()


def _write_results(path: Path, results: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(results, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Command-line entrypoint for the documented three-seed evaluation."""
    asyncio.run(run_all_evaluations())


if __name__ == "__main__":
    main()
