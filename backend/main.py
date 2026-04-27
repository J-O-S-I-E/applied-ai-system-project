"""
backend/main.py
FastAPI entry point for PawPal+ AI.

Run from the project root:
    uvicorn backend.main:app --reload
or:
    python run_api.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend/ then project root (whichever exists first wins).
load_dotenv(Path(__file__).parent / ".env")
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .pawpal_system import Owner, Pet, Task, Scheduler, Priority, Species
from .schemas import (
    ScheduleRequest,
    ScheduleResponse,
    TaskOut,
    ValidationOut,
    AIOut,
    PassageOut,
    PetGuidelinesOut,
)
from .services.evaluator import evaluate_schedule
from .services.rag import retrieve_for_pet
from .services.ai_agent import generate_ai_explanation

app = FastAPI(title="PawPal+ API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _build_owner(req: ScheduleRequest) -> Owner:
    """Reconstruct the domain Owner object from a ScheduleRequest."""
    owner = Owner(
        name=req.owner.name,
        available_start=req.owner.available_start,
        available_end=req.owner.available_end,
    )
    for pet_data in req.pets:
        pet = Pet(
            name=pet_data.name,
            species=Species(pet_data.species),
            age_years=pet_data.age_years,
        )
        for td in pet_data.tasks:
            if td.completed:
                continue
            task = Task(
                title=td.title,
                duration_minutes=td.duration_minutes,
                priority=Priority.from_str(td.priority),
                preferred_time=td.preferred_time or None,
                recurring=td.recurring,
                notes=td.notes,
                task_id=td.task_id or "",
            )
            pet.add_task(task)
        owner.add_pet(pet)
    return owner


def _serialize(task: Task) -> TaskOut:
    return TaskOut(
        task_id=task.task_id,
        title=task.title,
        duration_minutes=task.duration_minutes,
        priority=task.priority.name,
        preferred_time=task.preferred_time,
        recurring=task.recurring,
        notes=task.notes,
        completed=task.completed,
        scheduled_start=(
            task.scheduled_start.strftime("%I:%M %p") if task.scheduled_start else None
        ),
        scheduled_end=(
            task.scheduled_end.strftime("%I:%M %p") if task.scheduled_end else None
        ),
    )


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "gemini_configured": bool(os.environ.get("GEMINI_API_KEY"))}


@app.post("/api/schedule", response_model=ScheduleResponse)
def build_schedule(req: ScheduleRequest):
    """Build and return a schedule without AI analysis."""
    try:
        owner = _build_owner(req)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    result = Scheduler(owner).build_schedule()

    return ScheduleResponse(
        scheduled=[_serialize(t) for t in result.scheduled],
        skipped=[_serialize(t) for t in result.skipped],
        conflicts=result.conflicts,
        total_minutes=result.total_minutes,
        available_minutes=result.available_minutes,
        utilization_pct=result.utilization_pct,
    )


@app.post("/api/ai-schedule", response_model=ScheduleResponse)
def build_ai_schedule(req: ScheduleRequest):
    """Build schedule, then run per-pet RAG retrieval, guardrail evaluation, and Gemini AI."""
    try:
        owner = _build_owner(req)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    result = Scheduler(owner).build_schedule()

    # Per-pet RAG: retrieve passages scoped to each pet's species, age, and tasks
    pet_rag_contexts: dict[str, list[dict]] = {}
    pet_guidelines_out: list[PetGuidelinesOut] = []
    for pet in owner.pets:
        passages = retrieve_for_pet(pet, pet.tasks)
        pet_rag_contexts[pet.name] = passages
        if passages:
            pet_guidelines_out.append(PetGuidelinesOut(
                pet_name=pet.name,
                species=pet.species.value,
                age_years=pet.age_years,
                passages=[PassageOut(text=p["text"], source=p.get("source")) for p in passages],
            ))

    v_data = evaluate_schedule(result, owner)
    validation = ValidationOut(**v_data)

    ai_data = generate_ai_explanation(result, owner, pet_rag_contexts)
    ai = AIOut(
        reasoning=ai_data.get("reasoning", ""),
        explanation=ai_data.get("explanation", ""),
        recommendations=ai_data.get("recommendations", []),
        error=ai_data.get("error"),
    )

    return ScheduleResponse(
        scheduled=[_serialize(t) for t in result.scheduled],
        skipped=[_serialize(t) for t in result.skipped],
        conflicts=result.conflicts,
        total_minutes=result.total_minutes,
        available_minutes=result.available_minutes,
        utilization_pct=result.utilization_pct,
        validation=validation,
        ai=ai,
        pet_guidelines=pet_guidelines_out,
    )
