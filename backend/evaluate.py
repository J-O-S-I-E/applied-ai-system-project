#!/usr/bin/env python3
"""
evaluate.py -- PawPal+ AI Evaluation Test Harness

Runs a battery of test scenarios against the scheduler and AI guardrail
layer to verify correctness, consistency, and RAG retrieval.

Usage (from the project root):
    python backend/evaluate.py
"""

import sys
import io
import os
from pathlib import Path

# Allow direct execution: python backend/evaluate.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force UTF-8 output so emoji render correctly on all platforms.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Load .env so GEMINI_API_KEY is available for RAG tests
from dotenv import load_dotenv
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / "backend" / ".env")
load_dotenv(_root / ".env")

from datetime import datetime

from backend.pawpal_system import Owner, Pet, Task, Scheduler, Priority, Species
from backend.services.evaluator import evaluate_schedule
from backend.services.rag import retrieve_for_pet


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _make_owner(name: str, start: str = "08:00", end: str = "17:00") -> Owner:
    return Owner(name=name, available_start=start, available_end=end)


def _run(label: str, owner: Owner, expect_pass: bool) -> bool:
    """Build a schedule, validate it, print a summary row."""
    scheduler = Scheduler(owner)
    result = scheduler.build_schedule()
    v = evaluate_schedule(result, owner)

    print(f"\n{'─'*52}")
    print(f"Test  : {label}")
    print(f"Sched : {len(result.scheduled)} tasks  |  Skipped: {len(result.skipped)}  |  Conflicts: {len(result.conflicts)}")
    print(f"Score : {v['score']}/100  |  Passed: {v['passed']}")
    for issue in v["issues"]:
        print(f"  ISSUE   → {issue}")
    for warn in v["warnings"]:
        print(f"  WARNING → {warn}")

    matched = v["passed"] == expect_pass
    print(f"Result: {'✅ PASS' if matched else '❌ FAIL'}  (expected pass={expect_pass})")
    return matched


# ─────────────────────────────────────────────
# Test cases
# ─────────────────────────────────────────────

def test_normal_day() -> bool:
    """Case 1: Balanced day — all tasks should fit, no issues."""
    owner = _make_owner("Alex", start="08:00", end="20:00")
    dog = Pet("Buddy", Species.DOG, age_years=3.0)
    dog.add_task(Task("Morning walk",  30, Priority.HIGH,   preferred_time="morning"))
    dog.add_task(Task("Feeding",       15, Priority.HIGH,   preferred_time="morning"))
    dog.add_task(Task("Playtime",      20, Priority.MEDIUM))
    dog.add_task(Task("Evening walk",  30, Priority.HIGH,   preferred_time="evening"))
    owner.add_pet(dog)
    return _run("Normal Day", owner, expect_pass=True)


def test_overloaded_day() -> bool:
    """Case 2: Window too short — some HIGH tasks must be skipped → fail."""
    owner = _make_owner("Sam", start="09:00", end="09:30")  # 30-min window
    cat = Pet("Mochi", Species.CAT, age_years=2.0)
    cat.add_task(Task("Feeding",    15, Priority.HIGH))
    cat.add_task(Task("Medication", 10, Priority.HIGH))
    cat.add_task(Task("Grooming",   20, Priority.HIGH))   # will overflow
    owner.add_pet(cat)
    return _run("Overloaded Day (expect fail)", owner, expect_pass=False)


def test_conflicting_preferences() -> bool:
    """Case 3: Tasks with same preferred_time; greedy scheduler resolves cleanly."""
    owner = _make_owner("Riley")
    dog = Pet("Max", Species.DOG, age_years=5.0)
    dog.add_task(Task("Walk",     30, Priority.HIGH,   preferred_time="morning"))
    dog.add_task(Task("Feeding",  15, Priority.HIGH,   preferred_time="morning"))
    dog.add_task(Task("Training", 20, Priority.MEDIUM, preferred_time="morning"))
    owner.add_pet(dog)
    return _run("Conflicting Time Preferences (expect pass)", owner, expect_pass=True)


def test_empty_schedule() -> bool:
    """Case 4: No tasks at all — trivially valid."""
    owner = _make_owner("Jordan")
    owner.add_pet(Pet("Rex", Species.DOG, age_years=4.0))
    return _run("Empty Schedule (expect pass)", owner, expect_pass=True)


def test_low_utilization_warning() -> bool:
    """Case 5: One tiny task in a long window — warning but still passes."""
    owner = _make_owner("Dana", start="08:00", end="20:00")
    dog = Pet("Spot", Species.DOG, age_years=2.0)
    dog.add_task(Task("Quick feed", 10, Priority.HIGH))
    owner.add_pet(dog)
    return _run("Low Utilization Warning (expect pass)", owner, expect_pass=True)


