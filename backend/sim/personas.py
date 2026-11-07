"""Template-based, deterministic simulated customer responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CustomerPersona:
    """A rule-based persona; evaluation never calls an external language model."""

    name: str
    payment_behavior: str
    communication_style: str
    distress_indicators: tuple[str, ...]
    response_patterns: Mapping[str, str]

    def get_response(self, message: str, context: Mapping[str, object] | None = None) -> str:
        """Return a deterministic template selected from the message context."""
        normalized = message.casefold()
        if context:
            response_key = str(context.get("response_type", "")).casefold()
            if response_key in self.response_patterns:
                return self.response_patterns[response_key]
        for key in ("distress", "overdue", "promise", "payment", "reminder"):
            if key in normalized and key in self.response_patterns:
                return self.response_patterns[key]
        return self.response_patterns.get("default", "We will review this and update you.")


DEMO_PERSONAS: dict[str, CustomerPersona] = {
    "reddy-traders": CustomerPersona(
        name="Reddy Traders",
        payment_behavior="pays on the 5th and 20th",
        communication_style="polite but direct",
        distress_indicators=("cash-flow trouble", "delayed payments"),
        response_patterns={
            "reminder": "Payment run is on the 5th, will release with this batch.",
            "overdue": "We're checking the next payment run.",
            "payment": "Payment has been processed in the scheduled run.",
            "default": "Please share the invoice details and we will check.",
        },
    ),
    "sharma-suppliers": CustomerPersona(
        name="Sharma Suppliers",
        payment_behavior="pays on the 10th and 25th",
        communication_style="business-like",
        distress_indicators=(),
        response_patterns={
            "reminder": "We'll process it soon.",
            "overdue": "Processing is delayed.",
            "payment": "The payment is in process.",
            "default": "We will check with the accounts team.",
        },
    ),
    "patel-enterprises": CustomerPersona(
        name="Patel Enterprises",
        payment_behavior="pays on the 15th, often delayed",
        communication_style="reserved",
        distress_indicators=("cash-flow trouble", "will pay next month"),
        response_patterns={
            "reminder": "We'll try to expedite.",
            "overdue": "We're facing liquidity issues.",
            "distress": "We are facing cash-flow trouble and need more time.",
            "promise": "We expect to pay on the next payment run.",
            "default": "We will update you after checking internally.",
        },
    ),
    "gupta-electronics": CustomerPersona(
        name="Gupta Electronics",
        payment_behavior="pays on the 7th and 21st",
        communication_style="formal",
        distress_indicators=(),
        response_patterns={"reminder": "We will include this in our next payment run."},
    ),
    "sharma-traders": CustomerPersona(
        name="Sharma Traders",
        payment_behavior="pays on the 10th and 25th",
        communication_style="business-like",
        distress_indicators=(),
        response_patterns={"reminder": "We will process it soon."},
    ),
    "patel-suppliers": CustomerPersona(
        name="Patel Suppliers",
        payment_behavior="pays on the 15th, sometimes delayed",
        communication_style="reserved",
        distress_indicators=("cash-flow trouble",),
        response_patterns={"overdue": "Processing is delayed; we will update you."},
    ),
}

for _profile_key in (
    "reddy-components",
    "kumar-industries",
    "mehta-manufacturing",
    "iyer-distributors",
    "nair-components",
    "verma-industrial-supplies",
):
    DEMO_PERSONAS[_profile_key] = CustomerPersona(
        name=_profile_key.replace("-", " ").title(),
        payment_behavior="pays on documented monthly payment runs",
        communication_style="business-like",
        distress_indicators=(),
        response_patterns={
            "reminder": "We will review this for the next payment run.",
            "overdue": "The payment is delayed; we will provide an update.",
            "default": "We will check with our accounts team.",
        },
    )
