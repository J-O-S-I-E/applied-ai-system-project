"""
pawpal_system.py
Core logic layer for PawPal+.
All backend classes live here. This file is UI-agnostic.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import uuid


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class Priority(Enum):
    """Task urgency level used to determine scheduling order."""
    LOW    = 1
    MEDIUM = 2
    HIGH   = 3

    @classmethod
    def from_str(cls, s: str) -> "Priority":
        """Convert a plain string like 'high' to Priority.HIGH."""
        return cls[s.upper()]


class Species(Enum):
    """Supported pet species."""
    DOG   = "dog"
    CAT   = "cat"


# ─────────────────────────────────────────────
# Task
# ─────────────────────────────────────────────

@dataclass
class Task:
    """
    A single care activity for a pet.

    Attributes
    ----------
    title             : Human-readable name, e.g. "Morning walk".
    duration_minutes  : How long the task takes.
    priority          : LOW / MEDIUM / HIGH — drives scheduling order.
    preferred_time    : Optional hint: "morning", "afternoon", or "evening".
    recurring         : If True, completing the task auto-creates the next one.
    notes             : Free-text details, e.g. "Give with food".
    task_id           : Auto-generated unique ID (used for removal).
    completed         : Whether the task has been done today.
    scheduled_start   : Set by the Scheduler once a time slot is assigned.
    """
    title: str
    duration_minutes: int
    priority: Priority
    preferred_time: Optional[str] = None
    recurring: bool = False
    notes: str = ""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    completed: bool = False
    scheduled_start: Optional[datetime] = field(default=None, repr=False)

    @property
    def scheduled_end(self) -> Optional[datetime]:
        """Return the end time once scheduled_start has been set."""
        if self.scheduled_start:
            return self.scheduled_start + timedelta(minutes=self.duration_minutes)
        return None

    def mark_done(self) -> Optional["Task"]:
        """
        Mark this task complete.

        If the task is recurring, returns a new Task cloned for the
        next day (scheduled_start + 1 day via timedelta). Otherwise
        returns None.
        """
        self.completed = True
        if self.recurring and self.scheduled_start:
            next_start = self.scheduled_start + timedelta(days=1)
            clone = Task(
                title=self.title,
                duration_minutes=self.duration_minutes,
                priority=self.priority,
                preferred_time=self.preferred_time,
                recurring=True,
                notes=self.notes,
            )
            clone.scheduled_start = next_start
            return clone
        return None

    def summary(self) -> str:
        """Return a formatted one-line string for terminal or UI display."""
        time_str = (
            self.scheduled_start.strftime("%I:%M %p")
            if self.scheduled_start else "unscheduled"
        )
        return (
            f"[{self.priority.name:<6}] {self.title:<25} "
            f"({self.duration_minutes} min) @ {time_str}"
        )


# ─────────────────────────────────────────────
# Pet
# ─────────────────────────────────────────────

@dataclass
class Pet:
    """
    Represents one of the owner's pets.

    Owns a list of Task objects and provides filtered views of them.
    Does not know anything about scheduling — that belongs to Scheduler.
    """
    name: str
    species: Species
    age_years: float = 0.0
    notes: str = ""
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Append a new Task to this pet's task list."""
        self.tasks.append(task)

    def remove_task(self, task_id: str) -> bool:
        """Remove a task by its unique ID. Returns True if removed."""
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.task_id != task_id]
        return len(self.tasks) < before

    def pending_tasks(self) -> list[Task]:
        """Return all tasks that have not yet been marked complete."""
        return [t for t in self.tasks if not t.completed]

    def high_priority_tasks(self) -> list[Task]:
        """Return only HIGH-priority tasks that are not yet complete."""
        return [t for t in self.pending_tasks() if t.priority == Priority.HIGH]


# ─────────────────────────────────────────────
# Owner
# ─────────────────────────────────────────────

