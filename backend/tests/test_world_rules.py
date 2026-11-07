"""Regression tests for the seeded simulation engine."""

from datetime import date

import pytest
from sqlalchemy import text
from sqlmodel import Session, create_engine, select
from sqlalchemy.pool import StaticPool

from munshi.db.models import (
    Action,
    Business,
    Customer,
    InboundMessage,
    Invoice,
    InvoiceStatus,
    Payment,
    Promise,
)
from munshi.db.session import init_db
from sim.calibrate import calibrate_world
from sim.personas import DEMO_PERSONAS
from sim.profiles import CUSTOMER_PROFILES
from sim.world import SimulationWorld, create_world


def _world_result(seed: int) -> tuple[dict[str, object], list[dict], list[dict]]:
    world = SimulationWorld.from_scenario("eval", seed=seed)
    result = world.run_scenario()
    return result, world.payments, world.promises


def test_world_creation_and_time_advancement():
    world = SimulationWorld(seed=1)
    assert world.seed == 1
    assert world.tick_count == 0
    assert world.date == date(2026, 1, 1)

    world.tick(days=3)
    assert world.date == date(2026, 1, 4)
    assert world.tick_count == 3


@pytest.mark.parametrize("days", [0, -1, 1.5, True])
def test_tick_rejects_non_positive_or_non_integer_days(days):
    with pytest.raises(ValueError, match="positive integer"):
        SimulationWorld().tick(days=days)


def test_same_seed_and_scenario_produce_repeatable_results():
    first = _world_result(3)
    second = _world_result(3)
    assert first == second


def test_profile_cohort_and_scenario_sizes():
    assert len(CUSTOMER_PROFILES) == 12
    assert set(CUSTOMER_PROFILES) == set(DEMO_PERSONAS)
    assert calibrate_world()["months_of_learning"] == 3
    assert calibrate_world()["months_of_testing"] == 3
    assert calibrate_world()["available_customers"] == 12

    demo = SimulationWorld.from_scenario("demo")
    evaluation = SimulationWorld.from_scenario("eval")
    assert len(demo.customers) == 4
    assert sum(invoice.customer_key == "reddy-traders" for invoice in demo.invoices.values()) == 4
    assert len(demo.invoices) == 7
    assert len(evaluation.customers) == 6


def test_full_cohort_supports_twelve_customers_for_six_months():
    world = SimulationWorld.from_scenario("eval", customer_count=12)
    result = world.run_scenario()
    assert result["customer_count"] == 12
    assert result["date"] == "2026-07-01"
    assert result["invoice_count"] == 72


def test_demo_scenario_executes_payment_runs_for_six_months():
    world = SimulationWorld.from_scenario("demo", seed=1)
    result = world.run_scenario()
    assert result["date"] == "2026-07-01"
    assert result["tick_count"] == 181
    assert result["customer_count"] == 4
    assert result["invoice_count"] == 22
    assert any(event["type"] == "payment_run" for event in world.events)
    assert all(payment["amount_paise"] > 0 for payment in world.payments)


def test_payment_and_promise_are_recorded_deterministically():
    world = SimulationWorld(seed=9, start_date=date(2026, 1, 1))
    world.add_customer(
        "nair-components",
        explicit_invoice_plan=True,
    )
    invoice = world._create_invoice(
        "nair-components",
        "SIM-NAIR-1",
        500_000,
        issue_date=date(2026, 1, 1),
        due_days=0,
    )
    world.tick(days=(invoice.payment_date - world.date).days)

    assert len(world.payments) == 1
    assert world.payments[0]["invoice"] == invoice.number
    assert world.payments[0]["amount_paise"] == 500_000
    assert world.promises[0]["kept"] is True
    assert invoice.status == "PAID"


