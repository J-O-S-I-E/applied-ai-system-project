# PawPal+ AI

An AI-powered pet care scheduling assistant. Owners register their pets, add daily care tasks, and receive an intelligently explained schedule — backed by a Gemini language model, a semantic vector knowledge base, and a rule-based guardrail layer.

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

Or create a `.env` file in the project root:
```
GEMINI_API_KEY=your_key_here
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

Open `http://localhost:5173`. The app works without a Gemini key — only the AI explanation and RAG embedding steps are skipped.

> **First AI request**: The Chroma vector store is built automatically on the first `/api/ai-schedule` call. This takes ~30 seconds as it embeds all PDF chunks using Gemini. Subsequent requests load from the persisted store instantly.

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
│   POST /api/ai-schedule   → schedule + full AI layer  │
│   GET  /api/health        → status + key check        │
└────┬────────────────────────────┬────────────────────┘
     │                            │
     ▼                            ▼
┌─────────────────┐    ┌─────────────────────────────────┐
│  pawpal_system  │    │           AI Layer               │
│                 │    │                                  │
│  Owner          │    │  rag.py  (per-pet semantic RAG)  │
│  Pet            │    │  ├─ Gemini embeddings            │
│  Task           │    │  ├─ Chroma vector store          │
│  Scheduler      │    │  ├─ Multi-query retrieval        │
│  ScheduleResult │    │  ├─ Hybrid reranking             │
│                 │    │  └─ Source attribution           │
│  greedy first-  │    │                                  │
│  fit algorithm  │    │  ai_agent.py  (LangChain chain)  │
└─────────────────┘    │  ├─ ChatGoogleGenerativeAI       │
                       │  ├─ ChatPromptTemplate           │
                       │  └─ StrOutputParser → JSON       │
                       │                                  │
                       │  evaluator.py  (guardrails)      │
                       │  └─ rule-based 0–100 score       │
                       └─────────────────────────────────┘
```

---

## Features

### Core scheduling
- **Priority-first ordering** — HIGH tasks always placed before MEDIUM or LOW
- **Preferred-time hints** — soft constraints for morning / afternoon / evening
- **Conflict detection** — every task pair checked; overlaps surfaced as warnings
- **Recurring tasks** — completing a recurring task queues its next-day clone
- **Skip tracking** — tasks that overflow the window are listed separately

### AI layer
- **Semantic RAG** — PDF pet care guides (Dog-Book.pdf, Cat-Book.pdf from Humane Fort Wayne) are chunked, embedded with `gemini-embedding-001`, and stored in a persistent Chroma vector store. Per-pet retrieval runs multi-query search + hybrid reranking for the most relevant passages.
- **Per-pet context** — each pet's species, age, tasks, and notes drive independent retrieval queries. Retrieved passages are shown in a collapsible panel per pet.
- **LangChain AI agent** — `ChatGoogleGenerativeAI` + `ChatPromptTemplate` + `StrOutputParser` chain calls Gemini 2.0 Flash with the schedule context and retrieved passages, returning structured JSON: `reasoning`, `explanation`, and `recommendations`.
- **Guardrail evaluator** — rule-based validation scores the schedule 0–100; surfaces blocking issues (skipped HIGH tasks, conflicts) and warnings (utilisation extremes) independently of the LLM.

---

## Project Structure

```
applied-ai-system-project/
├── requirements.txt
├── .env                        ← GEMINI_API_KEY goes here
│
├── backend/
│   ├── pawpal_system.py        Core domain — Owner, Pet, Task, Scheduler
│   ├── run_api.py              Starts the FastAPI/Uvicorn server
│   ├── evaluate.py             8-case automated test harness
│   ├── main.py                 FastAPI route definitions
│   ├── schemas.py              Pydantic request/response models
│   ├── services/
│   │   ├── ai_agent.py         LangChain chain → Gemini 2.0 Flash
│   │   ├── rag.py              Semantic RAG — Chroma + Gemini embeddings
│   │   └── evaluator.py        Rule-based guardrail layer
│   └── data/
│       ├── Dog-Book.pdf        Humane Fort Wayne dog care guide
│       ├── Cat-Book.pdf        Humane Fort Wayne cat care guide
│       └── chroma_db/          Persisted vector store (auto-generated)
│
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── App.css
    │   ├── index.css
    │   ├── components/
    │   │   ├── OwnerSetup.jsx
    │   │   ├── PetManager.jsx
    │   │   ├── TaskManager.jsx
    │   │   └── ScheduleView.jsx
    │   └── services/
    │       └── api.js
    ├── package.json
    └── vite.config.js
