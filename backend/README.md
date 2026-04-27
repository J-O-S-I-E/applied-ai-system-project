# PawPal+ — Backend

FastAPI server that exposes the scheduling engine and AI layer as a REST API consumed by the React frontend.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI |
| Server | Uvicorn |
| Core scheduling | `pawpal_system.py` (pure Python) |
| AI agent | Google Gemini 2.0 Flash (`google-genai`) |
| RAG | Local JSON knowledge base + keyword retrieval |
| Guardrails | Rule-based evaluator |
| Validation | Pydantic v2 |

---

## Installation

From the **project root**:

```bash
# 1. Create a virtual environment
python -m venv venv

# 2. Activate it
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root (copy from `.env.example`):

```bash
GEMINI_API_KEY=your_key_here
```

Get a free key at [aistudio.google.com](https://aistudio.google.com).

The server starts and serves schedules without the key — the AI explanation step is skipped and the response includes `"error": "GEMINI_API_KEY not set"` in the `ai` field.

---

## Running the Server

```bash
# From the project root
python backend/run_api.py
```

Server starts at `http://localhost:8000`. Hot-reload is enabled — file changes restart the server automatically.

---

## API Reference

### `GET /api/health`

Returns server status and whether a Gemini key is configured.

```json
{ "status": "ok", "gemini_configured": true }
```

---

### `POST /api/schedule`

Builds and returns a schedule using the deterministic greedy algorithm. No AI call is made.

**Request body**

```json
{
  "owner": {
    "name": "Jordan",
    "available_start": "08:00",
    "available_end": "20:00"
  },
  "pets": [
    {
      "name": "Buddy",
      "species": "dog",
      "age_years": 3.0,
      "tasks": [
        {
          "task_id": "a1b2c3d4",
          "title": "Morning walk",
          "duration_minutes": 30,
          "priority": "HIGH",
          "preferred_time": "morning",
          "recurring": true,
          "notes": "",
          "completed": false
        }
      ]
    }
  ]
}
```

**Response**

```json
{
  "scheduled": [
    {
      "task_id": "a1b2c3d4",
      "title": "Morning walk",
      "duration_minutes": 30,
      "priority": "HIGH",
      "preferred_time": "morning",
      "recurring": true,
      "notes": "",
      "completed": false,
      "scheduled_start": "08:00 AM",
      "scheduled_end": "08:30 AM"
    }
  ],
  "skipped": [],
  "conflicts": [],
  "total_minutes": 30,
  "available_minutes": 720,
  "utilization_pct": 4.2
}
```

---

### `POST /api/ai-schedule`

Same scheduling logic, plus:
1. RAG retrieval from the pet care knowledge base
2. Guardrail validation (0–100 score)
3. Gemini AI reasoning + explanation + recommendations

**Request body** — identical to `/api/schedule`

**Response** — all fields from `/api/schedule`, plus:

```json
{
  "rag_guidelines": [
    "[EXERCISE] Dogs should not be walked immediately after eating..."
  ],
  "validation": {
    "passed": true,
    "issues": [],
    "warnings": ["Only 4.2% of your window is used..."],
    "score": 95
  },
  "ai": {
    "reasoning": "Morning walk was placed first because...",
    "explanation": "Today's schedule starts with Buddy's walk...",
    "recommendations": [
      "Wait 30–60 minutes after feeding before walking Buddy.",
      "Consider adding an evening walk for additional exercise."
    ],
    "error": null
  }
}
```

---

## Architecture

```
backend/
├── main.py          ← FastAPI app — route definitions and request/response wiring
├── schemas.py       ← Pydantic models for all request and response shapes
├── services/
│   ├── ai_agent.py  ← Calls Gemini 2.0 Flash; returns reasoning, explanation, recommendations
│   ├── rag.py       ← Keyword-based retrieval over pet_care_kb.json
│   └── evaluator.py ← Rule-based guardrail; scores schedules 0–100
└── data/
    └── pet_care_kb.json  ← 15 pet care guidelines indexed by species + keyword
```

### Service descriptions

**`ai_agent.py`**
Constructs a structured prompt from the schedule result, pet context, and RAG guidelines, then calls `gemini-2.0-flash`. The response is parsed as JSON with three keys: `reasoning`, `explanation`, and `recommendations`. Gracefully returns an `error` field if the API key is missing or the call fails.

**`rag.py`**
Loads `pet_care_kb.json` at call time and matches entries against two criteria: (1) the entry's `species` matches a pet in the request or is `"all"`, and (2) at least one of the entry's `keywords` appears as a substring in a task title or notes field. Returns up to 6 matching guidelines as a formatted string.

**`evaluator.py`**
Applies four rules to a `ScheduleResult`:
- Any HIGH-priority task in the skipped list → issue (−20 pts each)
- Any time conflict in the output → issue (−20 pts each)
- Utilisation > 95% → warning (−5 pts)
- Utilisation < 20% with tasks scheduled → warning (−5 pts)

Returns `passed: true` only when there are zero issues.

---

## Evaluation Harness

```bash
python backend/evaluate.py
```

Runs 8 test cases covering: normal day, overloaded window, conflicting time preferences, empty schedule, low utilisation, schedule determinism, RAG retrieval, and multi-pet scheduling.

Expected output: `8/8 tests passed`.
