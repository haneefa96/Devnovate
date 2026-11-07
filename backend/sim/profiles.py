"""Deterministic customer profiles used by the Munshi simulator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CustomerProfile:
    """Simulation-only customer behavior and documented business requirements."""

    name: str
    payment_run_days: tuple[int, ...]
    po_required: bool
    required_docs: tuple[str, ...] = ()
    risk_level: str = "NORMAL"
    contact_name: str = "Contact"
    contact_role: str = "Accounts"
    distress_cues: tuple[str, ...] = ()
    payment_reliability_bps: int = 9_000
    typical_delay_days: int = 0
    credit_days: int = 30

    def __post_init__(self) -> None:
        if not self.payment_run_days or any(day < 1 or day > 28 for day in self.payment_run_days):
            raise ValueError("payment run days must be between 1 and 28")
        if not 0 <= self.payment_reliability_bps <= 10_000:
            raise ValueError("payment reliability must be between 0 and 10000 basis points")
        if self.typical_delay_days < 0 or self.credit_days < 0:
            raise ValueError("delay and credit days must be non-negative")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible view of the profile."""
        return {
            "name": self.name,
            "payment_run_days": list(self.payment_run_days),
            "po_required": self.po_required,
            "required_docs": list(self.required_docs),
            "risk_level": self.risk_level,
            "contact_name": self.contact_name,
            "contact_role": self.contact_role,
            "distress_cues": list(self.distress_cues),
            "payment_reliability_bps": self.payment_reliability_bps,
            "typical_delay_days": self.typical_delay_days,
            "credit_days": self.credit_days,
        }


CUSTOMER_PROFILES: dict[str, CustomerProfile] = {
    "reddy-traders": CustomerProfile(
        name="Reddy Traders",
        payment_run_days=(5, 20),
        po_required=True,
        required_docs=("SIGNED_CHALLAN",),
        contact_name="Priya",
        contact_role="Accounts",
        payment_reliability_bps=9_600,
    ),
    "sharma-suppliers": CustomerProfile(
        name="Sharma Suppliers",
        payment_run_days=(10, 25),
        po_required=False,
        risk_level="WATCH",
        contact_name="Amit",
        contact_role="Purchase",
        payment_reliability_bps=9_000,
        typical_delay_days=2,
        credit_days=45,
    ),
    "patel-enterprises": CustomerProfile(
        name="Patel Enterprises",
        payment_run_days=(15,),
        po_required=True,
        required_docs=("SIGNED_CHALLAN", "GRN"),
        risk_level="HIGH",
        contact_name="Suresh",
        contact_role="Owner",
        distress_cues=("cash-flow trouble", "delayed payments"),
        payment_reliability_bps=6_800,
        typical_delay_days=12,
        credit_days=60,
    ),
    "gupta-electronics": CustomerProfile(
        name="Gupta Electronics",
        payment_run_days=(7, 21),
        po_required=True,
        required_docs=("PO_COPY",),
        contact_name="Neha",
        contact_role="Accounts",
        payment_reliability_bps=8_800,
        typical_delay_days=3,
    ),
    "sharma-traders": CustomerProfile(
        name="Sharma Traders",
        payment_run_days=(10, 25),
        po_required=False,
        contact_name="Amit",
        contact_role="Accounts",
        payment_reliability_bps=9_200,
        typical_delay_days=1,
    ),
    "patel-suppliers": CustomerProfile(
        name="Patel Suppliers",
        payment_run_days=(15,),
        po_required=True,
        required_docs=("SIGNED_CHALLAN",),
        contact_name="Suresh",
        contact_role="Purchase",
        payment_reliability_bps=7_500,
        typical_delay_days=8,
        credit_days=45,
    ),
    "reddy-components": CustomerProfile(
        name="Reddy Components",
        payment_run_days=(5, 20),
        po_required=True,
        required_docs=("SIGNED_CHALLAN",),
        contact_name="Kiran",
        contact_role="Accounts",
        payment_reliability_bps=9_300,
    ),
    "kumar-industries": CustomerProfile(
        name="Kumar Industries",
        payment_run_days=(8, 22),
        po_required=True,
        required_docs=("PO_COPY", "GRN"),
        contact_name="Anil",
        contact_role="Purchase",
        payment_reliability_bps=8_500,
        typical_delay_days=4,
        credit_days=45,
    ),
    "mehta-manufacturing": CustomerProfile(
        name="Mehta Manufacturing",
        payment_run_days=(12, 26),
        po_required=False,
        contact_name="Ritu",
        contact_role="Accounts",
        payment_reliability_bps=9_500,
        credit_days=30,
    ),
    "iyer-distributors": CustomerProfile(
        name="Iyer Distributors",
        payment_run_days=(6, 20),
        po_required=True,
        required_docs=("EWAY_BILL",),
        contact_name="Vijay",
        contact_role="Owner",
        payment_reliability_bps=8_000,
        typical_delay_days=7,
        credit_days=45,
    ),
    "nair-components": CustomerProfile(
        name="Nair Components",
        payment_run_days=(14, 28),
        po_required=False,
        contact_name="Lakshmi",
        contact_role="Accounts",
        payment_reliability_bps=9_700,
    ),
    "verma-industrial-supplies": CustomerProfile(
        name="Verma Industrial Supplies",
        payment_run_days=(10, 24),
        po_required=True,
        required_docs=("SIGNED_CHALLAN", "GRN"),
        risk_level="WATCH",
        contact_name="Raj",
        contact_role="Purchase",
        distress_cues=("cash flow is tight",),
        payment_reliability_bps=7_800,
        typical_delay_days=9,
        credit_days=60,
    ),
}

# Keep the original three-name demo mapping available to existing callers.
DEMO_PROFILES = {key: CUSTOMER_PROFILES[key] for key in (
    "reddy-traders",
    "sharma-suppliers",
    "patel-enterprises",
)}
DEMO_CUSTOMER_KEYS = (
    "reddy-traders",
    "sharma-suppliers",
    "patel-enterprises",
    "gupta-electronics",
)
EVAL_CUSTOMER_KEYS = (
    "reddy-traders",
    "sharma-suppliers",
    "patel-enterprises",
    "gupta-electronics",
    "sharma-traders",
    "patel-suppliers",
)

