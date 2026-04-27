"""
evaluator.py
Rule-based guardrail layer for PawPal+ AI.

Validates a ScheduleResult against a set of correctness rules and
returns a structured report with a pass/fail flag and a 0-100 score.
"""

from ..pawpal_system import ScheduleResult, Owner, Priority


def evaluate_schedule(result: ScheduleResult, owner: Owner) -> dict:
    """
    Validate a ScheduleResult against safety and quality rules.

    Rules checked
    -------------
    1. All HIGH-priority tasks must be scheduled.
    2. No time conflicts in the output.
    3. Utilisation warning if >95% or <20% of the window is used.
    4. Any skipped HIGH-priority tasks are escalated to issues.

    Returns
    -------
    dict with keys:
      passed   (bool)   — True if no hard issues were found
      issues   (list)   — Blocking problems (each costs 20 points)
      warnings (list)   — Non-blocking notices (each costs 5 points)
      score    (int)    — 0-100 quality score
    """
    issues: list[str] = []
    warnings: list[str] = []

    for conflict in result.conflicts:
        issues.append(f"Time conflict: {conflict}")

    if result.utilization_pct > 95:
        warnings.append(
            f"Schedule is {result.utilization_pct}% full — "
            "no buffer for tasks that run over time."
        )
    elif result.scheduled and result.utilization_pct < 20:
        warnings.append(
            f"Only {result.utilization_pct}% of your window is used — "
            "consider adding more tasks or shortening your availability."
        )

    skipped_high = [t for t in result.skipped if t.priority == Priority.HIGH]
    if skipped_high:
        issues.append(
            f"{len(skipped_high)} HIGH priority task(s) could not fit: "
            + ", ".join(f"'{t.title}'" for t in skipped_high)
        )
    elif result.skipped:
        warnings.append(
            f"{len(result.skipped)} lower-priority task(s) skipped "
            "due to time constraints."
        )

    score = max(0, 100 - len(issues) * 20 - len(warnings) * 5)

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "score": score,
    }
