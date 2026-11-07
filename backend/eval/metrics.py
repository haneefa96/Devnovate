"""Transparent aggregation of evaluation metrics and missing-data counts."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any


def compute_metrics(arm_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate run-level observations without imputing missing outcomes.

    ``arm_results`` contains one seed result per run. A missing measure remains
    ``None`` and its missing count is reported instead of being treated as zero.
    """
    invoices = [
        row
        for result in arm_results
        if result.get("status", "complete") == "complete"
        for row in result.get("invoice_results", [])
    ]

    days_late_by_month: dict[int, list[int]] = defaultdict(list)
    warning_lead_by_month: dict[int, list[int]] = defaultdict(list)
    blocker_total = 0
    blocker_caught = 0
    non_blocker_total = 0
    blocker_false_positives = 0
    missing_payment = 0
    missing_warning = 0

    for row in invoices:
        month = int(row["month"])
        days_late = row.get("days_late")
        if days_late is None:
            missing_payment += 1
        else:
            days_late_by_month[month].append(int(days_late))

        lead = row.get("warning_lead_days")
        if lead is None:
            missing_warning += 1
        else:
            warning_lead_by_month[month].append(int(lead))

        if row.get("actual_blocker"):
            blocker_total += 1
            blocker_caught += int(bool(row.get("blocker_caught")))
        else:
            non_blocker_total += 1
            blocker_false_positives += int(bool(row.get("blocker_false_positive")))

    month_indexes = sorted({int(row["month"]) for row in invoices})
    avg_late = {
        str(month): _average_or_none(days_late_by_month[month])
        for month in month_indexes
    }
    late_counts = {
        str(month): len(days_late_by_month[month])
        for month in month_indexes
    }
    avg_warning_lead = {
        str(month): _average_or_none(warning_lead_by_month[month])
        for month in month_indexes
    }
    warning_counts = {
        str(month): len(warning_lead_by_month[month])
        for month in month_indexes
    }

    learning = _aggregate_learning_curve(arm_results)
    memory_evidence_count = sum(
        int(result.get("memory_evidence_count", 0))
        for result in arm_results
        if result.get("status", "complete") == "complete"
    )
    memory_missing_customers = sum(
        int(result.get("memory_customers_missing_evidence", 0))
        for result in arm_results
        if result.get("status", "complete") == "complete"
    )
    all_days_late = [int(row["days_late"]) for row in invoices if row.get("days_late") is not None]
    all_warning_leads = [
        int(row["warning_lead_days"])
        for row in invoices
        if row.get("warning_lead_days") is not None
    ]
    return {
        "average_days_late": _average_or_none(all_days_late),
        "average_days_late_sample_count": len(all_days_late),
        "avg_days_late_by_month": avg_late,
        "days_late_sample_count_by_month": late_counts,
        "early_warning_lead_time": _average_or_none(all_warning_leads),
        "early_warning_sample_count": len(all_warning_leads),
        "early_warning_missing_count": missing_warning,
        "early_warning_lead_time_by_month": avg_warning_lead,
        "early_warning_sample_count_by_month": warning_counts,
        "blocker_catch_rate": blocker_caught / blocker_total if blocker_total else None,
        "blockers_caught": blocker_caught,
        "blocker_cases": blocker_total,
        "blocker_false_positives": blocker_false_positives,
        "non_blocker_cases": non_blocker_total,
        "blocker_false_positive_rate": (
            blocker_false_positives / non_blocker_total
            if non_blocker_total
            else None
        ),
        "learning_curve": learning,
        "invoice_count": len(invoices),
        "missing_payment_outcome_count": missing_payment,
        "missing_data_count": missing_payment + missing_warning,
        "memory_evidence_count": memory_evidence_count,
        "memory_customers_missing_evidence": memory_missing_customers,
    }


def _average_or_none(values: list[int]) -> float | None:
    return round(mean(values), 4) if values else None


def _aggregate_learning_curve(arm_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    months: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for result in arm_results:
        if result.get("status", "complete") != "complete":
            continue
        for row in result.get("learning_curve", []):
            months[int(row["month"])].append(row)

    output = []
    for month in sorted(months):
        samples = months[month]
        known = sum(int(row.get("known_facts", 0)) for row in samples)
        total = sum(int(row.get("total_facts", 0)) for row in samples)
        output.append(
            {
                "month": month,
                "known_facts": known,
                "total_facts": total,
                "coverage": round(known / total, 4) if total else None,
                "seed_count": len(samples),
            }
        )
    return output
