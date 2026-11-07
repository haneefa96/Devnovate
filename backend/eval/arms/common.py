"""Shared deterministic data contracts for evaluation arms."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


@dataclass(frozen=True)
class EvaluationCustomer:
    key: str
    name: str
    payment_run_days: tuple[int, ...]
    po_required: bool
    required_docs: tuple[str, ...]
    credit_days: int


@dataclass(frozen=True)
class EvaluationInvoice:
    customer_key: str
    invoice_number: str
    month_index: int
    issue_date: date
    due_date: date
    payment_run_date: date
    payment_date: date
    amount_paise: int
    required_docs: tuple[str, ...]
    po_required: bool
    attached_docs: tuple[str, ...]
    po_number_present: bool
    missing_documents: tuple[str, ...]
    fixed_missing_documents: tuple[str, ...]
    missing_po: bool

    @property
    def month(self) -> int:
        """Return the one-based month within the six-month scenario."""
        return self.month_index

    @property
    def is_blocker(self) -> bool:
        return bool(self.missing_documents or self.missing_po)


@dataclass
class ArmDecision:
    blocker_detected: bool
    warning_date: date | None
    detected_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocker_detected": self.blocker_detected,
            "warning_date": self.warning_date.isoformat() if self.warning_date else None,
            "detected_codes": list(self.detected_codes),
        }


class EvaluationArm:
    """Base strategy using only information explicitly provided by the runner."""

    arm: str
    name: str

    def __init__(self) -> None:
        self.known_documents: dict[str, set[str]] = {}
        self.known_po_required: dict[str, bool] = {}
        self.known_payment_run_days: dict[str, set[int]] = {}

    def initialize(self, customers: list[EvaluationCustomer]) -> None:
        """Initialize arm knowledge without exposing test outcomes."""

    def observe_training(self, events: list[dict[str, Any]]) -> None:
        """Learn only from events observed during the training window."""

    def decide(self, invoice: EvaluationInvoice) -> ArmDecision:
        """Evaluate observable fixed checks and known customer-specific facts."""
        detected: list[str] = []
        detected.extend(invoice.fixed_missing_documents)

        known_docs = self.known_documents.get(invoice.customer_key, set())
        detected.extend(
            doc
            for doc in known_docs
            if doc not in invoice.attached_docs
        )
        if (
            self.known_po_required.get(invoice.customer_key, False)
            and not invoice.po_number_present
        ):
            detected.append("PO_REF")

        warning_date = self._warning_date(invoice)
        return ArmDecision(
            blocker_detected=bool(detected),
            warning_date=warning_date,
            detected_codes=list(dict.fromkeys(detected)),
        )

    def _warning_date(self, invoice: EvaluationInvoice) -> date | None:
        """Fixed baseline warning two days before the invoice due date."""
        return invoice.due_date - timedelta(days=2)

    def knowledge_snapshot(
        self,
        customers: list[EvaluationCustomer],
        month: int,
    ) -> dict[str, Any]:
        """Report learned requirement and payment-run facts at a training month."""
        total = sum(2 + len(customer.required_docs) for customer in customers)
        known = sum(
            int(customer.key in self.known_po_required)
            + len(self.known_documents.get(customer.key, set()))
            + int(bool(self.known_payment_run_days.get(customer.key)))
            for customer in customers
        )
        return {
            "month": month,
            "known_facts": known,
            "total_facts": total,
            "coverage": known / total if total else None,
        }


def event_payload(content: Any) -> dict[str, Any] | None:
    """Parse a canonical JSON fact from Hindsight's recalled content."""
    import json

    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return None
    try:
        value = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