def test_missed_promise_generates_customer_message():
    world = SimulationWorld(seed=2)
    customer_profile = CUSTOMER_PROFILES["patel-enterprises"]
    world.add_customer("patel-enterprises", customer_profile, explicit_invoice_plan=True)
    invoice = world._create_invoice(
        "patel-enterprises",
        "SIM-PATEL-MISSED",
        200_000,
        issue_date=date(2026, 1, 1),
        due_days=0,
    )
    assert invoice.payment_date > invoice.promised_date
    world.tick(days=(invoice.promised_date - world.date).days)
    assert world.promises[0]["kept"] is None
    world.tick()
    assert world.messages
    assert "cash-flow trouble" in world.messages[0]["body"]
    assert world.promises[0]["kept"] is False
    world.tick(days=(invoice.payment_date - world.date).days)
    assert world.promises[0]["kept"] is False


def test_event_injection_updates_only_selected_customer():
    world = SimulationWorld.from_scenario("eval")
    original_contact = world.customers["reddy-traders"].profile.contact_name
    world.inject_event(
        "CONTACT_CHANGE",
        {"customer": "reddy-traders", "contact_name": "Rahul"},
    )
    world.inject_event(
        "REQUIREMENT_CHANGE",
        {"customer": "reddy-traders", "required_docs": ["SIGNED_CHALLAN", "GRN"]},
    )
    world.inject_event(
        "DISTRESS_START",
        {"customer": "patel-enterprises", "cue": "cash flow is tight"},
    )

    assert original_contact != world.customers["reddy-traders"].profile.contact_name
    assert world.customers["reddy-traders"].profile.contact_name == "Rahul"
    assert world.customers["reddy-traders"].profile.required_docs == (
        "SIGNED_CHALLAN",
        "GRN",
    )
    assert world.customers["sharma-suppliers"].profile.contact_name == "Amit"
    assert len(world.messages) == 1
    assert len(world.events) == 3


def test_invalid_events_and_unknown_customers_are_explicit():
    world = SimulationWorld.from_scenario("demo")
    with pytest.raises(ValueError, match="unsupported"):
        world.inject_event("UNKNOWN", {})
    with pytest.raises(ValueError, match="contact_name"):
        world.inject_event("CONTACT_CHANGE", {"customer": "reddy-traders"})
    with pytest.raises(ValueError, match="unknown simulated customer"):
        world.inject_event(
            "DISTRESS_START",
            {"customer": "not-a-customer"},
        )


def test_persistence_keeps_simulated_records_consistent():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    with Session(engine) as session:
        business = Business(
            name="Simulation Test Business",
            gstin="27AAACA1234A1Z1",
            state_code="27",
            bank_id="sim-test",
        )
        session.add(business)
        session.flush()

        world = SimulationWorld.from_scenario(
            "eval",
            seed=1,
            session=session,
            business_id=business.id,
        )
        world.run_scenario()
        session.commit()

        customers = session.exec(select(Customer)).all()
        invoices = session.exec(select(Invoice)).all()
        payments = session.exec(select(Payment)).all()
        promises = session.exec(select(Promise)).all()
        messages = session.exec(select(InboundMessage)).all()
        assert len(customers) == 6
        assert len(invoices) == len(world.invoices)
        assert len(payments) == len(world.payments)
        assert len(promises) == len(world.promises)
        assert len(messages) == len(world.messages)
        assert all(payment.reference.startswith("SIM-") for payment in payments)
        assert all(invoice.status == InvoiceStatus.PAID for invoice in invoices if any(
            payment.invoice_id == invoice.id for payment in payments
        ))
        assert all(message.channel == "SIMULATED" for message in messages)
        assert session.exec(select(Action)).all() == []
        assert session.exec(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()


def test_database_persistence_requires_explicit_business():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    init_db(engine)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="existing business"):
            SimulationWorld.from_scenario("demo", session=session)
    engine.dispose()


def test_seeded_factory_can_load_a_scenario():
    world = create_world(seed=5, scenario="eval")
    assert world.seed == 5
    assert world.scenario_name == "eval"
    assert len(world.customers) == 6