@dataclass
class Owner:
    """
    Represents the person using PawPal+.

    Owns a list of Pet objects and knows the daily window during which
    care tasks can be scheduled.
    """
    name: str
    available_start: str = "08:00"
    available_end: str = "20:00"
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Register a new pet with this owner."""
        self.pets.append(pet)

    def remove_pet(self, pet_name: str) -> bool:
        """Remove a pet by name (case-insensitive). Returns True if removed."""
        before = len(self.pets)
        self.pets = [p for p in self.pets if p.name.lower() != pet_name.lower()]
        return len(self.pets) < before

    def all_pending_tasks(self) -> list[Task]:
        """Aggregate pending tasks across ALL pets into one flat list."""
        return [task for pet in self.pets for task in pet.pending_tasks()]

    @property
    def available_minutes(self) -> int:
        """Total minutes between available_start and available_end."""
        fmt   = "%H:%M"
        start = datetime.strptime(self.available_start, fmt)
        end   = datetime.strptime(self.available_end,   fmt)
        return int((end - start).total_seconds() // 60)


# ─────────────────────────────────────────────
# ScheduleResult
# ─────────────────────────────────────────────

@dataclass
class ScheduleResult:
    """The output produced by Scheduler.build_schedule()."""
    scheduled: list[Task]
    skipped: list[Task]
    conflicts: list[str]
    total_minutes: int
    available_minutes: int

    @property
    def utilization_pct(self) -> float:
        """Percentage of the available window filled by scheduled tasks."""
        if self.available_minutes == 0:
            return 0.0
        return round(self.total_minutes / self.available_minutes * 100, 1)


# ─────────────────────────────────────────────
# Scheduler
# ─────────────────────────────────────────────

_TIME_SLOTS: dict[str, tuple[int, int]] = {
    "morning":   (6,  12),
    "afternoon": (12, 17),
    "evening":   (17, 21),
}


class Scheduler:
    """
    The scheduling brain of PawPal+.

    Algorithm
    ---------
    1. Collect all pending tasks from the Owner's pets.
    2. Sort them: HIGH → MEDIUM → LOW; ties broken by shortest duration first.
    3. Assign time slots greedily, respecting preferred_time hints.
    4. Skip any task that would overflow the owner's available window.
    5. Detect overlapping durations and surface them as warning strings.
    """

    def __init__(self, owner: Owner) -> None:
        self.owner = owner

    def build_schedule(self, date: Optional[datetime] = None) -> ScheduleResult:
        """Build and return a ScheduleResult for the given date."""
        date = date or datetime.today().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        tasks              = self.owner.all_pending_tasks()
        sorted_tasks       = self._sort_tasks(tasks)
        scheduled, skipped = self._assign_times(sorted_tasks, date)
        conflicts          = self._detect_conflicts(scheduled)
        total              = sum(t.duration_minutes for t in scheduled)

        return ScheduleResult(
            scheduled=scheduled,
            skipped=skipped,
            conflicts=conflicts,
            total_minutes=total,
            available_minutes=self.owner.available_minutes,
        )

    @staticmethod
    def sort_by_priority(tasks: list[Task]) -> list[Task]:
        return sorted(tasks, key=lambda t: (-t.priority.value, t.duration_minutes))

    @staticmethod
    def sort_by_time(tasks: list[Task]) -> list[Task]:
        return sorted(tasks, key=lambda t: t.scheduled_start or datetime.max)

    @staticmethod
    def filter_by_status(tasks: list[Task], completed: bool) -> list[Task]:
        return [t for t in tasks if t.completed == completed]

    @staticmethod
    def filter_by_pet(owner: Owner, pet_name: str) -> list[Task]:
        for pet in owner.pets:
            if pet.name.lower() == pet_name.lower():
                return pet.pending_tasks()
        return []

    @staticmethod
    def complete_and_recur(task: Task, pet: Pet) -> Optional[Task]:
        """Mark a task done and add the next-day clone to the pet if recurring."""
        next_task = task.mark_done()
        if next_task:
            pet.add_task(next_task)
        return next_task

    @staticmethod
    def _sort_tasks(tasks: list[Task]) -> list[Task]:
        return sorted(tasks, key=lambda t: (-t.priority.value, t.duration_minutes))

    def _assign_times(
        self, tasks: list[Task], date: datetime
    ) -> tuple[list[Task], list[Task]]:
        fmt       = "%H:%M"
        day_start = datetime.combine(
            date.date(),
            datetime.strptime(self.owner.available_start, fmt).time()
        )
        day_end = datetime.combine(
            date.date(),
            datetime.strptime(self.owner.available_end, fmt).time()
        )

        scheduled: list[Task] = []
        skipped:   list[Task] = []
        cursor = day_start

        for task in tasks:
            ideal_start = self._preferred_start(task, date)
            start = max(cursor, ideal_start) if ideal_start else cursor
            end   = start + timedelta(minutes=task.duration_minutes)

            if end > day_end:
                skipped.append(task)
                continue

            task.scheduled_start = start
            scheduled.append(task)
            cursor = end

        return scheduled, skipped

    def _preferred_start(self, task: Task, date: datetime) -> Optional[datetime]:
        if not task.preferred_time:
            return None
        slot = _TIME_SLOTS.get(task.preferred_time.lower())
        if not slot:
            return None
        return datetime.combine(
            date.date(),
            datetime.min.time().replace(hour=slot[0])
        )

    @staticmethod
    def _detect_conflicts(tasks: list[Task]) -> list[str]:
        conflicts = []
        for i, a in enumerate(tasks):
            for b in tasks[i + 1:]:
                if (
                    a.scheduled_start and a.scheduled_end
                    and b.scheduled_start and b.scheduled_end
                    and a.scheduled_start < b.scheduled_end
                    and b.scheduled_start < a.scheduled_end
                ):
                    conflicts.append(f"Overlap: '{a.title}' and '{b.title}'")
        return conflicts

    @staticmethod
    def explain(result: ScheduleResult) -> str:
        """Produce a plain-text schedule summary."""
        lines = ["Daily Schedule", "=" * 40]
        for t in result.scheduled:
            lines.append(t.summary())
        if result.skipped:
            lines.append("\nSkipped (didn't fit):")
            for t in result.skipped:
                lines.append(f"  - {t.title} ({t.duration_minutes} min, {t.priority.name})")
        if result.conflicts:
            lines.append("")
            lines.extend(result.conflicts)
        lines.append(
            f"\n{result.total_minutes} / {result.available_minutes} min used "
            f"({result.utilization_pct}%)"
        )
        return "\n".join(lines)
