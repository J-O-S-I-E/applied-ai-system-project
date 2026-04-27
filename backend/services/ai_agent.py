"""
ai_agent.py
PawPal+ AI scheduling advisor — LangChain RAG chain with Gemini 2.0 Flash.
"""

import json
import os

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from ..pawpal_system import ScheduleResult, Owner

# ── Prompt template ────────────────────────────────────────────────────────────

_TEMPLATE = """\
You are PawPal+, a warm and knowledgeable pet care advisor who genuinely loves animals.
You help owners create the best possible daily care routine for their beloved pets.

Personality & Tone:
- Warm, encouraging, and genuinely fond of every pet mentioned by name.
- Clear and organized — owners should be able to scan your advice in seconds.
- Grounded in the care guide: every recommendation must come directly from the passages below.
- Never clinical or robotic — you speak like a knowledgeable friend, not a textbook.
- If the passages do not fully cover a task, acknowledge what the guide says and stay honest.

You MUST base your analysis ONLY on the care guide passages provided.
Do not invent medical advice, specific timings, or claims not found in the passages.

SCHEDULE & PET INFORMATION:
{schedule}

RELEVANT CARE GUIDE PASSAGES (sourced per pet from the Humane Fort Wayne Pet Care Guide):
{context}

Your task:
Analyze the schedule above and respond with a JSON object containing exactly these three keys:

"reasoning"       — 3-5 sentences explaining step-by-step why tasks were ordered and placed as they \
were. Reference each pet's name, species, age, priority levels, and any care guide guidance.
"explanation"     — A friendly 3-4 sentence plain-English summary the owner can read at a glance.
"recommendations" — A JSON array of 3-4 short, actionable tips drawn directly from the care guide \
passages above. Each tip should reference specific guidance from the passages.

Respond ONLY with valid JSON. No markdown fences, no extra text.
"""

_prompt = ChatPromptTemplate.from_template(_TEMPLATE)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_schedule_str(result: ScheduleResult, owner: Owner) -> str:
    """Format owner, pets, and scheduled/skipped tasks into a readable block."""
    pets_lines = "\n".join(
        f"  • {p.name} — {p.species.value.title()}, {p.age_years} yrs old"
        for p in owner.pets
    )

    scheduled_lines = "\n".join(
        "  {time} — {title} ({dur} min, {pri}){notes}".format(
            time=t.scheduled_start.strftime("%I:%M %p") if t.scheduled_start else "?",
            title=t.title,
            dur=t.duration_minutes,
            pri=t.priority.name,
            notes=f"  [Notes: {t.notes}]" if t.notes else "",
        )
        for t in result.scheduled
    ) or "  (none scheduled)"

    skipped_lines = "\n".join(
        f"  • {t.title} ({t.duration_minutes} min, {t.priority.name})"
        for t in result.skipped
    ) or "  (none skipped)"

    return (
        f"Owner: {owner.name}  |  Window: {owner.available_start} – {owner.available_end}\n\n"
        f"Pets:\n{pets_lines}\n\n"
        f"Scheduled tasks:\n{scheduled_lines}\n\n"
        f"Skipped tasks (did not fit):\n{skipped_lines}"
    )


def _build_context_str(pet_rag_contexts: dict[str, list[dict]], owner: Owner) -> str:
    """Format per-pet RAG passages (dicts with text + source) into a labeled context block."""
    if not pet_rag_contexts:
        return "(No care guide passages retrieved.)"

    sections: list[str] = []
    for pet in owner.pets:
        passages = pet_rag_contexts.get(pet.name, [])
        if not passages:
            continue
        header = f"[ {pet.name} — {pet.species.value.title()}, {pet.age_years} yrs ]"
        lines = [
            f"  • {p['text']}{' (' + p['source'] + ')' if p.get('source') else ''}"
            for p in passages
        ]
        sections.append(f"{header}\n" + "\n".join(lines))

    return "\n\n".join(sections) if sections else "(No care guide passages retrieved.)"


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_ai_explanation(
    result: ScheduleResult,
    owner: Owner,
    pet_rag_contexts: dict[str, list[dict]],
) -> dict:
    """
    Run the PawPal+ RAG chain and return structured AI analysis.

    Parameters
    ----------
    result           : ScheduleResult from Scheduler.build_schedule()
    owner            : Owner whose pets and window were used
    pet_rag_contexts : {pet_name: [passage, ...]} pre-retrieved per pet

    Returns
    -------
    dict with keys: reasoning, explanation, recommendations, error
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {
            "reasoning": "",
            "explanation": "",
            "recommendations": [],
            "error": "GEMINI_API_KEY environment variable is not set.",
        }

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
    )

    chain = _prompt | llm | StrOutputParser()

    try:
        raw = chain.invoke({
            "schedule": _build_schedule_str(result, owner),
            "context": _build_context_str(pet_rag_contexts, owner),
        })

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)
        return {
            "reasoning": data.get("reasoning", ""),
            "explanation": data.get("explanation", ""),
            "recommendations": data.get("recommendations", []),
            "error": None,
        }

    except json.JSONDecodeError:
        return {
            "reasoning": raw if "raw" in dir() else "",
            "explanation": "AI analysis complete (raw response shown above).",
            "recommendations": [],
            "error": None,
        }
    except Exception as exc:
        return {
            "reasoning": "",
            "explanation": "",
            "recommendations": [],
            "error": str(exc),
        }
