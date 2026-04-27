"""
schemas.py
Pydantic request/response models for the PawPal+ FastAPI backend.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


# ── Inbound (React → API) ───────────────────────────────────────────────────

class TaskIn(BaseModel):
    task_id: Optional[str] = None
    title: str
    duration_minutes: int
    priority: str          # "HIGH" | "MEDIUM" | "LOW"
    preferred_time: Optional[str] = None
    recurring: bool = False
    notes: str = ""
    completed: bool = False


class PetIn(BaseModel):
    name: str
    species: str           # "dog" | "cat" | "other"
    age_years: float = 0.0
    tasks: list[TaskIn] = []


class OwnerIn(BaseModel):
    name: str
    available_start: str = "08:00"
    available_end: str = "20:00"


class ScheduleRequest(BaseModel):
    owner: OwnerIn
    pets: list[PetIn]


# ── Outbound (API → React) ──────────────────────────────────────────────────

class TaskOut(BaseModel):
    task_id: str
    title: str
    duration_minutes: int
    priority: str
    preferred_time: Optional[str]
    recurring: bool
    notes: str
    completed: bool
    scheduled_start: Optional[str]   # "09:00 AM"
    scheduled_end: Optional[str]     # "09:30 AM"


class ValidationOut(BaseModel):
    passed: bool
    issues: list[str]
    warnings: list[str]
    score: int


class AIOut(BaseModel):
    reasoning: str
    explanation: str
    recommendations: list[str]
    error: Optional[str] = None


class PassageOut(BaseModel):
    text: str
    source: Optional[str] = None


class PetGuidelinesOut(BaseModel):
    pet_name: str
    species: str
    age_years: float
    passages: list[PassageOut]


class ScheduleResponse(BaseModel):
    scheduled: list[TaskOut]
    skipped: list[TaskOut]
    conflicts: list[str]
    total_minutes: int
    available_minutes: int
    utilization_pct: float
    validation: Optional[ValidationOut] = None
    ai: Optional[AIOut] = None
    pet_guidelines: list[PetGuidelinesOut] = []