def test_consistency() -> bool:
    """Case 6: Identical inputs must produce identical outputs (determinism)."""
    def _fresh_owner() -> Owner:
        o = _make_owner("Casey")
        d = Pet("Luna", Species.DOG, age_years=2.0)
        d.add_task(Task("Walk",    30, Priority.HIGH,   preferred_time="morning"))
        d.add_task(Task("Feeding", 15, Priority.HIGH))
        d.add_task(Task("Play",    20, Priority.LOW))
        o.add_pet(d)
        return o

    fixed_date = datetime(2026, 4, 26)
    r1 = Scheduler(_fresh_owner()).build_schedule(fixed_date)
    r2 = Scheduler(_fresh_owner()).build_schedule(fixed_date)

    titles_match = [t.title for t in r1.scheduled] == [t.title for t in r2.scheduled]
    times_match  = [t.scheduled_start for t in r1.scheduled] == [t.scheduled_start for t in r2.scheduled]
    consistent   = titles_match and times_match

    print(f"\n{'─'*52}")
    print("Test  : Consistency (determinism)")
    print(f"  Run 1 → {[t.title for t in r1.scheduled]}")
    print(f"  Run 2 → {[t.title for t in r2.scheduled]}")
    print(f"Result: {'✅ PASS' if consistent else '❌ FAIL'}  (consistent={consistent})")
    return consistent


def test_rag_retrieval() -> bool:
    """Case 7: RAG must return at least one chunk for walk + feeding tasks.
    Skipped automatically if no PDFs are present or GEMINI_API_KEY is unset."""
    data_dir = Path(__file__).parent / "data"
    if not list(data_dir.glob("*.pdf")):
        print(f"\n{'─'*52}")
        print("Test  : RAG Knowledge Retrieval")
        print("  SKIP — no PDF files found in backend/data/")
        print("Result: ✅ PASS (skipped — no PDFs present)")
        return True
    if not os.environ.get("GEMINI_API_KEY"):
        print(f"\n{'─'*52}")
        print("Test  : RAG Knowledge Retrieval")
        print("  SKIP — GEMINI_API_KEY not set (needed to build embeddings)")
        print("Result: ✅ PASS (skipped — no API key)")
        return True

    owner = _make_owner("Morgan")
    dog = Pet("Biscuit", Species.DOG, age_years=3.0)
    dog.add_task(Task("Morning walk", 30, Priority.HIGH))
    dog.add_task(Task("Feeding",      15, Priority.HIGH))
    owner.add_pet(dog)

    passages = retrieve_for_pet(dog, dog.tasks)
    ok       = bool(passages)

    print(f"\n{'─'*52}")
    print("Test  : RAG Knowledge Retrieval")
    print(f"  Retrieved: {'Yes' if ok else 'No'} ({len(passages)} passages)")
    for p in passages:
        print(f"  → {p[:120]}{'...' if len(p) > 120 else ''}")
    print(f"Result: {'✅ PASS' if ok else '❌ FAIL'}")
    return ok


def test_multi_pet() -> bool:
    """Case 8: Multiple pets — all HIGH tasks across pets should be scheduled."""
    owner = _make_owner("Pat", start="07:00", end="19:00")
    dog = Pet("Buddy", Species.DOG, age_years=2.0)
    dog.add_task(Task("Walk",    30, Priority.HIGH))
    dog.add_task(Task("Feeding", 15, Priority.HIGH))
    cat = Pet("Mochi", Species.CAT, age_years=3.0)
    cat.add_task(Task("Cat feeding",  10, Priority.HIGH))
    cat.add_task(Task("Medication",   5,  Priority.HIGH))
    owner.add_pet(dog)
    owner.add_pet(cat)
    return _run("Multi-Pet (expect pass)", owner, expect_pass=True)


# ─────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🐾 PawPal+ AI — Evaluation Test Harness")
    print("=" * 52)

    suite = [
        test_normal_day,
        test_overloaded_day,
        test_conflicting_preferences,
        test_empty_schedule,
        test_low_utilization_warning,
        test_consistency,
        test_rag_retrieval,
        test_multi_pet,
    ]

    results = [fn() for fn in suite]
    passed  = sum(results)
    total   = len(results)

    print(f"\n{'='*52}")
    print(f"FINAL: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        failed = [suite[i].__name__ for i, ok in enumerate(results) if not ok]
        print(f"⚠️  Failed: {', '.join(failed)}")
        sys.exit(1)
