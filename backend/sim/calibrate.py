"""Reproducible simulation and evaluation defaults."""

from __future__ import annotations

from typing import Any


def calibrate_world() -> dict[str, Any]:
    """Return documented six-month, three-seed evaluation parameters."""
    return {
        "months_of_learning": 3,
        "months_of_testing": 3,
        "customers_per_seed": 6,
        "available_customers": 12,
        "full_evaluation_customers": 12,
        "seeds": [1, 2, 3],
        "start_date": "2026-01-01",
        "invoice_cycles": {
            "average_amount_paise": 4_820_000,
            "credit_days_range": [30, 60],
            "invoices_per_customer_per_month": 1,
        },
    }