```

---

## Testing

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
| 7 | RAG retrieval returns relevant passages | PASS |
| 8 | Multi-pet scheduling | PASS |

Expected output: `8/8 tests passed`

Tests 1–6 and 8 run without a Gemini key. Test 7 is skipped automatically if no PDFs or API key are present.

---

## Reflection

### 1. What is this project?

PawPal+ started as a **deterministic scheduling tool**: a greedy algorithm that sorts pet care tasks by priority and assigns them to time slots. The AI extension transforms it into an **adaptive, explainable system** by adding a language model, a semantic knowledge retrieval layer, and a self-checking guardrail.

The two systems coexist — the fast schedule button uses the original algorithm with zero AI calls. The AI schedule button uses the same algorithm for time assignment (keeping that logic predictable and testable), then layers RAG retrieval, Gemini explanation, and guardrail validation on top.

---

### 2. System design decisions

**Separation of concerns**

The original design split data (`Owner → Pet → Task`) from logic (`Scheduler`). This paid off during the AI extension: the Scheduler was reused without modification, and the AI services wrap its output rather than replacing it.

**Stateless API**

The React frontend owns all application state. Every API call sends the complete owner + pets + tasks payload. This keeps the backend stateless — no session management, no database — which simplifies deployment and makes each request independently testable.

**Graceful degradation**

All three AI services (`ai_agent`, `rag`, `evaluator`) are optional from the UI's perspective. If `GEMINI_API_KEY` is missing, the evaluator still runs; the RAG and Gemini steps are skipped and an error message is returned in the `ai.error` field. The schedule itself is never blocked by an AI failure.

**Per-pet RAG isolation**

Each pet gets its own retrieval pass scoped to its species, age, and tasks. This prevents a dog's walking guidelines from contaminating a cat's feeding context. The multi-query approach (4 queries per pet) broadens recall; hybrid reranking (semantic score + keyword overlap boost) improves precision.

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

---

### 4. AI features

**Semantic RAG (`rag.py`)**

Pet care PDFs (Humane Fort Wayne Dog-Book and Cat-Book) are split into 400-character chunks with 80-character overlap using `RecursiveCharacterTextSplitter`, embedded with `gemini-embedding-001`, and stored in a persistent Chroma vector store at `backend/data/chroma_db/`.

For each pet, four queries are built from the pet's species, age, and task descriptions. Each query hits the species-filtered vector store (`k=6`), and all results are merged. Deduplication runs first, then hybrid reranking (semantic position + keyword overlap score + boost for pet-care-specific terms like "walk", "feeding", "grooming"). The top 3 passages after relevance filtering are returned with source attribution.

**LangChain AI agent (`ai_agent.py`)**

Uses a `ChatPromptTemplate` → `ChatGoogleGenerativeAI` → `StrOutputParser` chain. The prompt injects the full schedule context (owner window, all pets, scheduled and skipped tasks) plus the per-pet RAG passages retrieved above. Gemini 2.0 Flash is asked to return strict JSON with three keys: `reasoning` (step-by-step decision rationale), `explanation` (plain-English owner-facing summary), and `recommendations` (3–4 actionable tips drawn directly from the retrieved passages). A markdown-fence stripping step handles model output that wraps JSON in code blocks.

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
- **RAG pipeline design** — used AI to design the multi-query retrieval + hybrid reranking approach, then reviewed and implemented each stage.
- **Prompt engineering** — iterated on the Gemini prompt through several versions. The key insight was asking for strict JSON output with named keys rather than free text — this eliminated the need to parse unstructured output.
- **Debugging** — used AI to interpret FastAPI validation errors and trace Pydantic v2 schema mismatches.

**What worked well with AI assistance**

The most reliable outputs came from prompts that included concrete code context. Asking *"Given this Pydantic schema, write the FastAPI route"* produced immediately usable code. Vague prompts like *"make the AI smarter"* produced unfocused suggestions.

**Where AI assistance fell short**

- Initial Gemini prompt produced inconsistently structured responses — sometimes returning markdown-fenced JSON, sometimes plain text. The workaround had to be discovered through testing.
- AI occasionally suggested over-engineering where simpler solutions worked fine.

**Key takeaway**

AI is most useful when you already have a clear design in mind and are asking it to fill in known gaps. The architectural decisions — stateless API, separation of scheduling logic from AI layer, graceful degradation — were made by reasoning through the requirements, not by asking an AI what to do.

---

### 6. Testing and verification

**Evaluation harness (`evaluate.py`)**

Eight test cases cover the main paths through the system:
- Determinism: identical inputs produce identical outputs on every run
- Guardrail correctness: overloaded schedules are correctly flagged as failures
- RAG retrieval: relevant passages are returned for standard dog/cat tasks
- Multi-pet: tasks from different pets are all considered in one schedule

**Confidence level**

High confidence in the scheduling logic — the greedy algorithm and conflict detector are tested with both happy paths and edge cases. Medium confidence in the AI output quality — the Gemini responses are structurally validated but their content depends on prompt quality and model behaviour, which can vary.

---

### 7. Limitations and future work

**Current limitations**
- No persistent storage — refreshing the browser wipes all state
- The Chroma vector store must be rebuilt if PDFs change (delete `backend/data/chroma_db/` to trigger a rebuild)
- No authentication — the API is open to any localhost caller
- Species is limited to dog/cat; other pets fall back to unfiltered retrieval

**Future improvements**
- SQLite persistence so pets and tasks survive page refreshes
- Learn from user feedback (thumbs up/down on AI explanations) to improve prompt tuning over time
- Mobile app with push notifications for task reminders
- Multi-user support with owner accounts
- Support additional species (rabbit, bird, etc.) with dedicated care guides
