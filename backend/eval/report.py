"""Evaluation report generation with explicit provenance and failures."""

from __future__ import annotations

from typing import Any

from .metrics import compute_metrics

_METRIC_DIRECTIONS = {
    "average_days_late": "lower",
    "early_warning_lead_time": "higher",
    "blocker_catch_rate": "higher",
}


def generate_report(evaluation_results: dict[str, Any]) -> dict[str, Any]:
    """Create a report without hiding failed arms or missing measurements."""
    raw_arms = evaluation_results.get("arms", {})
    arm_reports: dict[str, Any] = {}
    for arm, runs in raw_arms.items():
        if not isinstance(runs, dict):
            runs = {}
        run_values = list(runs.values())
        metrics = evaluation_results.get("metrics", {}).get(arm)
        if metrics is None:
            metrics = compute_metrics(run_values)
        arm_reports[arm] = {
            "name": _arm_name(arm, run_values),
            "status": _arm_status(run_values),
            "metrics": metrics,
            "runs": runs,
            "failures": [
                {
                    "seed": result.get("seed"),
                    "error": result.get("error"),
                }
                for result in run_values
                if result.get("status") != "complete"
            ],
        }

    comparison = _compare_arms(arm_reports)
    return {
        "report_type": "simulated_evaluation",
        "simulation_only": True,
        "real_world_results": False,
        "run_id": evaluation_results.get("run_id"),
        "scenario": evaluation_results.get("scenario", "eval"),
        "source_fingerprint": evaluation_results.get("source_fingerprint"),
        "learning_months": evaluation_results.get("learning_months", 3),
        "testing_months": evaluation_results.get("testing_months", 3),
        "test_months": evaluation_results.get("test_months", [4, 5, 6]),
        "seeds": evaluation_results.get("seeds", [1, 2, 3]),
        "customers_per_seed": evaluation_results.get("customers_per_seed", 6),
        "arm_methodology": evaluation_results.get("arm_methodology", {}),
        "synthetic_blocker_case_generation": evaluation_results.get(
            "synthetic_blocker_case_generation",
            {},
        ),
        "arms": arm_reports,
        "metric_definitions": {
            "average_days_late": (
                "Mean max(0, simulated payment date - invoice due date), "
                "testing invoices only."
            ),
            "early_warning_lead_time": (
                "Mean actual payment-run date - warning date in days; "
                "negative values mean a late warning."
            ),
            "blocker_catch_rate": (
                "Detected actual blocker cases / all actual blocker cases; "
                "null when there are no blocker cases."
            ),
            "blocker_false_positive_rate": (
                "False blocker detections / non-blocker cases; reported to "
                "expose over-detection."
            ),
            "learning_curve": (
                "Known customer-specific profile facts / applicable facts, "
                "measured monthly during months 1-3."
            ),
        },
        "comparison": comparison,
        "conclusion": _conclusion(comparison),
        "git_hash": evaluation_results.get("git_hash", ""),
    }


def _arm_name(arm: str, runs: list[dict[str, Any]]) -> str:
    for result in runs:
        if result.get("arm_name"):
            return str(result["arm_name"])
    return {
        "A": "Fixed rules, no memory",
        "B": "Structured database memory",
        "C": "Hindsight customer memory",
    }.get(arm, arm)


def _arm_status(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "missing"
    completed = sum(result.get("status") == "complete" for result in runs)
    if completed == len(runs):
        return "complete"
    if completed:
        return "partial"
    return "failed"


def _compare_arms(arms: dict[str, Any]) -> dict[str, Any]:
    structured = arms.get("B", {}).get("metrics", {})
    hindsight = arms.get("C", {}).get("metrics", {})
    comparison: dict[str, Any] = {}
    for metric, direction in _METRIC_DIRECTIONS.items():
        b_value = structured.get(metric)
        c_value = hindsight.get(metric)
        available = (
            arms.get("B", {}).get("status") in {"complete", "partial"}
            and arms.get("C", {}).get("status") in {"complete", "partial"}
            and isinstance(b_value, (int, float))
            and isinstance(c_value, (int, float))
        )
        if not available:
            comparison[metric] = {
                "arm_b": b_value,
                "arm_c": c_value,
                "direction": direction,
                "winner": None,
                "comparable": False,
            }
            continue
        if c_value == b_value:
            winner = "tie"
        elif (c_value > b_value) == (direction == "higher"):
            winner = "C"
        else:
            winner = "B"
        comparison[metric] = {
            "arm_b": b_value,
            "arm_c": c_value,
            "direction": direction,
            "winner": winner,
            "comparable": True,
        }
    return comparison


def _conclusion(comparison: dict[str, Any]) -> str:
    comparable = [value for value in comparison.values() if value.get("comparable")]
    if not comparable:
        return "Insufficient comparable data; no performance conclusion can be drawn."
    wins = sum(value.get("winner") == "C" for value in comparable)
    if len(comparable) < len(_METRIC_DIRECTIONS):
        return (
            f"Partial comparison only: Arm C leads Arm B on {wins} of "
            f"{len(comparable)} comparable metrics; missing metrics are not imputed."
        )
    if wins >= 2:
        return f"Arm C leads Arm B on {wins} of 3 comparable metrics in this simulation."
    return f"Arm C leads Arm B on {wins} of 3 metrics; the documented target was not met."
