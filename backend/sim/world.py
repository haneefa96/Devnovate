"""Seeded customer simulation world with optional SQLite persistence."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlmodel import Session, select

from munshi.db.models import (
    Business,
    Customer,
    CustomerRiskLevel,
    InboundMessage,
    Invoice,
    InvoiceStatus,
    Payment,
    Promise,
)
from sim.personas import DEMO_PERSONAS, CustomerPersona
from sim.profiles import CUSTOMER_PROFILES, CustomerProfile

_DEFAULT_START_DATE = date(2026, 1, 1)
_AVERAGE_INVOICE_AMOUNT_PAISE = 4_820_000


class ScenarioMonths(BaseModel):
    learning: int = Field(ge=0)
    testing: int = Field(ge=0)

    @model_validator(mode="after")
    def require_duration(self) -> "ScenarioMonths":
        if self.learning + self.testing < 1:
            raise ValueError("scenario duration must be at least one month")
        return self


class ScenarioInvoice(BaseModel):
    number: str = Field(min_length=1, max_length=100)
    amount_paise: int = Field(gt=0)
    due_days: int = Field(ge=0)


class ScenarioCustomer(BaseModel):
    name: str
    profile: str
    invoices: list[ScenarioInvoice] = Field(default_factory=list)


class ScenarioEvent(BaseModel):
    day: int = Field(ge=1)
    type: str
    customer: str | None = None
    result: str | None = None


class ScenarioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    seed: int
    start_date: date = _DEFAULT_START_DATE
    months: ScenarioMonths
    customers: list[ScenarioCustomer] = Field(min_length=1, max_length=12)
    events: list[ScenarioEvent] = Field(default_factory=list)


@dataclass
class SimulatedCustomer:
    key: str
    name: str
    profile: CustomerProfile
    persona: CustomerPersona
    database_id: int | None = None
    explicit_invoice_plan: bool = False


@dataclass
class SimulatedInvoice:
    customer_key: str
    number: str
    issue_date: date
    due_date: date
    amount_paise: int
    payment_date: date
    promised_date: date
    database_id: int | None = None
    promise_database_id: int | None = None
    payment_recorded: bool = False
    missed_promise_message_sent: bool = False

    @property
    def status(self) -> str:
        return "PAID" if self.payment_recorded else "OPEN"


class SimulationWorld:
    """Owns synthetic customers, invoices, promises, messages, and payment events.

    A SQLModel session is optional. When supplied, generated rows are flushed to
    that session but never committed; transaction ownership remains with the caller.
    """

    def __init__(
        self,
        seed: int = 1,
        *,
        start_date: date = _DEFAULT_START_DATE,
        session: Session | None = None,
        business_id: int | None = None,
        scenario_name: str | None = None,
        learning_months: int = 3,
        testing_months: int = 3,
    ):
        self.seed = seed
        self.start_date = start_date
        self.date = start_date
        self.tick_count = 0
        self.customers: dict[str, SimulatedCustomer] = {}
        self.invoices: dict[str, SimulatedInvoice] = {}
        self.payments: list[dict[str, Any]] = []
        self.promises: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.scenario_name = scenario_name
        self.learning_months = learning_months
        self.testing_months = testing_months
        self._session = session
        self._business_id = self._find_business_id(session, business_id)
        self._scenario_events: list[ScenarioEvent] = []
        self._invoice_sequence = 0
        self._simulation_end_date: date | None = None
        self._scenario_executed = False

    @staticmethod
    def _find_business_id(session: Session | None, business_id: int | None) -> int | None:
        if session is None:
            if business_id is not None:
                raise ValueError("business_id requires a persistence session")
            return None
        if business_id is not None:
            if session.get(Business, business_id) is None:
                raise ValueError(f"business {business_id} does not exist")
            return business_id
        business = session.exec(select(Business).order_by(Business.id)).first()
        if business is None or business.id is None:
            raise ValueError("a persisted simulation requires an existing business")
        return business.id

    @classmethod
    def from_scenario(
        cls,
        scenario: str | Path = "demo",
        *,
        seed: int | None = None,
        customer_count: int | None = None,
        session: Session | None = None,
        business_id: int | None = None,
    ) -> "SimulationWorld":
        """Load a checked-in scenario and build its synthetic customer cohort.

        Scenario files use JSON syntax, which is also valid YAML 1.2, so the
        simulator can load them without adding a YAML runtime dependency.
        """
        path = Path(scenario)
        if not path.is_file():
            path = Path(__file__).parent / "scenarios" / (
                path.name if path.suffix else f"{path.name}.yaml"
            )
        if not path.is_file():
            raise FileNotFoundError(f"simulation scenario not found: {path}")
        config = ScenarioConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))
        world = cls(
            seed=config.seed if seed is None else seed,
            start_date=config.start_date,
            session=session,
            business_id=business_id,
            scenario_name=config.name,
            learning_months=config.months.learning,
            testing_months=config.months.testing,
        )
        scenario_customers = list(config.customers)
        if customer_count is not None:
            if not 1 <= customer_count <= len(CUSTOMER_PROFILES):
                raise ValueError(f"customer_count must be between 1 and {len(CUSTOMER_PROFILES)}")
            if customer_count < len(scenario_customers):
                scenario_customers = scenario_customers[:customer_count]
            else:
                configured_profiles = {item.profile for item in scenario_customers}
                for key, profile in CUSTOMER_PROFILES.items():
                    if len(scenario_customers) >= customer_count:
                        break
                    if key not in configured_profiles:
                        scenario_customers.append(
                            ScenarioCustomer(name=profile.name, profile=key)
                        )

        for index, scenario_customer in enumerate(scenario_customers, start=1):
            profile = CUSTOMER_PROFILES.get(scenario_customer.profile)
            if profile is None:
                raise ValueError(f"unknown customer profile: {scenario_customer.profile}")
            world.add_customer(
                scenario_customer.profile,
                profile,
                name=scenario_customer.name,
                explicit_invoice_plan=bool(scenario_customer.invoices),
                profile_index=index,
            )
            for invoice in scenario_customer.invoices:
                world._create_invoice(
                    scenario_customer.profile,
                    invoice.number,
                    invoice.amount_paise,
                    issue_date=config.start_date,
                    due_days=invoice.due_days,
                )
        world._scenario_events = config.events
        return world

    def add_customer(
        self,
        key: str,
        profile: CustomerProfile | None = None,
        *,
        name: str | None = None,
        explicit_invoice_plan: bool = False,
        profile_index: int | None = None,
    ) -> SimulatedCustomer:
        """Add one profile to this world, optionally creating a synthetic DB row."""
        if key in self.customers:
            raise ValueError(f"customer already exists in simulation: {key}")
        profile = profile or CUSTOMER_PROFILES.get(key)
        if profile is None:
            raise ValueError(f"unknown customer profile: {key}")
        persona = DEMO_PERSONAS.get(key)
        if persona is None:
            raise ValueError(f"no deterministic persona is configured for profile: {key}")

        customer = SimulatedCustomer(
            key=key,
            name=name or profile.name,
            profile=profile,
            persona=persona,
            explicit_invoice_plan=explicit_invoice_plan,
        )
        if self._session is not None:
            index = profile_index or len(self.customers) + 1
            db_customer = Customer(
                business_id=self._business_id,
                name=f"[SIM] {customer.name}",
                gstin=f"27SIMU{index:06d}1Z5",
                state_code="27",
                credit_days=profile.credit_days,
                po_required=profile.po_required,
                required_docs=list(profile.required_docs),
                contact_name=profile.contact_name,
                contact_role=profile.contact_role,
                risk_level=CustomerRiskLevel(profile.risk_level),
            )
            self._session.add(db_customer)
            self._session.flush()
            customer.database_id = db_customer.id
        self.customers[key] = customer
        if not explicit_invoice_plan:
            self._create_monthly_invoice(customer, self.date)
        return customer

    def _create_monthly_invoice(self, customer: SimulatedCustomer, issue_date: date) -> None:
        self._invoice_sequence += 1
        month_token = issue_date.strftime("%Y%m")
        invoice_number = f"SIM-{self.seed}-{customer.key[:8]}-{month_token}"
        rng = random.Random(f"{self.seed}:amount:{customer.key}:{month_token}")
        amount_variation = _AVERAGE_INVOICE_AMOUNT_PAISE // 20
        variation = rng.randint(-amount_variation, amount_variation)
        amount_paise = _AVERAGE_INVOICE_AMOUNT_PAISE + variation
        self._create_invoice(
            customer.key,
            invoice_number,
            amount_paise,
            issue_date=issue_date,
            due_days=customer.profile.credit_days,
        )

    def _create_invoice(
        self,
        customer_key: str,
        number: str,
        amount_paise: int,
        *,
        issue_date: date,
        due_days: int,
    ) -> SimulatedInvoice:
        if number in self.invoices:
            raise ValueError(f"duplicate simulated invoice number: {number}")
        if customer_key not in self.customers:
            raise ValueError(f"unknown simulated customer: {customer_key}")
        customer = self.customers[customer_key]
        due_date = issue_date + timedelta(days=due_days)
        run_date = _next_payment_run(due_date, customer.profile.payment_run_days)
        rng = random.Random(f"{self.seed}:payment:{customer_key}:{number}")
        delay = customer.profile.typical_delay_days
        if rng.randrange(10_000) >= customer.profile.payment_reliability_bps:
            delay += rng.randint(14, 30)
        payment_date = run_date + timedelta(days=delay)

        simulated = SimulatedInvoice(
            customer_key=customer_key,
            number=number,
            issue_date=issue_date,
            due_date=due_date,
            amount_paise=amount_paise,
            payment_date=payment_date,
            promised_date=run_date,
        )
        if self._session is not None:
            db_invoice = Invoice(
                customer_id=customer.database_id,
                number=number,
                issue_date=issue_date,
                due_date=due_date,
                amount_paise=amount_paise,
                status=InvoiceStatus.SENT,
            )
            self._session.add(db_invoice)
            self._session.flush()
            simulated.database_id = db_invoice.id
        self.invoices[number] = simulated
        return simulated

    def tick(self, days: int = 1) -> None:
        """Advance simulated time one calendar day at a time."""
        if isinstance(days, bool) or not isinstance(days, int) or days < 1:
            raise ValueError("days must be a positive integer")
        for _ in range(days):
            self.date += timedelta(days=1)
            self.tick_count += 1
            if self.date.day == 1 and (
                self._simulation_end_date is None or self.date < self._simulation_end_date
            ):
                for customer in self.customers.values():
                    if not customer.explicit_invoice_plan:
                        self._create_monthly_invoice(customer, self.date)
            self._process_day()

    def _process_day(self) -> None:
        for invoice in self.invoices.values():
            if self.date >= invoice.due_date and invoice.promise_database_id is None:
                self._create_promise(invoice)
            if (
                invoice.promise_database_id is not None
                and self.date > invoice.promised_date
                and not invoice.payment_recorded
                and not invoice.missed_promise_message_sent
            ):
                self._mark_promise_missed(invoice)
                self._record_missed_promise_message(invoice)
            if self.date >= invoice.payment_date and not invoice.payment_recorded:
                self._record_payment(invoice)

    def _create_promise(self, invoice: SimulatedInvoice) -> None:
        customer = self.customers[invoice.customer_key]
        promise_data = {
            "customer": invoice.customer_key,
            "invoice": invoice.number,
            "promised_by": customer.profile.contact_name,
            "promised_date": invoice.promised_date.isoformat(),
            "kept": None,
        }
        self.promises.append(promise_data)
        if self._session is not None:
            row = Promise(
                invoice_id=invoice.database_id,
                customer_id=customer.database_id,
                promised_by=customer.profile.contact_name,
                promised_date=invoice.promised_date,
            )
            self._session.add(row)
            self._session.flush()
            invoice.promise_database_id = row.id
        else:
            invoice.promise_database_id = len(self.promises)

    def _record_payment(self, invoice: SimulatedInvoice) -> None:
        customer = self.customers[invoice.customer_key]
        payment_data = {
            "customer": invoice.customer_key,
            "invoice": invoice.number,
            "amount_paise": invoice.amount_paise,
            "paid_on": self.date.isoformat(),
            "reference": f"SIM-{self.seed}-{invoice.number}",
        }
        if self._session is not None:
            row = Payment(
                invoice_id=invoice.database_id,
                customer_id=customer.database_id,
                amount_paise=invoice.amount_paise,
                paid_on=self.date,
                reference=payment_data["reference"],
            )
            self._session.add(row)
            db_invoice = self._session.get(Invoice, invoice.database_id)
            if db_invoice is None:
                raise RuntimeError(f"persisted simulation invoice missing: {invoice.database_id}")
            db_invoice.status = InvoiceStatus.PAID
            self._session.add(db_invoice)
            self._session.flush()
        invoice.payment_recorded = True
        self.payments.append(payment_data)
        for promise in self.promises:
            if promise["invoice"] == invoice.number and promise["kept"] is None:
                promise["kept"] = self.date <= invoice.promised_date
        if self._session is not None and invoice.promise_database_id is not None:
            db_promise = self._session.get(Promise, invoice.promise_database_id)
            if db_promise is not None:
                db_promise.kept = self.date <= invoice.promised_date
                self._session.add(db_promise)
                self._session.flush()

    def _mark_promise_missed(self, invoice: SimulatedInvoice) -> None:
        for promise in self.promises:
            if promise["invoice"] == invoice.number and promise["kept"] is None:
                promise["kept"] = False
        if self._session is not None and invoice.promise_database_id is not None:
            db_promise = self._session.get(Promise, invoice.promise_database_id)
            if db_promise is None:
                raise RuntimeError(
                    f"persisted simulation promise missing: {invoice.promise_database_id}"
                )
            db_promise.kept = False
            self._session.add(db_promise)
            self._session.flush()

    def _record_missed_promise_message(self, invoice: SimulatedInvoice) -> None:
        customer = self.customers[invoice.customer_key]
        distress = bool(customer.profile.distress_cues)
        message_kind = "distress" if distress else "overdue"
        body = customer.persona.get_response(
            message_kind,
            {"response_type": message_kind, "invoice": invoice.number},
        )
        message_data = {
            "customer": customer.key,
            "invoice": invoice.number,
            "received_at": self.date.isoformat(),
            "body": body,
        }
        if self._session is not None:
            self._session.add(
                InboundMessage(
                    customer_id=customer.database_id,
                    invoice_id=invoice.database_id,
                    channel="SIMULATED",
                    sender_name=customer.profile.contact_name,
                    body=body,
                )
            )
            self._session.flush()
        self.messages.append(message_data)
        invoice.missed_promise_message_sent = True

    def inject_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Apply one documented synthetic customer event to this world."""
        if event_type not in {"CONTACT_CHANGE", "REQUIREMENT_CHANGE", "DISTRESS_START"}:
            raise ValueError(f"unsupported simulation event type: {event_type}")
        customer = self._resolve_customer(payload)
        event: dict[str, Any] = {
            "type": event_type,
            "customer": customer.key,
            "date": self.date.isoformat(),
        }
        if event_type == "CONTACT_CHANGE":
            contact_name = payload.get("contact_name")
            if not isinstance(contact_name, str) or not contact_name.strip():
                raise ValueError("CONTACT_CHANGE requires a non-empty contact_name")
            customer.profile = _replace_profile(customer.profile, contact_name=contact_name.strip())
            event["contact_name"] = customer.profile.contact_name
            if self._session is not None and customer.database_id is not None:
                row = self._session.get(Customer, customer.database_id)
                if row is None:
                    raise RuntimeError(
                        f"persisted simulation customer missing: {customer.database_id}"
                    )
                row.contact_name = customer.profile.contact_name
                self._session.add(row)
        elif event_type == "REQUIREMENT_CHANGE":
            required_docs = payload.get("required_docs")
            if (
                not isinstance(required_docs, list)
                or not all(isinstance(item, str) and item for item in required_docs)
            ):
                raise ValueError("REQUIREMENT_CHANGE requires required_docs as a list of strings")
            customer.profile = _replace_profile(
                customer.profile,
                required_docs=tuple(dict.fromkeys(required_docs)),
            )
            event["required_docs"] = list(customer.profile.required_docs)
            if self._session is not None and customer.database_id is not None:
                row = self._session.get(Customer, customer.database_id)
                if row is None:
                    raise RuntimeError(
                        f"persisted simulation customer missing: {customer.database_id}"
                    )
                row.required_docs = list(customer.profile.required_docs)
                self._session.add(row)
        else:
            cue = payload.get("cue", "cash-flow trouble")
            if not isinstance(cue, str) or not cue.strip():
                raise ValueError("DISTRESS_START cue must be a non-empty string")
            customer.profile = _replace_profile(
                customer.profile,
                distress_cues=customer.profile.distress_cues + (cue.strip(),),
            )
            event["cue"] = cue.strip()
            event["message"] = customer.persona.get_response(
                "distress",
                {"response_type": "distress"},
            )
            message_data = {
                "customer": customer.key,
                "invoice": None,
                "received_at": self.date.isoformat(),
                "body": event["message"],
            }
            if self._session is not None:
                self._session.add(
                    InboundMessage(
                        customer_id=customer.database_id,
                        channel="SIMULATED",
                        sender_name=customer.profile.contact_name,
                        body=event["message"],
                    )
                )
                self._session.flush()
            self.messages.append(message_data)
        if self._session is not None:
            self._session.flush()
        self.events.append(event)

    def _resolve_customer(self, payload: dict[str, Any]) -> SimulatedCustomer:
        key = payload.get("customer") or payload.get("customer_key")
        if key is None:
            database_id = payload.get("customer_id")
            key = next(
                (
                    customer.key
                    for customer in self.customers.values()
                    if customer.database_id == database_id
                ),
                None,
            )
        if key not in self.customers:
            raise ValueError(f"unknown simulated customer: {key}")
        return self.customers[key]

    def run_scenario(self) -> dict[str, Any]:
        """Execute all scheduled scenario events, then run its full duration."""
        if self.scenario_name is None:
            raise ValueError("run_scenario requires a world loaded from a scenario")
        if self._scenario_executed:
            raise ValueError("scenario has already been executed")
        self._simulation_end_date = _add_months(
            self.start_date,
            self.learning_months + self.testing_months,
        )
        for event in sorted(self._scenario_events, key=lambda item: item.day):
            target = self.start_date + timedelta(days=event.day - 1)
            if target > self._simulation_end_date:
                raise ValueError(f"scenario event falls outside its duration: day {event.day}")
            if target > self.date:
                self.tick((target - self.date).days)
            if event.type == "payment_run":
                self.events.append(
                    {
                        "type": "payment_run",
                        "customer": event.customer,
                        "result": event.result,
                        "date": self.date.isoformat(),
                    }
                )
            else:
                payload: dict[str, Any] = {}
                if event.customer:
                    payload["customer"] = next(
                        (
                            key
                            for key, customer in self.customers.items()
                            if customer.name == event.customer or key == event.customer
                        ),
                        event.customer,
                    )
                self.inject_event(event.type, payload)

        if self._simulation_end_date > self.date:
            self.tick((self._simulation_end_date - self.date).days)
        self._scenario_executed = True
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic summary metadata for the world."""
        return {
            "date": self.date.isoformat(),
            "tick_count": self.tick_count,
            "customer_count": len(self.customers),
            "invoice_count": len(self.invoices),
            "payment_count": len(self.payments),
            "promise_count": len(self.promises),
            "message_count": len(self.messages),
            "seed": self.seed,
            "scenario": self.scenario_name,
        }


def create_world(
    seed: int = 1,
    *,
    scenario: str | Path | None = None,
    customer_count: int | None = None,
    session: Session | None = None,
    business_id: int | None = None,
) -> SimulationWorld:
    """Create an empty seeded world or load a named simulation scenario."""
    if scenario is not None:
        return SimulationWorld.from_scenario(
            scenario,
            seed=seed,
            customer_count=customer_count,
            session=session,
            business_id=business_id,
        )
    return SimulationWorld(seed=seed, session=session, business_id=business_id)


def _next_payment_run(due_date: date, run_days: tuple[int, ...]) -> date:
    """Find the first configured payment-run day on or after the due date."""
    current = date(due_date.year, due_date.month, 1)
    for _ in range(24):
        for day in sorted(run_days):
            candidate = date(current.year, current.month, day)
            if candidate >= due_date:
                return candidate
        current = _add_months(current, 1)
    raise ValueError("could not find a payment run within two years")


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, min(value.day, 28))


def _replace_profile(profile: CustomerProfile, **changes: Any) -> CustomerProfile:
    values = profile.to_dict()
    values.update(changes)
    for key in ("payment_run_days", "required_docs", "distress_cues"):
        values[key] = tuple(values[key])
    return CustomerProfile(**values)
