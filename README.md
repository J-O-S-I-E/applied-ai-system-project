# PawPal+ AI

An AI-powered pet care scheduling assistant. Owners register their pets, add daily care tasks, and receive an intelligently explained schedule — backed by a Gemini language model, a pet care knowledge base, and a rule-based guardrail layer.

---

## Quick Start

**1 — Install Python dependencies**
```bash
pip install -r requirements.txt
```

**2 — Set your Gemini API key** (free at [aistudio.google.com](https://aistudio.google.com))
```bash
# Windows
set GEMINI_API_KEY=your_key_here

# macOS / Linux
export GEMINI_API_KEY=your_key_here
```

**3 — Start the API server** (Terminal 1)
```bash
python backend/run_api.py
# → http://localhost:8000
```

**4 — Start the React frontend** (Terminal 2)
```bash
cd frontend
npm install      # first time only
npm run dev
# → http://localhost:5173
```

Open `http://localhost:5173` in your browser. The app works without the Gemini key — only the AI explanation step is skipped.

---

## System Architecture

```
┌──────────────────────────────────────────────────────┐
│              React Frontend  (Vite · port 5173)       │
│                                                       │
│   [ Setup ]  [ Tasks ]  [ Schedule ]                  │
│      │           │            │                       │
│   OwnerSetup  TaskManager  ScheduleView               │
│   PetManager                  │                       │
│                          ⚡  Build Schedule (Fast)     │
│                          🧠  Generate AI Schedule      │
└────────────────────┬─────────────────────────────────┘
                     │  HTTP  /api/*  (proxied by Vite)
                     ▼
┌──────────────────────────────────────────────────────┐
│              FastAPI Backend  (Uvicorn · port 8000)   │
│                                                       │
│   POST /api/schedule      → fast schedule only        │
│   POST /api/ai-schedule   → schedule + AI layer       │
└────┬────────────────────────────┬────────────────────┘
     │                            │
     ▼                            ▼
┌─────────────────┐    ┌─────────────────────────────┐
│  pawpal_system  │    │          AI Layer            │
│                 │    │                              │
│  Owner          │    │  rag.py                      │
│  Pet            │    │  → matches keywords against  │
│  Task           │    │    pet_care_kb.json (15 tips) │
│  Scheduler      │    │                              │
│  ScheduleResult │    │  ai_agent.py                 │
│                 │    │  → Gemini 2.0 Flash           │
│  greedy, first- │    │    reasoning + explanation   │
│  fit algorithm  │    │                              │
└─────────────────┘    │  evaluator.py                │
                       │  → rule-based guardrails     │
                       │    0-100 quality score        │
                       └─────────────────────────────┘
```

---

## Features

### Core scheduling (rule-based)
- **Priority-first ordering** — HIGH tasks always placed before MEDIUM or LOW
- **Preferred-time hints** — soft constraints for morning / afternoon / evening
- **Conflict detection** — every task pair checked; overlaps surfaced as warnings
- **Recurring tasks** — completing a recurring task queues its next-day clone
- **Skip tracking** — tasks that overflow the window are listed with an explanation

### AI layer
- **Gemini AI agent** — generates step-by-step reasoning and a plain-English explanation for every scheduling decision
- **RAG retrieval** — 15 pet care guidelines retrieved by species and keyword before the AI prompt is built; injected as context
- **Guardrail evaluator** — rule-based validation scores the schedule 0–100 and surfaces blocking issues (skipped HIGH tasks, conflicts) and warnings (utilisation extremes)

---

## Project Structure

```
pawpal-plus/
├── requirements.txt
├── .env.example
│
├── backend/
│   ├── pawpal_system.py   Core domain logic — Owner, Pet, Task, Scheduler
│   ├── run_api.py         Starts the FastAPI server
│   ├── evaluate.py        8-case test harness (no Gemini key required)
│   ├── main.py            FastAPI route definitions
│   ├── schemas.py         Pydantic request / response models
│   ├── services/
│   │   ├── ai_agent.py    Gemini 2.0 Flash integration
│   │   ├── rag.py         Keyword retrieval
│   │   └── evaluator.py   Rule-based guardrails
│   └── data/
│       └── pet_care_kb.json   15-entry pet care knowledge base
│
└── frontend/              React + Vite application
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   │   ├── OwnerSetup.jsx
    │   │   ├── PetManager.jsx
    │   │   ├── TaskManager.jsx
    │   │   └── ScheduleView.jsx
    │   └── services/api.js
    ├── package.json
    └── vite.config.js
```

For detailed instructions on each part of the system, see:
- [backend/README.md](backend/README.md) — API reference, service descriptions, configuration
- [frontend/README.md](frontend/README.md) — component architecture, state management, styling

---

## Testing

### Evaluation harness (no API key needed)
```bash
python backend/evaluate.py
```

Runs 8 automated test cases:

| # | Test | Expected |
|---|---|---|
| 1 | Normal balanced day | PASS |
| 2 | Overloaded window — HIGH task can't fit | FAIL (correct) |
| 3 | Conflicting time preferences | PASS |
| 4 | Empty schedule | PASS |
| 5 | Low utilisation warning | PASS |
| 6 | Determinism — same inputs → same output | PASS |
| 7 | RAG retrieval returns relevant guidelines | PASS |
| 8 | Multi-pet scheduling | PASS |

Expected output: `8/8 tests passed`

---

## Reflection

### 1. What is this project?

PawPal+ started as a **deterministic scheduling tool**: a greedy algorithm that sorts pet care tasks by priority and assigns them to time slots. The AI extension transforms it into an **adaptive, explainable system** by adding a language model, a knowledge retrieval layer, and a self-checking guardrail.

The two systems coexist — the fast schedule button uses the original algorithm with zero AI calls. The AI schedule button uses the same algorithm for the actual time assignment (keeping that logic predictable and testable), then layers explanation and validation on top.

---

### 2. System design decisions

**Separation of concerns**

The original design split data (`Owner → Pet → Task`) from logic (`Scheduler`). This decision paid off during the AI extension: the Scheduler could be reused without modification, and the AI services simply wrap its output rather than replacing it.

**Stateless API**

The React frontend owns all application state. Every API call sends the complete owner + pets + tasks payload. This means the backend is stateless — no session management, no database — which simplifies deployment and keeps each request independently testable.

**Graceful degradation**

All three AI services (`ai_agent`, `rag`, `evaluator`) are optional from the UI's perspective. If `GEMINI_API_KEY` is missing, the evaluator and RAG still run; only the Gemini call is skipped and an error message is returned in the `ai.error` field. The schedule itself is never blocked by an AI failure.

**Design changes from original**

- Added `task_id` (UUID) to `Task` to support reliable client-side identification and "mark done" without title collisions.
- Added `ScheduleResult` as a typed return object rather than a plain dict — this made the FastAPI response schema straightforward to derive with Pydantic.
- Kept `available_start` / `available_end` as strings on `Owner` — the React time input natively produces "HH:MM" strings, and conversion happens inside the Scheduler only when a `datetime` object is actually needed.

---

### 3. Scheduling logic and tradeoffs

**Algorithm**

The scheduler uses a greedy, first-fit approach:
1. Collect all pending tasks from all pets
2. Sort by priority (HIGH first), break ties by shortest duration
3. Walk through the sorted list; assign each task the next available slot, respecting preferred-time hints where possible
4. Skip any task whose end time would exceed the availability window
5. Check every task pair for overlapping durations and surface conflicts as warnings

**Why greedy?**

A greedy algorithm is simple to reason about: an owner reading the output can predict exactly why each task landed where it did. Optimality (fitting the maximum number of tasks) matters less than predictability for a daily care schedule.

**Key tradeoff**

A single large HIGH task can displace several smaller MEDIUM tasks that would collectively fit in the same window. This is intentional — the system's core promise is that the most important care always happens, even at the cost of lower-priority items.

**Conflict detector**

An O(n²) nested-loop comparison is used rather than a sort-then-single-pass approach. The faster algorithm only catches adjacent overlaps; the nested loop catches any pair including non-adjacent tasks. At 5–15 tasks per schedule the performance difference is immeasurable.

---

### 4. AI features

**Gemini agent (`ai_agent.py`)**

Takes the complete schedule context — owner availability, all pet details, scheduled and skipped tasks, and retrieved guidelines — and asks Gemini 2.0 Flash to return a structured JSON response with three fields: `reasoning` (step-by-step decision rationale), `explanation` (a plain-English owner-facing summary), and `recommendations` (2–3 actionable tips). The response is parsed and re-validated before being forwarded to the frontend.

**RAG (`rag.py`)**

A simple but effective keyword-based retrieval: 15 entries in `pet_care_kb.json`, each with a species tag and a keyword list. Before building the Gemini prompt, the system scans all task titles and notes for keyword matches, filters by the pet species in the request, and prepends up to 6 matching guidelines as context. This gives the model grounding in real pet care facts rather than relying solely on training data.

Example: a schedule containing "Morning walk" and "Feeding" for a dog retrieves the guideline *"Dogs should not be walked immediately after eating — wait at least 30–60 minutes to reduce risk of bloat."* The model then uses this when reasoning about task order.

**Guardrail evaluator (`evaluator.py`)**

Rule-based — no LLM involved. Four checks produce a 0–100 score:
- Skipped HIGH-priority task → issue, −20 pts each
- Time conflict in output → issue, −20 pts each
- Utilisation > 95% → warning, −5 pts
- Utilisation < 20% with scheduled tasks → warning, −5 pts

This layer runs even without a Gemini key and gives users an objective quality signal independent of the AI explanation.

---

### 5. AI collaboration

**How AI was used during development**

- **Architecture planning** — used AI to map out the FastAPI + React + Gemini integration before writing any code. Most effective when the prompt was specific: *"I have a Python dataclass-based domain model. How should I structure Pydantic schemas to mirror it for a FastAPI endpoint?"*

- **RAG knowledge base** — used AI to draft the initial 15 pet care guidelines, then reviewed and edited each one for accuracy. This was faster than manual research and produced well-structured entries.

- **Prompt engineering** — iterated on the Gemini prompt through several versions. The key insight was asking for a strict JSON response with named keys rather than free text — this eliminated the need to parse unstructured output.

- **Debugging** — used AI to interpret FastAPI validation errors and trace a Pydantic v2 schema mismatch in the response model.

**What worked well with AI assistance**

The most reliable AI outputs came from prompts that included concrete code context. Asking *"Given this Pydantic schema, write the FastAPI route"* produced immediately usable code. Vague prompts like *"make the AI smarter"* produced unfocused suggestions.

**Where AI assistance fell short**

- Initial Gemini prompt produced inconsistently structured responses — sometimes returning markdown-fenced JSON, sometimes plain text. The workaround (stripping code fences before parsing) had to be discovered through testing, not AI suggestion.
- AI occasionally suggested over-engineering: adding a vector database for RAG, adding Redis for caching. Both were rejected in favour of simpler solutions appropriate for the project scale.

**Key takeaway**

AI is most useful when you already have a clear design in mind and are asking it to fill in known gaps. The architectural decisions — stateless API, separation of scheduling logic from AI layer, graceful degradation — were made by reasoning through the requirements, not by asking an AI what to do.

---

### 6. Testing and verification

**Evaluation harness (`evaluate.py`)**

Eight test cases cover the main paths through the system:
- Determinism: identical inputs produce identical outputs on every run
- Guardrail correctness: overloaded schedules are correctly flagged as failures
- RAG retrieval: relevant guidelines are returned for standard dog/cat tasks
- Multi-pet: tasks from different pets are all considered in one schedule

**Confidence level**

High confidence in the scheduling logic — the greedy algorithm and conflict detector are tested with both happy paths and edge cases. Medium confidence in the AI output quality — the Gemini responses are structurally validated but their content depends on prompt quality and model behaviour, which can vary.

---

### 7. Limitations and future work

**Current limitations**
- No persistent storage — refreshing the browser wipes all state
- RAG is keyword-based; semantically similar phrases ("dinner" vs "evening meal") may not match
- Schedule quality depends on prompt wording — edge cases can produce unexpected explanations
- No authentication — the API is open to any localhost caller

**Future improvements**
- Replace keyword RAG with vector embeddings for semantic matching
- Add SQLite persistence so pets and tasks survive page refreshes
- Learn from user feedback (thumbs up/down on AI explanations) to improve prompt tuning over time
- Mobile app with push notifications for task reminders
- Multi-user support with owner accounts
