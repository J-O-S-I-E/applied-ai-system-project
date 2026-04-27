# PawPal+ — Frontend

React + Vite single-page application for the PawPal+ AI pet care scheduling assistant.

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI framework | React 18 |
| Build tool | Vite 5 |
| Styling | Plain CSS with custom properties |
| HTTP client | `fetch` (built-in) |
| State management | React `useState` (client-side only) |

---

## Prerequisites

- Node.js 18 or higher (`node --version`)
- The [backend server](../backend/README.md) running on `http://localhost:8000`

---

## Installation

```bash
cd frontend
npm install
```

---

## Running

```bash
npm run dev
```

Opens at `http://localhost:5173`. The Vite dev server proxies all `/api/*` requests to `http://localhost:8000`, so no CORS configuration is needed during development.

### Production build

```bash
npm run build    # outputs to frontend/dist/
npm run preview  # local preview of the built output
```

---

## Component Architecture

```
App.jsx                        ← Root: global state, 3-tab navigation
│
├── components/
│   ├── OwnerSetup.jsx         ← Name + availability window form
│   ├── PetManager.jsx         ← Add/list pets
│   ├── TaskManager.jsx        ← Add/list tasks per pet
│   └── ScheduleView.jsx       ← Build schedule + display results + AI panel
│
└── services/
    └── api.js                 ← fetch wrappers for /api/schedule and /api/ai-schedule
```

### State management

All application state lives in `App.jsx` and is passed down as props. There is no external state library.

| State | Shape | Description |
|---|---|---|
| `owner` | `{ name, available_start, available_end, saved }` | Owner profile |
| `pets` | `Pet[]` | Array of pet objects, each with a `tasks` array |
| `scheduleResult` | `ScheduleResponse \| null` | Last API response |

**Pet shape**
```js
{
  id: string,            // client-side UUID (React key)
  name: string,
  species: "dog" | "cat" | "other",
  age_years: number,
  tasks: Task[]
}
```

**Task shape**
```js
{
  task_id: string,       // 8-char UUID slice, sent to API
  title: string,
  duration_minutes: number,
  priority: "HIGH" | "MEDIUM" | "LOW",
  preferred_time: "morning" | "afternoon" | "evening" | null,
  recurring: boolean,
  notes: string,
  completed: boolean
}
```

### Tab layout

| Tab | Components rendered |
|---|---|
| Setup | `OwnerSetup` + `PetManager` |
| Tasks | `TaskManager` |
| Schedule | `ScheduleView` |

### ScheduleView behaviour

- **Build Schedule (Fast)** — calls `POST /api/schedule`, shows metrics + task table.
- **Generate AI Schedule** — calls `POST /api/ai-schedule`, shows the same table plus RAG guidelines panel, guardrail score bar, AI reasoning, explanation, and recommendations.
- **Done button** — marks a task complete in client state and clears the result, prompting the user to rebuild.

---

## API Integration

```
src/services/api.js
```

Two exported functions:

```js
buildSchedule(owner, pets)    // → POST /api/schedule
buildAISchedule(owner, pets)  // → POST /api/ai-schedule
```

Both accept the same shape and return a `ScheduleResponse` object. Errors throw with the message from the API's `detail` field.

The proxy in `vite.config.js` rewrites `/api` → `http://localhost:8000/api` during development, so no absolute URLs appear in application code.

---

## Styling

All styles live in two files:

| File | Purpose |
|---|---|
| `src/index.css` | CSS custom properties (design tokens), global reset |
| `src/App.css` | All component styles — layout, cards, forms, tables, AI panel |

CSS custom properties (defined in `:root`):

```css
--primary        #7c3aed   purple
--danger         #dc2626   red     (HIGH priority)
--warning        #d97706   amber   (MEDIUM priority / warnings)
--success        #16a34a   green   (LOW priority / success states)
--bg             #f1f5f9   page background
--card           #ffffff   card background
```
