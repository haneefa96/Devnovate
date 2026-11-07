"""Arm C: Hindsight experience memory with isolated evaluation banks."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, time
from typing import Any

from munshi.config import clock
from munshi.memory.queries import MemoryStore

from .common import EvaluationArm, EvaluationCustomer, event_payload


class HindsightUnavailableError(RuntimeError):
    """Raised when Arm C cannot use its required external memory service."""


class ArmCPolicy(EvaluationArm):
    """Learns customer facts only from Hindsight events retained during training."""

    arm = "C"
    name = "Hindsight customer memory"

    def __init__(
        self,
        memory_store: Any | None = None,
        *,
        bank_name: str,
    ) -> None:
        super().__init__()
        self.memory_store = memory_store or MemoryStore()
        self.bank_name = bank_name
        self.customers: list[EvaluationCustomer] = []
        self.memory_evidence: dict[str, set[str]] = {}
        self.reflected_requirement_count = 0

    def initialize(self, customers: list[EvaluationCustomer]) -> None:
        self.customers = list(customers)

    async def start(self) -> None:
        if not self.memory_store.is_available:
            raise HindsightUnavailableError("Hindsight is unavailable; Arm C cannot run")
        created = await self.memory_store.create_bank(
            bank_name=self.bank_name,
            business_name=f"Evaluation {self.bank_name}",
        )
        if not created:
            raise HindsightUnavailableError(
                f"could not create isolated Hindsight bank {self.bank_name}"
            )

    async def observe_training(self, events: list[dict[str, Any]]) -> None:
        """Retain only eligible training evidence, then retrieve it customer by customer."""
        for event in events:
            customer_key = str(event["customer_key"])
            event_date = date.fromisoformat(str(event["observed_on"]))
            content = json.dumps(event, sort_keys=True, separators=(",", ":"))
            response = await self.memory_store.retain(
                bank_name=self.bank_name,
                timestamp=datetime.combine(event_date, time.min, tzinfo=clock.now().tzinfo),
                customer_id=customer_key,
                invoice_id=str(event.get("invoice_number") or "") or None,
                content=content,
                tags=[f"customer:{customer_key}", "kind:experience"],
                event_type="experience",
            )
            if not response:
                raise HindsightUnavailableError(
                    f"Hindsight retain failed for customer {customer_key}"
                )

        for customer in self.customers:
            if not self.memory_store.is_available:
                raise HindsightUnavailableError("Hindsight became unavailable during evaluation")
            memories = await self.memory_store.recall(
                bank_name=self.bank_name,
                customer_id=customer.key,
                kind="experience",
                query="customer payment runs, invoice holds, document requirements",
                k=100,
                cutoff_days=365,
            )
            for memory in memories:
                payload = event_payload(memory.get("content"))
                if payload is None or payload.get("customer_key") != customer.key:
                    continue
                evidence_id = memory.get("id")
                if isinstance(evidence_id, str) and evidence_id:
                    self._apply_fact(payload, evidence_id)
                else:
                    fallback_id = f"content:{customer.key}:{payload.get('invoice_number')}"
                    self._apply_fact(payload, fallback_id)

            reflection = await self.memory_store.reflect(
                bank_name=self.bank_name,
                customer_id=customer.key,
                query=(
                    "Summarize only observed payment-run dates and invoice holds "
                    "for this customer, citing retained evidence."
                ),
            )
            if not isinstance(reflection, dict):
                raise HindsightUnavailableError(
                    f"Hindsight returned invalid reflection for customer {customer.key}"
                )
            if not self.memory_store.is_available:
                raise HindsightUnavailableError(
                    "Hindsight became unavailable during reflection"
                )
            self._apply_evidenced_reflection(customer.key, reflection)

    def _apply_evidenced_reflection(
        self,
        customer_key: str,
        reflection: dict[str, Any],
    ) -> None:
        """Accept reflected requirements only when they cite recalled facts."""
        recalled_evidence = self.memory_evidence.get(customer_key, set())
        for requirement in reflection.get("requirements", []):
            if hasattr(requirement, "model_dump"):
                requirement = requirement.model_dump()
            if not isinstance(requirement, dict):
                continue
            evidence_ids = set(requirement.get("evidence_ids", []))
            if not evidence_ids.intersection(recalled_evidence):
                continue
            self.reflected_requirement_count += 1
            self.memory_evidence.setdefault(customer_key, set()).update(evidence_ids)

    def _apply_fact(self, payload: dict[str, Any], evidence_id: str) -> None:
        customer_key = str(payload["customer_key"])
        fact_type = payload.get("fact_type")
        value = payload.get("value")
        if fact_type == "required_document" and isinstance(value, str):
            self.known_documents.setdefault(customer_key, set()).add(value)
        elif fact_type == "po_required" and value is True:
            self.known_po_required[customer_key] = True
        elif fact_type == "payment_run_day" and isinstance(value, int) and 1 <= value <= 28:
            self.known_payment_run_days.setdefault(customer_key, set()).add(value)
        else:
            return
        self.memory_evidence.setdefault(customer_key, set()).add(evidence_id)

    def _warning_date(self, invoice):
        days = self.known_payment_run_days.get(invoice.customer_key, set())
        if not days:
            return None
        predicted_run = _next_run_after(invoice.due_date, days)
        return max(invoice.issue_date, predicted_run - timedelta(days=2))

    def knowledge_snapshot(
        self,
        customers: list[EvaluationCustomer],
        month: int,
    ) -> dict[str, Any]:
        snapshot = super().knowledge_snapshot(customers, month)
        snapshot["evidence_count"] = sum(
            len(evidence) for evidence in self.memory_evidence.values()
        )
        snapshot["customers_with_memory"] = sum(
            bool(self.memory_evidence.get(customer.key)) for customer in customers
        )
        snapshot["reflected_requirement_count"] = self.reflected_requirement_count
        return snapshot


def _next_run_after(due_date: date, run_days: set[int]) -> date:
    current = date(due_date.year, due_date.month, 1)
    for _ in range(24):
        for day in sorted(run_days):
            candidate = date(current.year, current.month, day)
            if candidate >= due_date:
                return candidate
        month_index = current.year * 12 + current.month
        year, month = divmod(month_index, 12)
        current = date(year, month + 1, 1)
    raise ValueError("learned payment run does not occur within two years")
