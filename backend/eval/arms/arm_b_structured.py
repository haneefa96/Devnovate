"""Arm B: structured customer columns, with no Hindsight access."""

from __future__ import annotations

from sim.world import SimulationWorld

from .common import EvaluationArm, EvaluationCustomer


class ArmBPolicy(EvaluationArm):
    """Uses only documented customer columns available in structured storage."""

    arm = "B"
    name = "Structured database memory"

    @classmethod
    def from_world(cls, world: SimulationWorld) -> "ArmBPolicy":
        """Create a policy from the structured customer records."""
        policy = cls()
        policy.initialize(
            [
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
        )
        return policy

    def initialize(self, customers: list[EvaluationCustomer]) -> None:
        for customer in customers:
            self.known_documents[customer.key] = set(customer.required_docs)
            self.known_po_required[customer.key] = customer.po_required

